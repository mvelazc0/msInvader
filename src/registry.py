"""Per-technique contract table for technique chaining.

Each entry declares, for one technique:

    "requires":   [param, ...]   parameters the technique cannot run without
    "credential": param          the parameter carrying the auth material
    "scope":      "graph"|...    the scoped API the technique calls (if any)

An absent entry means "no declared contract": ``validate_playbook`` performs no
required-parameter check for that technique, and the engine applies no scope
handling.
"""

TECHNIQUES = {
    "password_auth": {
        "requires": ["username", "password", "scope"],
    },
    "device_code_auth": {
        "requires": ["username", "scope"],
    },
    "client_credentials_auth": {
        "requires": ["client_id", "client_secret", "scope"],
    },
    "refresh_token_auth": {
        # scope (v2.0) xor resource (v1.0) is enforced at run time by
        # get_token_with_refresh_token; only refresh_token is unconditional.
        "requires": ["refresh_token"],
    },
    "register_device": {
        "requires": ["access_token", "tenant_domain"],
        "credential": "access_token",
    },
    "get_prt_with_refresh_token": {
        "requires": ["refresh_token", "key_path", "cert_path"],
        "credential": "refresh_token",
    },
    "get_token_with_prt": {
        "requires": ["prt", "session_key", "client_id", "resource"],
    },
    "create_whfb_key": {
        "requires": ["access_token"],
        "credential": "access_token",
    },
    "get_prt_with_whfb_key": {
        "requires": ["whfb_key_path", "key_path", "cert_path", "username"],
    },
}


def get_contract(technique_name):
    """Return the contract dict for *technique_name*, or ``{}`` if undeclared."""
    return TECHNIQUES.get(technique_name, {})
