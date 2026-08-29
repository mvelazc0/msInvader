"""Passing values from one technique to the next.

A step can name what it produced, and a later step can point at it:

    - technique: "register_device"
      output: device_creds                    # -> device_id, key_path, cert_path

    - technique: "get_prt_with_refresh_token"
      parameters:
        key_path:  ${device_creds.key_path}
        cert_path: ${device_creds.cert_path}

This is how an attack chains in practice: register a device, then use that
device's certificate to request a Primary Refresh Token. This module resolves
those ${...} references and keeps each step's output for later steps to use;
src/auth_techniques.py picks the access token for the API a technique calls.
"""

import json
import logging
import os
import re
from datetime import datetime

# ${output_name.field} - one output name, one field, and the reference must be
# the whole value with nothing around it. Deeper paths (${a.b.c}) are not
# supported; no shipped playbook needs one, and adding them back is a one-line
# change the day a technique returns a nested dict.
REFERENCE = re.compile(r'^\$\{([A-Za-z_][\w-]*)\.([A-Za-z_][\w-]*)\}$')


class PlaybookError(Exception):
    """A playbook cannot be run as written: a broken ${...} reference, a
    reference to an output no step produces, or a refresh token that could not
    be redeemed for the audience a step needs."""


def _prefix(step):
    """'Step 4 (read_email): ' from a step label, or '' when there is none."""
    return f"{step}: " if step else ""


def _and_list(items):
    """['a'] -> 'a';  ['a', 'b'] -> 'a and b';  ['a', 'b', 'c'] -> 'a, b and c'."""
    items = list(items)
    if len(items) <= 1:
        return items[0] if items else ""
    return f"{', '.join(items[:-1])} and {items[-1]}"


def looks_like_reference(value):
    """True when *value* is a ${...} reference and not a plain literal. A string
    that contains ${ but is malformed still counts, so the caller rejects it
    rather than falling back to treating it as a literal."""
    return isinstance(value, str) and '${' in value


def resolve_references(parameters, outputs, step=""):
    """Replace every ${output.field} in *parameters* with the value it points at.

    Returns ``(resolved, sources)``: *resolved* is *parameters* with references
    substituted, *sources* maps a parameter name to the output it came from so a
    later step can be told where its token originated. Literals pass straight
    through and do not appear in *sources*.
    """
    resolved = {}
    sources = {}
    logging.debug(f"{_prefix(step)}resolving {len(parameters)} parameter(s)")

    for name, value in parameters.items():
        if not looks_like_reference(value):
            resolved[name] = value
            continue

        match = REFERENCE.fullmatch(value)
        if not match:
            # A broken reference must not be passed on as a literal: that turns
            # "${device_creds.key_path}" into a filename and reports a missing
            # file instead of the missing step it really is.
            raise PlaybookError(f"{_prefix(step)}parameter '{name}': bad reference "
                                f"{value!r}, expected ${{output.field}}")

        output_name, field = match.group(1), match.group(2)
        output = outputs.get(output_name)
        if not isinstance(output, dict):
            raise PlaybookError(
                f"{_prefix(step)}parameter '{name}': no output named '{output_name}' "
                f"(available: {', '.join(outputs.names()) or 'none'})")
        if field not in output:
            raise PlaybookError(
                f"{_prefix(step)}parameter '{name}': output '{output_name}' has no "
                f"field '{field}' (it has: {', '.join(output) or 'none'})")

        resolved[name] = output[field]
        sources[name] = output_name
        logging.debug(f"{_prefix(step)}parameter '{name}' <- {output_name}.{field}")

    if sources:
        by_output = {}
        for param, output_name in sources.items():
            by_output.setdefault(output_name, []).append(param)
        summary = ', '.join(f"{_and_list(names)} from '{output_name}'"
                            for output_name, names in by_output.items())
        logging.info(f"{_prefix(step)}using {summary}")

    return resolved, sources


class OutputStore:
    """Every step's output, kept for the rest of the run so later steps can point
    at it.

    Given a run directory, each output is also written there as ``<name>.json``
    and read back from there when a name is not in memory, so a long chain can
    be resumed partway through. Tokens minted mid-run are held separately, not
    folded into the output dict, so a saved ``<name>.json`` stays exactly what
    the technique returned.
    """

    # The keyword argument's name is the one published on the CLI flag.
    def __init__(self, artifact_dir=None):
        self._outputs = {}
        self._minted = {}
        self._dir = artifact_dir
        if self._dir:
            logging.info(f"outputs will be written to {self._dir}/ and read back "
                         f"from there when not in memory")

    def get(self, name):
        """Look up an earlier step's output by name: memory first, then disk."""
        if name in self._outputs:
            logging.debug(f"output '{name}' taken from memory")
            return self._outputs[name]
        return self._load_from_disk(name)

    def _load_from_disk(self, name):
        """Fall back to ``<run-dir>/<name>.json`` so a partial run can be
        resumed. Sharp edge: a stale directory hands back an expired token and
        the run then fails as though the technique were broken, so the file's
        timestamp is logged.
        """
        if not self._dir:
            return None
        path = os.path.join(self._dir, f"{name}.json")
        if not os.path.isfile(path):
            logging.debug(f"output '{name}' is not in memory and not at {path}")
            return None

        modified = datetime.fromtimestamp(
            os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M:%S')
        with open(path, 'r') as handle:
            output = json.load(handle)
        logging.info(f"output '{name}' read from the disk fallback {path} "
                     f"(modified {modified}) - a stale file hands back an expired token")
        return output

    def save(self, name, output, save_to_disk=None, step=""):
        """Keep *output* under *name*, and write it out if a destination is set.
        Only field names are logged, never values: an output holds live access
        tokens, refresh tokens and device secrets."""
        self._outputs[name] = output

        if isinstance(output, dict):
            fields = ', '.join(output) or '(none)'
        else:
            fields = f"(not a dict: {type(output).__name__})"
            logging.warning(f"{_prefix(step)}output '{name}' is not a dict; later "
                            f"steps cannot reference a field of it")
        logging.info(f"{_prefix(step)}saved output '{name}' with fields: {fields}")

        for path in self._destinations(name, save_to_disk):
            with open(path, 'w') as handle:
                json.dump(output, handle, indent=2)
            logging.info(f"{_prefix(step)}wrote output '{name}' to {path}")

    def _destinations(self, name, save_to_disk):
        """Where ``save`` writes *name*: the step's own ``save_to_disk:`` target,
        then the run-wide output directory."""
        paths = []
        if save_to_disk:
            paths.append(save_to_disk)
        if self._dir:
            os.makedirs(self._dir, exist_ok=True)
            paths.append(os.path.join(self._dir, f"{name}.json"))
        return paths

    def names(self):
        """Every output name available now - in memory and on disk."""
        found = set(self._outputs)
        if self._dir and os.path.isdir(self._dir):
            for entry in os.listdir(self._dir):
                if entry.endswith('.json'):
                    found.add(entry[:-len('.json')])
        logging.debug(f"outputs available: {', '.join(sorted(found)) or 'none'}")
        return sorted(found)

    def minted_token(self, output_name, scope):
        """A token this run already redeemed from *output_name* for *scope*, or None."""
        token = self._minted.get((output_name, scope))
        if token:
            logging.debug(f"have a cached {scope} token from '{output_name}'")
        return token

    def save_minted_token(self, output_name, scope, token):
        """Remember a token redeemed mid-run, held apart from the output dict so
        the saved JSON stays exactly what the technique returned."""
        self._minted[(output_name, scope)] = token
        logging.debug(f"cached the {scope} token minted from '{output_name}'")


def validate_playbook(config, registry=None):
    """Check a playbook without running it: no authentication, no API calls, no writes.

    Returns a list of human-readable errors. Empty means the playbook is valid.
    """
    registry = registry or {}
    errors = []
    for playbook in config.get('playbooks', []) or []:
        techniques = playbook.get('techniques', []) or []
        steps = [t for t in techniques if t.get('enabled', False)]
        logging.debug(f"validating {len(steps)} enabled step(s) in "
                      f"'{playbook.get('name', 'unnamed playbook')}'")
        errors += check_references(steps)
        errors += check_required_parameters(steps, registry)
    logging.debug(f"playbook validation found {len(errors)} problem(s)")
    return errors


def check_references(steps):
    """Every ${output.field} must point at an earlier enabled step's output."""
    produced = {}
    for number, step in enumerate(steps, start=1):
        name = step.get('output')
        if name and name not in produced:
            produced[name] = number
    logging.debug(f"outputs this playbook produces: {', '.join(produced) or 'none'}")

    errors = []
    for number, step in enumerate(steps, start=1):
        technique = step.get('technique', '<unknown>')
        for parameter, value in (step.get('parameters') or {}).items():
            if not looks_like_reference(value):
                continue
            label = f"Step {number} ({technique}), parameter '{parameter}'"

            match = REFERENCE.fullmatch(value)
            if not match:
                errors.append(f"{label}: malformed reference {value!r}, "
                              f"expected ${{output.field}}")
                continue

            referenced = match.group(1)
            producer = produced.get(referenced)
            if producer is None:
                earlier = [n for n, s in produced.items() if s < number]
                errors.append(f"{label}: references output '{referenced}', which no "
                              f"enabled step produces (available here: "
                              f"{', '.join(earlier) or 'none'})")
            elif producer >= number:
                errors.append(f"{label}: references output '{referenced}', which is "
                              f"produced later, by step {producer}")
    return errors


def check_required_parameters(steps, registry):
    """Every parameter a technique cannot run without must be present."""
    errors = []
    for number, step in enumerate(steps, start=1):
        technique = step.get('technique', '<unknown>')
        spec = registry.get(technique)
        if not spec:
            continue
        parameters = step.get('parameters') or {}
        required = spec.get('requires', [])
        logging.debug(f"Step {number} ({technique}) needs: {', '.join(required) or 'nothing'}")
        for name in required:
            if name not in parameters:
                errors.append(f"Step {number} ({technique}) is missing required "
                              f"parameter: {name} (requires: {', '.join(required)})")
    return errors
