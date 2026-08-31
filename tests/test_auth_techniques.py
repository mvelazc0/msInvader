"""Offline unit tests for the authentication technique wrappers.

The transport functions in src.auth are patched out; nothing here touches the
network. Run:  python -m unittest discover -s tests
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import auth_techniques as at  # noqa: E402
from src.engine import validate_playbook  # noqa: E402
from src.registry import TECHNIQUES  # noqa: E402

AUTH_CONFIG = {"tenant_id": "tenant-from-config"}


class TestDefaults(unittest.TestCase):
    """The promoted defaults must match the values hardcoded in src.auth."""

    def test_default_client_id_is_the_one_hardcoded_in_src_auth(self):
        self.assertEqual(at.DEFAULT_CLIENT_ID, "d3590ed6-52b3-4102-aeff-aad2292ab01c")
        auth_src = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "auth.py"
        )
        with open(auth_src) as handle:
            body = handle.read()
        # Present in get_ms_token_username_pass and get_ms_token_device_code.
        self.assertGreaterEqual(body.count(at.DEFAULT_CLIENT_ID), 2)


class TestPasswordAuth(unittest.TestCase):

    def test_builds_resource_owner_artifact(self):
        with mock.patch.object(at, "get_ms_token_username_pass",
                               return_value={"access_token": "AT", "refresh_token": "RT"}) as fn:
            artifact = at.password_auth(AUTH_CONFIG, {
                "username": "u@x", "password": "p", "scope": "graph/.default",
            })
        fn.assert_called_once_with("tenant-from-config", "u@x", "p", "graph/.default")
        self.assertEqual(artifact, {
            "access_token": "AT", "refresh_token": "RT",
            "tenant_id": "tenant-from-config",
            "client_id": at.DEFAULT_CLIENT_ID,
            "scope": "graph/.default", "flow": "resource_owner",
        })

    def test_param_tenant_id_overrides_config(self):
        with mock.patch.object(at, "get_ms_token_username_pass",
                               return_value={"access_token": "AT", "refresh_token": "RT"}):
            artifact = at.password_auth(AUTH_CONFIG, {
                "tenant_id": "tenant-from-step",
                "username": "u@x", "password": "p", "scope": "s",
            })
        self.assertEqual(artifact["tenant_id"], "tenant-from-step")

    def test_custom_client_id_rejected(self):
        with self.assertRaises(ValueError):
            at.password_auth(AUTH_CONFIG, {
                "username": "u", "password": "p", "scope": "s",
                "client_id": "11111111-1111-1111-1111-111111111111",
            })

    def test_resource_param_rejected(self):
        with self.assertRaises(ValueError):
            at.password_auth(AUTH_CONFIG, {
                "username": "u", "password": "p", "resource": "https://graph.microsoft.com",
            })

    def test_failed_flow_returns_none(self):
        with mock.patch.object(at, "get_ms_token_username_pass", return_value=None):
            self.assertIsNone(at.password_auth(AUTH_CONFIG, {
                "username": "u", "password": "p", "scope": "s",
            }))


class TestDeviceCodeAuth(unittest.TestCase):

    def test_v2_path_passes_default_client_id_and_flow(self):
        with mock.patch.object(at, "get_ms_token_device_code",
                               return_value={"access_token": "AT", "refresh_token": "RT"}) as fn:
            artifact = at.device_code_auth(AUTH_CONFIG, {
                "username": "u@x", "scope": "s", "require_ngcmfa": False,
            })
        fn.assert_called_once_with("tenant-from-config", "u@x", "s", at.DEFAULT_CLIENT_ID, False)
        self.assertEqual(artifact["flow"], "device_code")
        self.assertEqual(artifact["client_id"], at.DEFAULT_CLIENT_ID)

    def test_v1_endpoint_routes_to_v1_helper_with_amr(self):
        with mock.patch.object(at, "get_ms_token_device_code_v1",
                               return_value={"access_token": "AT", "refresh_token": "RT"}) as fn_v1, \
             mock.patch.object(at, "get_ms_token_device_code") as fn_v2:
            at.device_code_auth(AUTH_CONFIG, {
                "username": "u@x", "scope": "s",
                "use_v1_endpoint": True, "require_ngcmfa": True,
            })
        fn_v2.assert_not_called()
        fn_v1.assert_called_once_with(
            "tenant-from-config", "u@x", "s", at.DEFAULT_CLIENT_ID, use_amr_values=True
        )

    def test_explicit_client_id_threaded_through(self):
        with mock.patch.object(at, "get_ms_token_device_code",
                               return_value={"access_token": "AT", "refresh_token": "RT"}) as fn:
            at.device_code_auth(AUTH_CONFIG, {
                "username": "u@x", "scope": "s",
                "client_id": "29d9ed98-a469-4536-ade2-f981bc1d605e",
            })
        self.assertEqual(fn.call_args[0][3], "29d9ed98-a469-4536-ade2-f981bc1d605e")


class TestClientCredentialsAuth(unittest.TestCase):

    def test_threads_client_id_secret_scope_and_sets_flow(self):
        with mock.patch.object(at, "get_ms_token_client",
                               return_value={"access_token": "AT", "refresh_token": False}) as fn:
            artifact = at.client_credentials_auth(AUTH_CONFIG, {
                "client_id": "app-id", "client_secret": "sh", "scope": "graph/.default",
            })
        fn.assert_called_once_with("tenant-from-config", "app-id", "sh", "graph/.default")
        self.assertEqual(artifact["flow"], "client_credentials")
        self.assertEqual(artifact["client_id"], "app-id")
        self.assertIs(artifact["refresh_token"], False)


class TestRefreshTokenAuth(unittest.TestCase):

    def test_v2_scope_path(self):
        with mock.patch.object(at, "get_token_with_refresh_token",
                               return_value={"access_token": "AT2", "refresh_token": "RT2"}) as fn:
            artifact = at.refresh_token_auth(AUTH_CONFIG, {
                "refresh_token": "RT", "scope": "outlook/.default",
            })
        fn.assert_called_once_with(
            "tenant-from-config", "RT",
            scope="outlook/.default", resource=None, client_id=at.DEFAULT_CLIENT_ID,
        )
        self.assertEqual(artifact["flow"], "refresh_token")
        self.assertEqual(artifact["scope"], "outlook/.default")
        self.assertNotIn("resource", artifact)

    def test_v1_resource_path_records_resource_field(self):
        with mock.patch.object(at, "get_token_with_refresh_token",
                               return_value={"access_token": "AT2", "refresh_token": "RT2"}):
            artifact = at.refresh_token_auth(AUTH_CONFIG, {
                "refresh_token": "RT", "resource": "https://graph.microsoft.com",
            })
        self.assertEqual(artifact["resource"], "https://graph.microsoft.com")
        self.assertIsNone(artifact["scope"])


class TestValidatesInPlaybook(unittest.TestCase):

    def test_playbook_using_all_four_auth_techniques_validates(self):
        config = {"playbooks": [{"name": "auth", "techniques": [
            {"technique": "password_auth", "enabled": True, "output": "ropc",
             "parameters": {"username": "u@x", "password": "p", "scope": "s"}},
            {"technique": "device_code_auth", "enabled": True, "output": "dc",
             "parameters": {"username": "u@x", "scope": "s"}},
            {"technique": "client_credentials_auth", "enabled": True, "output": "app",
             "parameters": {"client_id": "a", "client_secret": "b", "scope": "s"}},
            {"technique": "refresh_token_auth", "enabled": True, "output": "refreshed",
             "parameters": {"refresh_token": "${ropc.refresh_token}",
                            "scope": "outlook/.default"}},
        ]}]}
        self.assertEqual(validate_playbook(config, TECHNIQUES), [])

    def test_missing_required_auth_param_is_flagged(self):
        config = {"playbooks": [{"name": "auth", "techniques": [
            {"technique": "client_credentials_auth", "enabled": True,
             "parameters": {"client_id": "a", "scope": "s"}},  # no client_secret
        ]}]}
        errors = validate_playbook(config, TECHNIQUES)
        self.assertEqual(len(errors), 1)
        self.assertIn("missing required parameter: client_secret", errors[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
