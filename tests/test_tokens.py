"""Offline tests for handing a chained step the right access token.

Covers src.auth_techniques: scope_for, token_for_step, token_for_scope and
uses_impersonation. get_token_with_refresh_token is patched out; nothing here
touches the network.
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import auth_techniques as at  # noqa: E402
from src.auth_techniques import (  # noqa: E402
    SCOPES,
    scope_for,
    token_for_scope,
    token_for_step,
    uses_impersonation,
)
from src.engine import OutputStore, PlaybookError  # noqa: E402

GRAPH = "https://graph.microsoft.com/.default"
EWS = "https://outlook.office365.com/.default"
ARM = "https://management.azure.com/.default"


def _store(**outputs):
    store = OutputStore()
    for name, value in outputs.items():
        store.save(name, value)
    return store


class TestScopes(unittest.TestCase):

    def test_values_match_the_client_module_constants(self):
        self.assertEqual(SCOPES["graph"], GRAPH)
        self.assertEqual(SCOPES["ews"], EWS)
        self.assertEqual(SCOPES["rest"], EWS)
        self.assertEqual(SCOPES["arm"], ARM)
        self.assertEqual(SCOPES["keyvault"], "https://vault.azure.net/.default")
        self.assertEqual(SCOPES["prt"], "https://enrollment.manage.microsoft.com/.default")


class TestScopeFor(unittest.TestCase):

    def test_plain_scope(self):
        self.assertEqual(scope_for("enable_email_forwarding"), "rest")
        self.assertEqual(scope_for("list_key_vaults"), "arm")

    def test_multi_method_scope_resolves_by_access_method(self):
        self.assertEqual(scope_for("read_email", "graph"), "graph")
        self.assertEqual(scope_for("read_email", "ews"), "ews")

    def test_no_scope_declared(self):
        self.assertIsNone(scope_for("register_device"))
        self.assertIsNone(scope_for("password_spray"))


class TestTokenForStep(unittest.TestCase):

    def test_technique_with_no_scope_gets_no_token(self):
        with mock.patch.object(at, "get_token_with_refresh_token") as fn:
            self.assertIsNone(
                token_for_step("register_device", {"access_token": "AT"}, {}, _store()))
        fn.assert_not_called()

    def test_literal_credential_used_as_is_no_mint(self):
        with mock.patch.object(at, "get_token_with_refresh_token") as fn:
            token = token_for_step("read_email", {"access_token": "PASTED"}, {},
                                   _store(), access_method="graph")
        fn.assert_not_called()
        self.assertEqual(token, {"access_token": "PASTED"})

    def test_matching_scope_returns_value_without_minting(self):
        store = _store(victim1={"access_token": "AT", "scope": GRAPH, "flow": "device_code"})
        with mock.patch.object(at, "get_token_with_refresh_token") as fn:
            token = token_for_step("read_email", {"access_token": "AT"},
                                   {"access_token": "victim1"}, store, access_method="graph")
        fn.assert_not_called()
        self.assertEqual(token, {"access_token": "AT"})

    def test_v1_resource_field_counts_as_coverage(self):
        store = _store(t={"access_token": "AT", "resource": ARM})
        with mock.patch.object(at, "get_token_with_refresh_token") as fn:
            token = token_for_step("list_key_vaults", {"access_token": "AT"},
                                   {"access_token": "t"}, store)
        fn.assert_not_called()
        self.assertEqual(token["access_token"], "AT")


class TestTokenForScope(unittest.TestCase):

    def test_scope_mismatch_redeems_once_and_reuses(self):
        store = _store(victim1={
            "access_token": "GRAPH_AT", "refresh_token": "RT",
            "tenant_id": "tid", "client_id": "cid",
            "scope": GRAPH, "flow": "device_code",
        })
        with mock.patch.object(at, "get_token_with_refresh_token",
                               return_value={"access_token": "EWS_AT", "refresh_token": None}) as fn:
            first = token_for_scope(store.get("victim1"), "victim1", "ews", store)
            second = token_for_scope(store.get("victim1"), "victim1", "ews", store)

        fn.assert_called_once_with("tid", "RT", scope=EWS, client_id="cid")
        self.assertEqual(first, "EWS_AT")
        self.assertEqual(second, "EWS_AT")               # served from the run's cache
        self.assertEqual(store.minted_token("victim1", "ews"), "EWS_AT")

    def test_redeemed_refresh_token_replaces_the_stored_one(self):
        output = {"access_token": "AT", "refresh_token": "RT1", "tenant_id": "t",
                  "client_id": "c", "scope": GRAPH}
        store = _store(victim1=output)
        with mock.patch.object(at, "get_token_with_refresh_token",
                               return_value={"access_token": "ARM_AT", "refresh_token": "RT2"}):
            token_for_scope(store.get("victim1"), "victim1", "arm", store)
        self.assertEqual(output["refresh_token"], "RT2")
        self.assertEqual(store.minted_token("victim1", "arm"), "ARM_AT")

    def test_mismatch_without_refresh_token_raises(self):
        store = _store(victim1={"access_token": "AT", "scope": GRAPH})   # no refresh_token
        with mock.patch.object(at, "get_token_with_refresh_token") as fn:
            with self.assertRaises(PlaybookError):
                token_for_scope(store.get("victim1"), "victim1", "ews", store)
        fn.assert_not_called()

    def test_redeem_http_failure_raises(self):
        store = _store(victim1={"access_token": "AT", "refresh_token": "RT",
                                "tenant_id": "t", "client_id": "c", "scope": GRAPH})
        with mock.patch.object(at, "get_token_with_refresh_token", return_value=None):
            with self.assertRaises(PlaybookError):
                token_for_scope(store.get("victim1"), "victim1", "ews", store)


class TestUsesImpersonation(unittest.TestCase):

    def test_true_for_ews_technique_holding_an_application_token(self):
        store = _store(app={"access_token": "AT", "scope": GRAPH, "flow": "client_credentials"})
        self.assertTrue(uses_impersonation("read_email", "ews",
                                           {"access_token": "app"}, store))

    def test_false_for_ews_technique_holding_a_user_token(self):
        store = _store(victim1={"access_token": "AT", "scope": EWS, "flow": "device_code"})
        self.assertFalse(uses_impersonation("read_email", "ews",
                                            {"access_token": "victim1"}, store))

    def test_false_for_graph_technique_even_with_an_application_token(self):
        # A Graph step never sends the EWS impersonation header, whatever token
        # it holds.
        store = _store(app={"access_token": "AT", "scope": GRAPH, "flow": "client_credentials"})
        self.assertFalse(uses_impersonation("read_email", "graph",
                                            {"access_token": "app"}, store))

    def test_false_for_literal_credential(self):
        self.assertFalse(uses_impersonation("read_email", "ews", {}, _store()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
