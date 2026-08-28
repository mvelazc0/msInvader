"""Per-technique contract table for technique chaining.

Each entry declares, for one technique:

    "requires":   [param, ...]   parameters the technique cannot run without
    "credential": param          the parameter carrying the auth material
    "scope":      "graph"|...    the scoped API the technique calls (if any)

An absent entry means "no declared contract": ``validate_playbook`` performs no
required-parameter check for that technique, and the engine applies no scope
handling.
"""

TECHNIQUES = {}


def get_contract(technique_name):
    """Return the contract dict for *technique_name*, or ``{}`` if undeclared."""
    return TECHNIQUES.get(technique_name, {})
