"""Offline checks for the converted device-registration / PRT / WHFB chain.

The techniques themselves make live HTTP calls, so these tests cover only the
parts that are reachable without a tenant: input validation, the absence of
token-file I/O, the rewritten config2.yml, and resolving a late step's inputs
from an artifact directory captured by an earlier run.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml  # noqa: E402

from src import device_client as dc  # noqa: E402
from src.engine import RunContext, resolve_params, validate_playbook  # noqa: E402
from src.registry import TECHNIQUES  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestNoTokenFileIO(unittest.TestCase):
    """Converted techniques take resolved values; they never open a token file."""

    def test_device_client_source_has_no_token_file_params(self):
        with open(os.path.join(REPO, "src", "device_client.py")) as handle:
            body = handle.read()
        for needle in ("prt_file", "token_out", 'params.get("prt_out"', "whfb_key_file"):
            self.assertNotIn(needle, body, needle)
        self.assertNotIn("json.load(", body)  # json.loads on HTTP bodies is fine

    def test_get_token_with_prt_requires_prt_and_session_key(self):
        self.assertIsNone(dc.get_token_with_prt({
            "client_id": "c", "resource": "r",  # no prt / session_key
        }))

    def test_get_token_with_prt_rejects_bad_session_key_without_touching_disk(self):
        self.assertIsNone(dc.get_token_with_prt({
            "prt": "PRT", "session_key": "not-base64!!!",
            "client_id": "c", "resource": "r",
        }))

    def test_create_whfb_key_needs_only_access_token_now(self):
        # The old "session parameter is required" gate is gone.
        self.assertIsNone(dc.create_whfb_key({}))  # missing access_token -> None, no crash

    def test_get_prt_with_refresh_token_requires_key_and_cert_paths(self):
        self.assertIsNone(dc.get_prt_with_refresh_token({"refresh_token": "rt"}))

    def test_get_prt_with_whfb_key_uses_new_param_name(self):
        # All required params missing -> None; and the function reads whfb_key_path.
        self.assertIsNone(dc.get_prt_with_whfb_key({"key_path": "k", "cert_path": "c",
                                                    "username": "u"}))


class TestRewrittenConfig2(unittest.TestCase):

    def setUp(self):
        path = os.path.join(REPO, "config2.yml")
        if not os.path.exists(path):
            self.skipTest("config2.yml not present (untracked)")
        with open(path) as handle:
            self.config = yaml.safe_load(handle)

    def test_validates_clean(self):
        self.assertEqual(validate_playbook(self.config, TECHNIQUES), [])

    def test_no_session_block_and_no_file_params(self):
        self.assertNotIn("sessions", self.config["authentication"])
        raw = yaml.dump(self.config)
        for needle in ("_file:", "token_out", "prt_out", "session:"):
            self.assertNotIn(needle, raw)

    def test_every_step_wires_by_reference_or_literal_only(self):
        steps = self.config["playbooks"][0]["techniques"]
        for step in steps:
            self.assertIn("output", step)


class TestStandaloneResumeFromArtifactDir(unittest.TestCase):
    """A late get_token_with_prt step resolves from a captured artifact dir with
    every preceding step disabled - no playbook edit."""

    def test_last_step_inputs_resolve_from_disk(self):
        path = os.path.join(REPO, "config2.yml")
        if not os.path.exists(path):
            self.skipTest("config2.yml not present (untracked)")
        with open(path) as handle:
            steps = yaml.safe_load(handle)["playbooks"][0]["techniques"]
        last = steps[-1]
        self.assertEqual(last["technique"], "get_token_with_prt")

        with tempfile.TemporaryDirectory() as run_dir:
            with open(os.path.join(run_dir, "whfb_prt.json"), "w") as handle:
                json.dump({"refresh_token": "PRT-VALUE", "session_key": "U0VTU0lPTg=="},
                          handle)
            ctx = RunContext(artifact_dir=run_dir)
            resolved, provenance = resolve_params(last["parameters"], ctx)

        self.assertEqual(resolved["prt"], "PRT-VALUE")
        self.assertEqual(resolved["session_key"], "U0VTU0lPTg==")
        self.assertEqual(provenance, {"prt": "whfb_prt", "session_key": "whfb_prt"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
