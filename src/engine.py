"""Technique chaining: passing one technique's output into a later technique.

A parameter value is either a plain literal or a reference of the form
``${artifact.field}`` that points at a field of an artifact produced by an
earlier step. An artifact is a plain dict stored under a name for the duration
of a run.

Pieces:

  * ``RunContext``        - the per-run artifact store, plus an optional on-disk
                            artifact directory used as a resume fallback.
  * ``parse_reference``   - the ``${artifact.field}`` grammar.
  * ``resolve_params``    - expands references in a parameter dict, returning
                            the resolved values plus their provenance.
  * ``validate_playbook`` - offline load-time checks: reference syntax,
                            artifact ordering, and required-parameter presence.
                            No API calls, no auth, no file writes.
  * ``build_credential``  - turn a step's resolved credential parameter into the
                            ``token`` dict a technique expects, minting a token
                            for the required audience from the source artifact's
                            refresh token when the scopes differ.
"""

import difflib
import json
import logging
import os
import re
from datetime import datetime

from src.auth import get_token_with_refresh_token

# An artifact name, then one or more dotted field segments. The reference must
# be the *entire* scalar - no surrounding text, no whitespace.
REFERENCE_RE = re.compile(
    r'^\$\{([A-Za-z_][A-Za-z0-9_-]*)((?:\.[A-Za-z_][A-Za-z0-9_-]*)+)\}$'
)


class ReferenceError(Exception):
    """A reference could not be parsed or resolved.

    Raised for a malformed ``${...}`` string, an unknown artifact, an unknown
    field, or an attempt to walk into a non-mapping value.
    """


def parse_reference(value):
    """Classify a parameter value.

    Returns ``None`` when *value* is a plain literal (any non-string, or a
    string with no ``${``). Returns ``(artifact_name, [field, ...])`` for a
    well-formed reference.

    Raises ``ReferenceError`` when *value* contains ``${`` but is not a full,
    valid reference. A malformed reference is never silently treated as a
    literal: doing so would turn a broken reference into a "file not found"
    further down the line, pointing at the wrong problem.
    """
    if not isinstance(value, str) or '${' not in value:
        return None

    match = REFERENCE_RE.match(value)
    if not match:
        raise ReferenceError(
            f"malformed reference {value!r}\n"
            f"    expected ${{artifact.field}}, with at least one field and no "
            f"surrounding text or whitespace"
        )

    name = match.group(1)
    fields = match.group(2).lstrip('.').split('.')
    return name, fields


def _walk(artifact_name, fields, data):
    """Walk *fields* into *data*, segment by segment."""
    current = data
    for depth, field in enumerate(fields):
        if not isinstance(current, dict):
            walked = '.'.join([artifact_name] + fields[:depth])
            raise ReferenceError(
                f"path '${{{artifact_name}.{'.'.join(fields)}}}' failed at "
                f"'{field}': '{walked}' is a {type(current).__name__}, not a mapping"
            )
        if field not in current:
            available = ', '.join(current.keys()) or '(none)'
            close = difflib.get_close_matches(field, list(current.keys()), n=1)
            hint = f", did you mean '{close[0]}'?" if close else ""
            raise ReferenceError(
                f"artifact '{artifact_name}' has no field '{field}'{hint}\n"
                f"    available fields: {available}"
            )
        current = current[field]
    return current


def resolve_params(params, ctx):
    """Resolve every reference in *params* against *ctx*.

    Returns ``(resolved_params, provenance)`` where *provenance* maps a
    parameter name to the artifact name it was resolved from. Literals are
    absent from *provenance*.
    """
    resolved = {}
    provenance = {}

    for key, value in params.items():
        ref = parse_reference(value)
        if ref is None:
            resolved[key] = value
            continue

        name, fields = ref
        artifact = ctx.get(name)
        if artifact is None:
            raise ReferenceError(
                f"parameter '{key}': artifact '{name}' is not available\n"
                f"    available: {', '.join(ctx.names()) or '(none)'}"
            )
        resolved[key] = _walk(name, fields, artifact)
        provenance[key] = name

    return resolved, provenance


# Short scope name -> the .default scope string each technique family needs.
# Mirrors the constants scattered across the client modules today.
SCOPES = {
    "graph":    "https://graph.microsoft.com/.default",
    "ews":      "https://outlook.office365.com/.default",
    "rest":     "https://outlook.office365.com/.default",
    "arm":      "https://management.azure.com/.default",
    "keyvault": "https://vault.azure.net/.default",
    "prt":      "https://enrollment.manage.microsoft.com/.default",
}


def _artifact_covers_scope(artifact, scope_name):
    """True if the artifact already holds a token for *scope_name*."""
    want = SCOPES.get(scope_name, scope_name)
    if artifact.get("scope") == want or artifact.get("resource") == want:
        return True
    return scope_name in (artifact.get("_scoped_tokens") or {})


def mint_scoped_token(artifact, scope_name):
    """Return an access token for *scope_name*, minting it from the artifact's
    refresh token if not already held, and caching it back into the artifact."""
    cache = artifact.setdefault("_scoped_tokens", {})
    if scope_name in cache:
        return cache[scope_name]

    want = SCOPES.get(scope_name, scope_name)
    refresh_token = artifact.get("refresh_token")
    if not refresh_token:
        raise ReferenceError(
            f"cannot acquire a '{scope_name}' token: the source artifact has no "
            f"refresh_token (its token is scoped for '{artifact.get('scope')}')"
        )

    logging.info(f"minting a '{scope_name}'-scoped token from the source artifact's refresh token")
    result = get_token_with_refresh_token(
        artifact.get("tenant_id"), refresh_token,
        scope=want, client_id=artifact.get("client_id"),
    )
    if not result or not result.get("access_token"):
        raise ReferenceError(f"failed to mint a '{scope_name}'-scoped token from the source artifact")

    cache[scope_name] = result["access_token"]
    if result.get("refresh_token"):
        artifact["refresh_token"] = result["refresh_token"]
    return result["access_token"]


def build_credential(resolved_value, source_artifact, ctx, scope_name=None):
    """Build the ``token`` dict a technique receives, plus its ews_impersonation flag.

    resolved_value  - the step's already-resolved credential parameter.
    source_artifact - provenance: the artifact name the value came from, or None
                      when the caller passed a literal.
    scope_name      - the audience the technique needs (a key of SCOPES), or None
                      when the technique calls no scoped API.

    A literal has no provenance: it is used as-is, with ews_impersonation False.
    Otherwise ews_impersonation follows the source artifact's ``flow`` (4.6), and
    when the artifact's token is for a different audience a new one is minted from
    its refresh token and cached back (4.5).
    """
    if source_artifact is None:
        return {"access_token": resolved_value}, False

    artifact = ctx.get(source_artifact)
    if not isinstance(artifact, dict):
        return {"access_token": resolved_value}, False

    ews_impersonation = artifact.get("flow") == "client_credentials"

    if not scope_name:
        return {"access_token": resolved_value}, ews_impersonation

    if _artifact_covers_scope(artifact, scope_name):
        cached = (artifact.get("_scoped_tokens") or {}).get(scope_name)
        return {"access_token": cached or resolved_value}, ews_impersonation

    return {"access_token": mint_scoped_token(artifact, scope_name)}, ews_impersonation


class RunContext:
    """Per-run artifact store with an optional on-disk fallback directory."""

    def __init__(self, artifact_dir=None):
        self._store = {}
        self.artifact_dir = artifact_dir

    def get(self, name):
        """In-memory store first, then ``<artifact_dir>/<name>.json``.

        A disk fallback is logged at INFO with the source file's modification
        time, because a stale directory silently supplies expired tokens.
        Returns ``None`` when the artifact is nowhere.
        """
        if name in self._store:
            return self._store[name]

        if self.artifact_dir:
            path = os.path.join(self.artifact_dir, f"{name}.json")
            if os.path.isfile(path):
                mtime = datetime.fromtimestamp(
                    os.path.getmtime(path)
                ).strftime('%Y-%m-%d %H:%M:%S')
                with open(path, 'r') as handle:
                    artifact = json.load(handle)
                logging.info(
                    f"artifact '{name}' resolved from disk fallback: {path} "
                    f"(modified {mtime})"
                )
                return artifact

        return None

    def put(self, name, artifact, save_to_disk=None):
        """Store *artifact*, then optionally serialize it.

        Writes to *save_to_disk* if given, and to ``<artifact_dir>/<name>.json``
        if an artifact directory is set. Logs the artifact's field names only,
        never their values, since artifacts hold live secrets.
        """
        self._store[name] = artifact

        if isinstance(artifact, dict):
            fields = ', '.join(artifact.keys()) or '(no fields)'
        else:
            fields = f"(non-dict: {type(artifact).__name__})"
        logging.info(f"stored artifact '{name}' with fields: {fields}")

        if save_to_disk:
            with open(save_to_disk, 'w') as handle:
                json.dump(artifact, handle, indent=2)
            logging.info(f"wrote artifact '{name}' to {save_to_disk}")

        if self.artifact_dir:
            os.makedirs(self.artifact_dir, exist_ok=True)
            path = os.path.join(self.artifact_dir, f"{name}.json")
            with open(path, 'w') as handle:
                json.dump(artifact, handle, indent=2)
            logging.info(f"wrote artifact '{name}' to {path}")

    def names(self):
        """Artifact names available in memory and in the artifact directory."""
        found = set(self._store)
        if self.artifact_dir and os.path.isdir(self.artifact_dir):
            for entry in os.listdir(self.artifact_dir):
                if entry.endswith('.json'):
                    found.add(entry[:-len('.json')])
        return sorted(found)


def validate_playbook(config, registry=None):
    """Offline load-time validation.

    Pure playbook-internal analysis. Walks every ``${artifact.field}`` in every
    enabled step and checks that some earlier enabled step declares
    ``output: <artifact>``; checks each declared required parameter is present.
    Performs no authentication, no HTTP, and no file writes.

    Returns a list of human-readable error strings; empty means valid.
    """
    registry = registry or {}
    errors = []

    for playbook in config.get('playbooks', []) or []:
        techniques = playbook.get('techniques', []) or []
        enabled = [t for t in techniques if t.get('enabled', False)]

        # First pass: which step number produces each named artifact.
        produced = {}
        for step_no, tech in enumerate(enabled, start=1):
            output_name = tech.get('output')
            if output_name:
                produced[output_name] = step_no

        for step_no, tech in enumerate(enabled, start=1):
            name = tech.get('technique', '<unknown>')
            params = tech.get('parameters', {}) or {}

            for key, value in params.items():
                try:
                    ref = parse_reference(value)
                except ReferenceError as exc:
                    errors.append(f"Step {step_no} ({name}), parameter '{key}': {exc}")
                    continue
                if ref is None:
                    continue

                art_name, _fields = ref
                if art_name not in produced:
                    earlier = [n for n, s in produced.items() if s < step_no]
                    errors.append(
                        f"Step {step_no} ({name}), parameter '{key}': references "
                        f"artifact '{art_name}', which no enabled step produces\n"
                        f"    available at this point: {', '.join(earlier) or '(none)'}"
                    )
                elif produced[art_name] >= step_no:
                    errors.append(
                        f"Step {step_no} ({name}), parameter '{key}': references "
                        f"artifact '{art_name}', which is produced later, by step "
                        f"{produced[art_name]}"
                    )

            contract = registry.get(name)
            if contract:
                required = contract.get('requires', [])
                for req in required:
                    if req not in params:
                        errors.append(
                            f"Step {step_no} ({name}) is missing required "
                            f"parameter: {req}\n    requires: {', '.join(required)}"
                        )

    return errors
