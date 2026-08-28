"""Offline unit tests for the technique-chaining engine.

Run:  python -m unittest discover -s tests
   or python tests/test_engine.py

No tenant, no network, no msInvader import beyond src.engine.
"""

import json
import logging
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.engine import (  # noqa: E402
    ReferenceError,
    RunContext,
    parse_reference,
    resolve_params,
    validate_playbook,
)


class TestReferenceGrammar(unittest.TestCase):
    """Literals stay literals; malformed references raise instead of passing through."""

    # A plain literal: parse_reference returns None, never raises.
    LITERALS = [
        "device_creds.key_path",        # bare dotted form - no ${, so a literal
        "msinvader-test.key",           # literal file path (the reference point)
        "device_creds['key_path']",     # bracket form - no ${
        "{device_creds.key_path}",      # single brace, no $
        "/abs/path/to/token.json",
        "plain string value",
        "",
    ]

    # Contains ${ but is not a full, valid reference: MUST raise, never literal.
    MALFORMED = [
        "${device_creds}",              # no field segment (no shorthand in v1)
        "${device_creds.key_path",      # missing closing brace
        "pre-${device_creds.key_path}", # surrounding text (prefix)
        "${device_creds.key_path} tail",# surrounding text (suffix)
        "${ device_creds.key_path }",   # internal whitespace
        "${device_creds..key_path}",    # empty field segment
        "${.key_path}",                 # missing artifact name
        "${}",
        "${1abc.field}",                # artifact name may not start with a digit
    ]

    VALID = {
        "${a.b}": ("a", ["b"]),
        "${victim1.access_token}": ("victim1", ["access_token"]),
        "${graph_result.value.id}": ("graph_result", ["value", "id"]),
        "${evil_app.app_id}": ("evil_app", ["app_id"]),
        "${drs-token.refresh_token}": ("drs-token", ["refresh_token"]),
    }

    def test_literals_are_not_references(self):
        for value in self.LITERALS:
            with self.subTest(value=value):
                self.assertIsNone(parse_reference(value))

    def test_non_strings_are_not_references(self):
        for value in (5, True, False, None, 3.14, ["${a.b}"], {"k": "v"}):
            with self.subTest(value=value):
                self.assertIsNone(parse_reference(value))

    def test_malformed_references_raise_not_pass_through(self):
        for value in self.MALFORMED:
            with self.subTest(value=value):
                with self.assertRaises(ReferenceError):
                    parse_reference(value)

    def test_valid_references_parse(self):
        for value, expected in self.VALID.items():
            with self.subTest(value=value):
                self.assertEqual(parse_reference(value), expected)


class TestResolveParams(unittest.TestCase):

    def test_literal_passthrough_and_no_provenance(self):
        ctx = RunContext()
        params = {"key_path": "msinvader-test.key", "limit": 5, "enabled": True}
        resolved, provenance = resolve_params(params, ctx)
        self.assertEqual(resolved, params)
        self.assertEqual(provenance, {})

    def test_reference_resolution_records_provenance(self):
        ctx = RunContext()
        ctx.put("victim1", {"access_token": "eyJ0.aaa", "refresh_token": "0.rrr"})
        params = {
            "access_token": "${victim1.access_token}",
            "mailbox": "ceo@contoso.onmicrosoft.com",
        }
        resolved, provenance = resolve_params(params, ctx)
        self.assertEqual(resolved["access_token"], "eyJ0.aaa")
        self.assertEqual(resolved["mailbox"], "ceo@contoso.onmicrosoft.com")
        self.assertEqual(provenance, {"access_token": "victim1"})

    def test_nested_path_walks(self):
        ctx = RunContext()
        ctx.put("graph_result", {"value": {"id": "user-123", "mail": "a@b.c"}})
        resolved, _ = resolve_params({"uid": "${graph_result.value.id}"}, ctx)
        self.assertEqual(resolved["uid"], "user-123")

    def test_unknown_artifact_raises_with_available_list(self):
        ctx = RunContext()
        ctx.put("victim1", {"access_token": "x"})
        with self.assertRaises(ReferenceError) as caught:
            resolve_params({"t": "${evil_app.app_id}"}, ctx)
        self.assertIn("evil_app", str(caught.exception))
        self.assertIn("victim1", str(caught.exception))

    def test_unknown_field_raises_with_fields_and_hint(self):
        ctx = RunContext()
        ctx.put("victim1", {"access_token": "x", "refresh_token": "y"})
        with self.assertRaises(ReferenceError) as caught:
            resolve_params({"t": "${victim1.acces_token}"}, ctx)
        message = str(caught.exception)
        self.assertIn("no field 'acces_token'", message)
        self.assertIn("access_token", message)
        self.assertIn("did you mean 'access_token'?", message)

    def test_walk_into_non_mapping_raises(self):
        ctx = RunContext()
        ctx.put("victim1", {"access_token": "x"})
        with self.assertRaises(ReferenceError) as caught:
            resolve_params({"t": "${victim1.access_token.inner}"}, ctx)
        self.assertIn("not a mapping", str(caught.exception))

    def test_malformed_reference_in_params_raises(self):
        ctx = RunContext()
        with self.assertRaises(ReferenceError):
            resolve_params({"key_path": "${device_creds}"}, ctx)


class TestRunContext(unittest.TestCase):

    def test_in_memory_put_get_round_trip(self):
        ctx = RunContext()
        artifact = {"app_id": "abc", "object_id": "def"}
        ctx.put("evil_app", artifact)
        self.assertEqual(ctx.get("evil_app"), artifact)

    def test_get_missing_returns_none(self):
        self.assertIsNone(RunContext().get("nope"))

    def test_put_logs_field_names_not_values(self):
        ctx = RunContext()
        with self.assertLogs(level=logging.INFO) as logs:
            ctx.put("cred", {"secret": "S3CR3T-do-not-log", "key_id": "k1"})
        blob = "\n".join(logs.output)
        self.assertIn("stored artifact 'cred' with fields: secret, key_id", blob)
        self.assertNotIn("S3CR3T-do-not-log", blob)

    def test_save_to_disk_writes_named_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "token_out.json")
            ctx = RunContext()
            ctx.put("tok", {"access_token": "eyJ0"}, save_to_disk=target)
            self.assertTrue(os.path.isfile(target))
            with open(target) as handle:
                self.assertEqual(json.load(handle), {"access_token": "eyJ0"})

    def test_artifact_dir_round_trip_across_contexts(self):
        with tempfile.TemporaryDirectory() as tmp:
            writer = RunContext(artifact_dir=tmp)
            writer.put("drs_token", {"refresh_token": "0.rrr", "flow": "device_code"})
            self.assertTrue(os.path.isfile(os.path.join(tmp, "drs_token.json")))

            reader = RunContext(artifact_dir=tmp)
            self.assertEqual(
                reader.get("drs_token"),
                {"refresh_token": "0.rrr", "flow": "device_code"},
            )

    def test_disk_fallback_is_logged_with_mtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            RunContext(artifact_dir=tmp).put("device_creds", {"key_path": "k"})
            reader = RunContext(artifact_dir=tmp)
            with self.assertLogs(level=logging.INFO) as logs:
                reader.get("device_creds")
            blob = "\n".join(logs.output)
            self.assertIn("disk fallback", blob)
            self.assertIn("modified", blob)

    def test_in_memory_shadows_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            RunContext(artifact_dir=tmp).put("a", {"v": "on-disk"})
            ctx = RunContext(artifact_dir=tmp)
            ctx.put("a", {"v": "in-memory"})
            self.assertEqual(ctx.get("a"), {"v": "in-memory"})

    def test_names_merges_memory_and_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            RunContext(artifact_dir=tmp).put("on_disk", {"x": 1})
            ctx = RunContext(artifact_dir=tmp)
            ctx.put("in_mem", {"y": 2})
            self.assertEqual(ctx.names(), ["in_mem", "on_disk"])


class TestValidatePlaybook(unittest.TestCase):

    @staticmethod
    def _pb(techniques):
        return {"playbooks": [{"name": "t", "techniques": techniques}]}

    def test_clean_chained_playbook_passes(self):
        config = self._pb([
            {"technique": "device_code_auth", "enabled": True, "output": "victim1",
             "parameters": {"username": "u@x"}},
            {"technique": "read_email", "enabled": True,
             "parameters": {"access_token": "${victim1.access_token}", "mailbox": "u@x"}},
        ])
        self.assertEqual(validate_playbook(config), [])

    def test_typoed_artifact_name_is_flagged(self):
        config = self._pb([
            {"technique": "device_code_auth", "enabled": True, "output": "victim1",
             "parameters": {}},
            {"technique": "read_email", "enabled": True,
             "parameters": {"access_token": "${victi1.access_token}"}},  # typo
        ])
        errors = validate_playbook(config)
        self.assertEqual(len(errors), 1)
        self.assertIn("no enabled step produces", errors[0])
        self.assertIn("victi1", errors[0])

    def test_forward_reference_is_flagged(self):
        config = self._pb([
            {"technique": "read_email", "enabled": True,
             "parameters": {"access_token": "${app_token.access_token}"}},
            {"technique": "client_credentials_auth", "enabled": True, "output": "app_token",
             "parameters": {}},
        ])
        errors = validate_playbook(config)
        self.assertEqual(len(errors), 1)
        self.assertIn("produced later, by step 2", errors[0])

    def test_reference_to_disabled_producer_is_flagged(self):
        config = self._pb([
            {"technique": "device_code_auth", "enabled": False, "output": "victim1",
             "parameters": {}},
            {"technique": "read_email", "enabled": True,
             "parameters": {"access_token": "${victim1.access_token}"}},
        ])
        errors = validate_playbook(config)
        self.assertEqual(len(errors), 1)
        self.assertIn("no enabled step produces", errors[0])

    def test_malformed_reference_is_flagged(self):
        config = self._pb([
            {"technique": "get_prt_with_refresh_token", "enabled": True,
             "parameters": {"key_path": "${device_creds}"}},
        ])
        errors = validate_playbook(config)
        self.assertEqual(len(errors), 1)
        self.assertIn("malformed reference", errors[0])

    def test_missing_required_parameter_is_flagged(self):
        registry = {
            "get_prt_with_refresh_token": {
                "requires": ["refresh_token", "key_path", "cert_path"],
            },
        }
        config = self._pb([
            {"technique": "get_prt_with_refresh_token", "enabled": True,
             "parameters": {"refresh_token": "x", "key_path": "k"}},
        ])
        errors = validate_playbook(config, registry)
        self.assertEqual(len(errors), 1)
        self.assertIn("missing required parameter: cert_path", errors[0])

    def test_unknown_technique_without_contract_is_not_flagged(self):
        # An absent registry contract means no required-parameter check.
        config = self._pb([
            {"technique": "read_email", "enabled": True, "parameters": {}},
        ])
        self.assertEqual(validate_playbook(config, {}), [])

    def test_session_model_playbook_has_no_references_to_validate(self):
        config = self._pb([
            {"technique": "read_email", "enabled": True,
             "parameters": {"session": "victim1", "access_method": "graph",
                            "mailbox": "victim1@contoso.onmicrosoft.com", "limit": 5}},
        ])
        self.assertEqual(validate_playbook(config), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
