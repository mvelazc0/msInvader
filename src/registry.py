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
    "get_prt_with_refresh_token_v2": {
        # v2.0 endpoint: prt_protocol_version 3.0 in place of windows_api_version.
        "requires": ["refresh_token", "key_path", "cert_path"],
        "credential": "refresh_token",
    },
    "get_token_with_prt": {
        "requires": ["prt", "session_key", "client_id", "resource"],
    },
    "get_token_with_prt_v2": {
        # v2.0 endpoint: a 'scope' string in place of the v1.0 'resource'.
        "requires": ["prt", "session_key", "client_id", "scope"],
    },
    "create_whfb_key": {
        "requires": ["access_token"],
        "credential": "access_token",
    },
    "get_prt_with_whfb_key": {
        "requires": ["whfb_key_path", "key_path", "cert_path", "username"],
    },
    "get_prt_with_whfb_key_v2": {
        # v2.0 endpoint: prt_protocol_version 3.0 in place of windows_api_version.
        "requires": ["whfb_key_path", "key_path", "cert_path", "username"],
    },

    # --- Graph ---
    "search_email":                 {"requires": ["access_token"], "credential": "access_token", "scope": "graph"},
    "search_onedrive":              {"requires": ["access_token"], "credential": "access_token", "scope": "graph"},
    "send_mail":                    {"requires": ["access_token"], "credential": "access_token", "scope": "graph"},
    "add_application_secret":       {"requires": ["access_token", "app_id"], "credential": "access_token", "scope": "graph"},
    "add_service_principal":        {"requires": ["access_token", "app_id"], "credential": "access_token", "scope": "graph"},
    "create_app_registration":     {"requires": ["access_token"], "credential": "access_token", "scope": "graph"},
    "admin_consent":               {"requires": ["access_token"], "credential": "access_token", "scope": "graph"},
    "enumerate_users":             {"requires": ["access_token"], "credential": "access_token", "scope": "graph"},
    "enumerate_groups":            {"requires": ["access_token"], "credential": "access_token", "scope": "graph"},
    "enumerate_applications":      {"requires": ["access_token"], "credential": "access_token", "scope": "graph"},
    "enumerate_service_principals":{"requires": ["access_token"], "credential": "access_token", "scope": "graph"},
    "enumerate_directory_roles":   {"requires": ["access_token"], "credential": "access_token", "scope": "graph"},
    "enumerate_app_role_assignments": {"requires": ["access_token"], "credential": "access_token", "scope": "graph"},
    "change_user_password":        {"requires": ["access_token"], "credential": "access_token", "scope": "graph"},
    "assign_app_role":             {"requires": ["access_token"], "credential": "access_token", "scope": "graph"},
    "create_user":                 {"requires": ["access_token"], "credential": "access_token", "scope": "graph"},
    "assign_entra_role":           {"requires": ["access_token"], "credential": "access_token", "scope": "graph"},

    # --- multi-method (scope depends on access_method) ---
    "read_email":   {"requires": ["access_token", "mailbox"], "credential": "access_token",
                     "scope": {"graph": "graph", "ews": "ews"}},
    "create_rule":  {"requires": ["access_token"], "credential": "access_token",
                     "scope": {"graph": "graph", "ews": "ews", "rest": "rest"}},
    "add_folder_permission": {"requires": ["access_token"], "credential": "access_token",
                              "scope": {"ews": "ews", "rest": "rest"}},

    # --- REST (Exchange Online management) ---
    "enable_email_forwarding": {"requires": ["access_token"], "credential": "access_token", "scope": "rest"},
    "add_mailbox_delegation":  {"requires": ["access_token"], "credential": "access_token", "scope": "rest"},
    "run_compliance_search":   {"requires": ["access_token"], "credential": "access_token", "scope": "rest"},
    "create_mailflow_rule":    {"requires": ["access_token"], "credential": "access_token", "scope": "rest"},

    # --- ARM ---
    "list_key_vaults":                        {"requires": ["access_token"], "credential": "access_token", "scope": "arm"},
    "add_keyvault_access_policy":             {"requires": ["access_token"], "credential": "access_token", "scope": "arm"},
    "list_keyvault_access_policies":          {"requires": ["access_token"], "credential": "access_token", "scope": "arm"},
    "enumerate_arm_role_assignments":         {"requires": ["access_token"], "credential": "access_token", "scope": "arm"},
    "enumerate_arm_resources":               {"requires": ["access_token"], "credential": "access_token", "scope": "arm"},
    "enumerate_privileged_arm_role_holders":  {"requires": ["access_token"], "credential": "access_token", "scope": "arm"},
    # The VM techniques call management.azure.com, so they need an ARM token,
    # not the Key Vault token they were handed before.
    "execute_command":       {"requires": ["access_token", "subscription_id", "resource_group", "vm_name"],
                              "credential": "access_token", "scope": "arm"},
    "execute_custom_script": {"requires": ["access_token"], "credential": "access_token", "scope": "arm"},
    "reset_password":        {"requires": ["access_token"], "credential": "access_token", "scope": "arm"},
    "list_extensions":       {"requires": ["access_token"], "credential": "access_token", "scope": "arm"},
    "delete_extension":      {"requires": ["access_token"], "credential": "access_token", "scope": "arm"},

    # --- Key Vault data plane ---
    "list_keyvault_items":   {"requires": ["access_token"], "credential": "access_token", "scope": "keyvault"},
    "access_key_vault_item": {"requires": ["access_token"], "credential": "access_token", "scope": "keyvault"},

    # --- no credential ---
    "password_spray": {"requires": ["user_list", "password"]},
}


def get_contract(technique_name):
    """Return the contract dict for *technique_name*, or ``{}`` if undeclared."""
    return TECHNIQUES.get(technique_name, {})
