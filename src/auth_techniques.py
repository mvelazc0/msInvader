"""Authentication flows expressed as playbook techniques.

Each function is a thin wrapper over ``src.auth``. It takes the playbook's
global ``authentication`` config plus the step's already-resolved parameters,
and returns a token output: a dict carrying the tokens together with the
context needed to obtain further tokens later -

    access_token, refresh_token, tenant_id, client_id, scope, flow

``flow`` records how the token was obtained: ``resource_owner``,
``device_code``, ``client_credentials`` or ``refresh_token``.

The raw HTTP flows in ``src.auth`` are the transport layer and are not touched
here. A parameter that a given flow's transport function cannot honor (for
example ``resource`` on the device code flow, whose helper has no v1.0 form) is
rejected rather than silently ignored, since the ``client_id`` / audience of a
sign-in is exactly what a detection engineer varies.
"""

import logging

from src.auth import (
    get_ms_token_client,
    get_ms_token_device_code,
    get_ms_token_device_code_v1,
    get_ms_token_username_pass,
    get_token_with_refresh_token,
)
from src.engine import PlaybookError, _prefix
from src.registry import TECHNIQUES

# Public client used by default, matching the value hardcoded in src.auth today
# (get_ms_token_username_pass, get_ms_token_device_code): "Microsoft Office".
DEFAULT_CLIENT_ID = 'd3590ed6-52b3-4102-aeff-aad2292ab01c'

# Short scope name -> the .default scope string that API family needs. The
# client modules used to each keep their own copy of these strings.
SCOPES = {
    "graph":    "https://graph.microsoft.com/.default",
    "ews":      "https://outlook.office365.com/.default",
    "rest":     "https://outlook.office365.com/.default",
    "arm":      "https://management.azure.com/.default",
    "keyvault": "https://vault.azure.net/.default",
    "prt":      "https://enrollment.manage.microsoft.com/.default",
}


def _tenant_id(auth_config, params):
    return params.get('tenant_id') or auth_config.get('tenant_id')


def _reject_unsupported(technique, params, names):
    """Raise if a parameter this flow cannot honor was supplied (truthy)."""
    for name in names:
        if params.get(name):
            raise ValueError(
                f"{technique}: parameter '{name}' is not supported for this flow"
            )


def _token_output(result, tenant_id, client_id, flow, scope=None, resource=None):
    """Build a context-carrying token output, or None if the flow failed."""
    if not result or not result.get('access_token'):
        logging.error(f"{flow} flow did not return an access token")
        return None

    output = {
        'access_token': result.get('access_token'),
        'refresh_token': result.get('refresh_token'),
        'tenant_id': tenant_id,
        'client_id': client_id,
        'scope': scope,
        'flow': flow,
    }
    if resource is not None:
        output['resource'] = resource
    return output


def password_auth(auth_config, params):
    """Resource-owner password credentials flow."""
    tenant_id = _tenant_id(auth_config, params)
    scope = params.get('scope')
    client_id = params.get('client_id') or DEFAULT_CLIENT_ID

    _reject_unsupported('password_auth', params,
                        ['resource', 'use_v1_endpoint', 'require_ngcmfa'])
    if client_id != DEFAULT_CLIENT_ID:
        raise ValueError(
            "password_auth: overriding client_id requires a change to src.auth; "
            f"this flow always authenticates as {DEFAULT_CLIENT_ID}"
        )

    result = get_ms_token_username_pass(
        tenant_id, params.get('username'), params.get('password'), scope
    )
    return _token_output(result, tenant_id, client_id, 'resource_owner', scope=scope)


def device_code_auth(auth_config, params):
    """Device code flow. ``use_v1_endpoint`` selects the v1.0 endpoint."""
    tenant_id = _tenant_id(auth_config, params)
    scope = params.get('scope')
    client_id = params.get('client_id') or DEFAULT_CLIENT_ID
    username = params.get('username')
    require_ngcmfa = bool(params.get('require_ngcmfa', False))

    _reject_unsupported('device_code_auth', params, ['resource'])

    if params.get('use_v1_endpoint', False):
        result = get_ms_token_device_code_v1(
            tenant_id, username, scope, client_id, use_amr_values=require_ngcmfa
        )
    else:
        result = get_ms_token_device_code(
            tenant_id, username, scope, client_id, require_ngcmfa
        )
    return _token_output(result, tenant_id, client_id, 'device_code', scope=scope)


def client_credentials_auth(auth_config, params):
    """Client credentials (application) flow."""
    tenant_id = _tenant_id(auth_config, params)
    scope = params.get('scope')
    client_id = params.get('client_id')
    client_secret = params.get('client_secret')

    _reject_unsupported('client_credentials_auth', params,
                        ['resource', 'use_v1_endpoint', 'require_ngcmfa'])

    result = get_ms_token_client(tenant_id, client_id, client_secret, scope)
    return _token_output(result, tenant_id, client_id, 'client_credentials', scope=scope)


def refresh_token_auth(auth_config, params):
    """Redeem a refresh token for a new access token (v2.0 scope or v1.0 resource)."""
    tenant_id = _tenant_id(auth_config, params)
    scope = params.get('scope')
    resource = params.get('resource')
    client_id = params.get('client_id') or DEFAULT_CLIENT_ID

    _reject_unsupported('refresh_token_auth', params,
                        ['use_v1_endpoint', 'require_ngcmfa'])

    result = get_token_with_refresh_token(
        tenant_id, params.get('refresh_token'),
        scope=scope, resource=resource, client_id=client_id,
    )
    return _token_output(
        result, tenant_id, client_id, 'refresh_token', scope=scope, resource=resource
    )


# ---------------------------------------------------------------------------
# Handing a chained step the right token
#
# A playbook step that calls a scoped API names an earlier authentication step
# as its credential. That step's token was minted for one audience, and it will
# not work against a different one - so before the technique runs, the token is
# checked against the API it is about to call and, if it does not fit, a new one
# is redeemed from the refresh token.
# ---------------------------------------------------------------------------

def scope_for(technique_name, access_method=None):
    """The scoped API a technique calls - 'graph', 'ews', 'rest', 'arm',
    'keyvault' - or None when it calls none. A technique that runs over more
    than one API declares its scope per access_method; this resolves that."""
    scope = TECHNIQUES.get(technique_name, {}).get('scope')
    if isinstance(scope, dict):
        return scope.get(access_method)
    return scope


def token_for_step(technique_name, parameters, sources, outputs, access_method=None, step=""):
    """Work out the access token a technique should be handed.

    Returns the ``{"access_token": ...}`` dict the technique function expects,
    or None for a technique that calls no scoped API and manages its own auth.
    """
    spec = TECHNIQUES.get(technique_name, {})
    credential_param = spec.get('credential')
    scope = scope_for(technique_name, access_method)
    if not credential_param or scope is None:
        return None

    value = parameters.get(credential_param)
    source = sources.get(credential_param)
    if source is None:
        # A pasted token, with no earlier step behind it: use it as written.
        return {"access_token": value}

    output = outputs.get(source)
    if not isinstance(output, dict):
        return {"access_token": value}

    return {"access_token": token_for_scope(output, source, scope, outputs, step=step)}


def token_for_scope(output, output_name, scope, outputs, step=""):
    """Get an access token for *scope*, using this step's source output.

    A playbook step gets its token from an earlier authentication step. That
    token was minted for one audience - Graph, EWS, ARM - and it will not work
    against a different one. There are three ways this can go.
    """
    wanted = SCOPES.get(scope, scope)

    # 1. The token the playbook already produced is for the right audience.
    if output.get('scope') == wanted or output.get('resource') == wanted:
        return output['access_token']

    # 2. We already redeemed this output's refresh token for that audience
    #    earlier in the run, so reuse it rather than signing in again.
    already = outputs.minted_token(output_name, scope)
    if already:
        logging.info(f"{_prefix(step)}reusing the {scope} token obtained earlier "
                     f"from '{output_name}'")
        return already

    # 3. Nothing fits. Redeem the refresh token for the audience we need.
    #
    #    This is a real authentication request against Entra ID. It appears in
    #    the tenant's sign-in logs even though the playbook has no step for it,
    #    which is worth knowing when reading the telemetry a run produced.
    refresh_token = output.get('refresh_token')
    if not refresh_token:
        raise PlaybookError(
            f"{_prefix(step)}need a {scope} token, but the token from "
            f"'{output_name}' is scoped for '{output.get('scope')}' and carries "
            f"no refresh_token to redeem")

    logging.info(f"{_prefix(step)}the token from '{output_name}' is scoped for "
                 f"'{output.get('scope')}', redeeming its refresh token for {scope}")
    result = get_token_with_refresh_token(
        output.get('tenant_id'), refresh_token,
        scope=wanted, client_id=output.get('client_id'),
    )
    if not result or not result.get('access_token'):
        raise PlaybookError(f"{_prefix(step)}could not redeem the refresh token "
                            f"from '{output_name}' for a {scope} token")

    outputs.save_minted_token(output_name, scope, result['access_token'])
    if result.get('refresh_token'):
        output['refresh_token'] = result['refresh_token']
    return result['access_token']


def uses_impersonation(technique_name, access_method, sources, outputs):
    """True when an EWS technique must send an impersonation header.

    EWS needs the header for application-permission access, and must not send it
    for delegated access. A token obtained with client credentials is the
    former; a token from a user sign-in is the latter.
    """
    if scope_for(technique_name, access_method) != 'ews':
        return False
    credential_param = TECHNIQUES.get(technique_name, {}).get('credential')
    source = sources.get(credential_param) if credential_param else None
    if source is None:
        return False
    output = outputs.get(source)
    return isinstance(output, dict) and output.get('flow') == 'client_credentials'
