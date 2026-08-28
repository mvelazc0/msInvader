"""Authentication flows expressed as playbook techniques.

Each function is a thin wrapper over ``src.auth``. It takes the playbook's
global ``authentication`` config plus the step's already-resolved parameters,
and returns a token artifact: a dict carrying the tokens together with the
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

# Public client used by default, matching the value hardcoded in src.auth today
# (get_ms_token_username_pass, get_ms_token_device_code): "Microsoft Office".
DEFAULT_CLIENT_ID = 'd3590ed6-52b3-4102-aeff-aad2292ab01c'


def _tenant_id(auth_config, params):
    return params.get('tenant_id') or auth_config.get('tenant_id')


def _reject_unsupported(technique, params, names):
    """Raise if a parameter this flow cannot honor was supplied (truthy)."""
    for name in names:
        if params.get(name):
            raise ValueError(
                f"{technique}: parameter '{name}' is not supported for this flow"
            )


def _token_artifact(result, tenant_id, client_id, flow, scope=None, resource=None):
    """Build a context-carrying token artifact, or None if the flow failed."""
    if not result or not result.get('access_token'):
        logging.error(f"{flow} flow did not return an access token")
        return None

    artifact = {
        'access_token': result.get('access_token'),
        'refresh_token': result.get('refresh_token'),
        'tenant_id': tenant_id,
        'client_id': client_id,
        'scope': scope,
        'flow': flow,
    }
    if resource is not None:
        artifact['resource'] = resource
    return artifact


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
    return _token_artifact(result, tenant_id, client_id, 'resource_owner', scope=scope)


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
    return _token_artifact(result, tenant_id, client_id, 'device_code', scope=scope)


def client_credentials_auth(auth_config, params):
    """Client credentials (application) flow."""
    tenant_id = _tenant_id(auth_config, params)
    scope = params.get('scope')
    client_id = params.get('client_id')
    client_secret = params.get('client_secret')

    _reject_unsupported('client_credentials_auth', params,
                        ['resource', 'use_v1_endpoint', 'require_ngcmfa'])

    result = get_ms_token_client(tenant_id, client_id, client_secret, scope)
    return _token_artifact(result, tenant_id, client_id, 'client_credentials', scope=scope)


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
    return _token_artifact(
        result, tenant_id, client_id, 'refresh_token', scope=scope, resource=resource
    )
