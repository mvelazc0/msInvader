"""Offline tests for credential building and lazy per-scope token minting."""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import engine  # noqa: E402
from src.engine import (  # noqa: E402
    SCOPES,
    RunContext,
    ReferenceError,
    build_credential,
    mint_scoped_token,
)

GRAPH = "https://graph.microsoft.com/.default"
EWS = "https://outlook.office365.com/.default"


def _ctx(**artifacts):
    ctx = RunContext()
    for name, art in artifacts.items():
        ctx._store[name] = art
    return ctx


class TestScopes(unittest.TestCase):

    def test_values_match_the_client_module_constants(self):
        self.assertEqual(SCOPES["graph"], GRAPH)
        self.assertEqual(SCOPES["ews"], EWS)
        self.assertEqual(SCOPES["rest"], EWS)
        self.assertEqual(SCOPES["arm"], "https://management.azure.com/.default")
        self.assertEqual(SCOPES["keyvault"], "https://vault.azure.net/.default")
        self.assertEqual(SCOPES["prt"], "https://enrollment.manage.microsoft.com/.default")


class TestLiteralCredential(unittest.TestCase):

    def test_literal_used_as_is_no_provenance_no_mint(self):
        with mock.patch.object(engine, "get_token_with_refresh_token") as fn:
            token, imp = build_credential("PASTED", None, _ctx(), scope_name="graph")
        fn.assert_not_called()
        self.assertEqual(token, {"access_token": "PASTED"})
        self.assertFalse(imp)


class TestScopeMatch(unittest.TestCase):

    def test_matching_scope_returns_value_without_minting(self):
        ctx = _ctx(victim1={"access_token": "AT", "scope": GRAPH, "flow": "device_code"})
        with mock.patch.object(engine, "get_token_with_refresh_token") as fn:
            token, imp = build_credential("AT", "victim1", ctx, scope_name="graph")
        fn.assert_not_called()
        self.assertEqual(token, {"access_token": "AT"})
        self.assertFalse(imp)

    def test_v1_resource_field_counts_as_coverage(self):
        ctx = _ctx(t={"access_token": "AT", "resource": "https://management.azure.com/.default"})
        with mock.patch.object(engine, "get_token_with_refresh_token") as fn:
            token, _ = build_credential("AT", "t", ctx, scope_name="arm")
        fn.assert_not_called()
        self.assertEqual(token["access_token"], "AT")

    def test_no_scope_declared_passes_value_through_but_still_sets_impersonation(self):
        ctx = _ctx(app={"access_token": "AT", "scope": GRAPH, "flow": "client_credentials"})
        with mock.patch.object(engine, "get_token_with_refresh_token") as fn:
            token, imp = build_credential("AT", "app", ctx, scope_name=None)
        fn.assert_not_called()
        self.assertEqual(token, {"access_token": "AT"})
        self.assertTrue(imp)


class TestLazyMinting(unittest.TestCase):

    def test_scope_mismatch_mints_once_and_caches(self):
        ctx = _ctx(victim1={
            "access_token": "GRAPH_AT", "refresh_token": "RT",
            "tenant_id": "tid", "client_id": "cid",
            "scope": GRAPH, "flow": "device_code",
        })
        with mock.patch.object(engine, "get_token_with_refresh_token",
                               return_value={"access_token": "EWS_AT", "refresh_token": None}) as fn:
            token1, _ = build_credential("GRAPH_AT", "victim1", ctx, scope_name="ews")
            token2, _ = build_credential("GRAPH_AT", "victim1", ctx, scope_name="ews")

        fn.assert_called_once_with("tid", "RT", scope=EWS, client_id="cid")
        self.assertEqual(token1, {"access_token": "EWS_AT"})
        self.assertEqual(token2, {"access_token": "EWS_AT"})   # served from cache
        self.assertEqual(ctx.get("victim1")["_scoped_tokens"], {"ews": "EWS_AT"})

    def test_mint_refreshes_stored_refresh_token_when_a_new_one_returns(self):
        art = {"access_token": "AT", "refresh_token": "RT1", "tenant_id": "t",
               "client_id": "c", "scope": GRAPH}
        with mock.patch.object(engine, "get_token_with_refresh_token",
                               return_value={"access_token": "ARM_AT", "refresh_token": "RT2"}):
            mint_scoped_token(art, "arm")
        self.assertEqual(art["refresh_token"], "RT2")
        self.assertEqual(art["_scoped_tokens"]["arm"], "ARM_AT")

    def test_mismatch_without_refresh_token_raises(self):
        ctx = _ctx(victim1={"access_token": "AT", "scope": GRAPH})  # no refresh_token
        with mock.patch.object(engine, "get_token_with_refresh_token") as fn:
            with self.assertRaises(ReferenceError):
                build_credential("AT", "victim1", ctx, scope_name="ews")
        fn.assert_not_called()

    def test_mint_http_failure_raises(self):
        ctx = _ctx(victim1={"access_token": "AT", "refresh_token": "RT",
                            "tenant_id": "t", "client_id": "c", "scope": GRAPH})
        with mock.patch.object(engine, "get_token_with_refresh_token", return_value=None):
            with self.assertRaises(ReferenceError):
                build_credential("AT", "victim1", ctx, scope_name="ews")

    def test_impersonation_true_for_client_credentials_flow_even_when_minting(self):
        ctx = _ctx(app={"access_token": "AT", "refresh_token": "RT", "tenant_id": "t",
                        "client_id": "c", "scope": GRAPH, "flow": "client_credentials"})
        with mock.patch.object(engine, "get_token_with_refresh_token",
                               return_value={"access_token": "X"}):
            _, imp = build_credential("AT", "app", ctx, scope_name="ews")
        self.assertTrue(imp)


if __name__ == "__main__":
    unittest.main(verbosity=2)
