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
    OutputStore,
    PlaybookError,
    resolve_references,
    validate_playbook,
)


class TestResolveReferences(unittest.TestCase):

    def test_literal_passthrough_and_no_sources(self):
        outputs = OutputStore()
        params = {"key_path": "msinvader-test.key", "limit": 5, "enabled": True}
        resolved, sources = resolve_references(params, outputs)
        self.assertEqual(resolved, params)
        self.assertEqual(sources, {})

    def test_reference_resolution_records_its_source(self):
        outputs = OutputStore()
        outputs.save("victim1", {"access_token": "eyJ0.aaa", "refresh_token": "0.rrr"})
        params = {
            "access_token": "${victim1.access_token}",
            "mailbox": "ceo@contoso.onmicrosoft.com",
        }
        resolved, sources = resolve_references(params, outputs)
        self.assertEqual(resolved["access_token"], "eyJ0.aaa")
        self.assertEqual(resolved["mailbox"], "ceo@contoso.onmicrosoft.com")
        self.assertEqual(sources, {"access_token": "victim1"})

    def test_unknown_output_raises_with_available_list(self):
        outputs = OutputStore()
        outputs.save("victim1", {"access_token": "x"})
        with self.assertRaises(PlaybookError) as caught:
            resolve_references({"t": "${evil_app.app_id}"}, outputs)
        self.assertIn("evil_app", str(caught.exception))
        self.assertIn("victim1", str(caught.exception))

    def test_unknown_field_raises_with_available_fields(self):
        outputs = OutputStore()
        outputs.save("victim1", {"access_token": "x", "refresh_token": "y"})
        with self.assertRaises(PlaybookError) as caught:
            resolve_references({"t": "${victim1.acces_token}"}, outputs)
        message = str(caught.exception)
        self.assertIn("no field 'acces_token'", message)
        self.assertIn("access_token", message)

    def test_malformed_reference_raises_not_pass_through(self):
        # Contains ${ but is not a full ${output.field}: must raise, never be
        # treated as a literal filename.
        outputs = OutputStore()
        for value in ("${device_creds}", "${device_creds.key_path",
                      "pre-${device_creds.key_path}", "${ device_creds.key_path }"):
            with self.subTest(value=value):
                with self.assertRaises(PlaybookError):
                    resolve_references({"key_path": value}, outputs)

    def test_narrates_where_each_value_came_from(self):
        outputs = OutputStore()
        outputs.save("device_creds", {"key_path": "k", "cert_path": "c"})
        with self.assertLogs(level=logging.INFO) as logs:
            resolve_references(
                {"key_path": "${device_creds.key_path}",
                 "cert_path": "${device_creds.cert_path}"},
                outputs, step="Step 4 (get_prt_with_refresh_token)")
        blob = "\n".join(logs.output)
        self.assertIn("Step 4 (get_prt_with_refresh_token): using", blob)
        self.assertIn("key_path and cert_path from 'device_creds'", blob)


class TestOutputStore(unittest.TestCase):

    def test_in_memory_save_get_round_trip(self):
        store = OutputStore()
        output = {"app_id": "abc", "object_id": "def"}
        store.save("evil_app", output)
        self.assertEqual(store.get("evil_app"), output)

    def test_get_missing_returns_none(self):
        self.assertIsNone(OutputStore().get("nope"))

    def test_save_logs_field_names_not_values(self):
        store = OutputStore()
        with self.assertLogs(level=logging.INFO) as logs:
            store.save("cred", {"secret": "S3CR3T-do-not-log", "key_id": "k1"})
        blob = "\n".join(logs.output)
        self.assertIn("saved output 'cred' with fields: secret, key_id", blob)
        self.assertNotIn("S3CR3T-do-not-log", blob)

    def test_save_to_disk_writes_named_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "token_out.json")
            store = OutputStore()
            store.save("tok", {"access_token": "eyJ0"}, save_to_disk=target)
            self.assertTrue(os.path.isfile(target))
            with open(target) as handle:
                self.assertEqual(json.load(handle), {"access_token": "eyJ0"})

    def test_artifact_dir_round_trip_across_stores(self):
        with tempfile.TemporaryDirectory() as tmp:
            writer = OutputStore(artifact_dir=tmp)
            writer.save("drs_token", {"refresh_token": "0.rrr", "flow": "device_code"})
            self.assertTrue(os.path.isfile(os.path.join(tmp, "drs_token.json")))

            reader = OutputStore(artifact_dir=tmp)
            self.assertEqual(
                reader.get("drs_token"),
                {"refresh_token": "0.rrr", "flow": "device_code"},
            )

    def test_disk_fallback_is_logged_with_mtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            OutputStore(artifact_dir=tmp).save("device_creds", {"key_path": "k"})
            reader = OutputStore(artifact_dir=tmp)
            with self.assertLogs(level=logging.INFO) as logs:
                reader.get("device_creds")
            blob = "\n".join(logs.output)
            self.assertIn("disk fallback", blob)
            self.assertIn("modified", blob)

    def test_in_memory_shadows_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            OutputStore(artifact_dir=tmp).save("a", {"v": "on-disk"})
            store = OutputStore(artifact_dir=tmp)
            store.save("a", {"v": "in-memory"})
            self.assertEqual(store.get("a"), {"v": "in-memory"})

    def test_names_merges_memory_and_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            OutputStore(artifact_dir=tmp).save("on_disk", {"x": 1})
            store = OutputStore(artifact_dir=tmp)
            store.save("in_mem", {"y": 2})
            self.assertEqual(store.names(), ["in_mem", "on_disk"])

    def test_minted_token_is_kept_out_of_the_saved_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = OutputStore(artifact_dir=tmp)
            store.save("victim1", {"access_token": "AT", "refresh_token": "RT",
                                   "tenant_id": "t", "client_id": "c", "scope": "graph"})
            store.save_minted_token("victim1", "ews", "EWS_AT")

            self.assertEqual(store.minted_token("victim1", "ews"), "EWS_AT")
            with open(os.path.join(tmp, "victim1.json")) as handle:
                on_disk = json.load(handle)
            self.assertEqual(set(on_disk),
                             {"access_token", "refresh_token", "tenant_id",
                              "client_id", "scope"})
            self.assertNotIn("minted", on_disk)
            self.assertNotIn("_scoped_tokens", on_disk)


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

    def test_typoed_output_name_is_flagged(self):
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

    def test_playbook_with_only_literals_has_no_references_to_validate(self):
        config = self._pb([
            {"technique": "read_email", "enabled": True,
             "parameters": {"access_token": "pasted-token", "access_method": "graph",
                            "mailbox": "victim1@contoso.onmicrosoft.com", "limit": 5}},
        ])
        self.assertEqual(validate_playbook(config), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
