from app.config import get_settings

_override: str | None = None
_disabled_extra: set[str] = set()

ALL_FLAGS = [
    "bola", "bfla", "bopla", "mass_assignment", "data_exposure", "api_key_weak", "rate_limit", "method_override",
    "legacy_api", "verbose_errors", "gql_introspection", "gql_depth", "gql_batching", "gql_field_authz", "gql_mutation_authz",
    "oauth_redirect", "oauth_state", "oauth_pkce", "oauth_code_reuse", "oauth_scope", "oauth_refresh", "oauth_client_auth", "oauth_expiry",
    "oidc_validation", "oidc_nonce", "oidc_linking", "oidc_jku",
    "saml_signature", "saml_wrapping", "saml_replay", "saml_audience", "saml_recipient", "saml_issuer", "saml_cert", "saml_correlation", "saml_slo",
    "nosql", "proto_pollution",
    "approval_bypass", "lead_convert", "reassign", "deal_value", "workflow_state", "role_change", "doc_share", "ownership", "admin_actions",
    "file_download", "file_upload", "file_name", "file_replace",
    "xss_stored", "xss_reflected", "xss_dom", "csrf", "ssrf", "sqli", "session_fixation", "session_handling", "misconfig_cors", "misconfig_headers",
    "auth_enum", "auth_lockout", "otp_bruteforce", "weak_reset",
]


def mode() -> str:
    s = get_settings()
    m = _override or s.security_mode
    if m == "vulnerable" and not s.training_allowed:
        return "secure"
    return m


def set_override(m: str | None):
    global _override
    _override = m


def vuln(flag: str) -> bool:
    if mode() != "vulnerable":
        return False
    off = {x.strip() for x in get_settings().vuln_disable.split(",") if x.strip()}
    return flag not in off
