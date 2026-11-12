# Vulnerable training configuration

> For isolated, authorized training and testing only. Never expose this configuration to a network you do not fully control.

## Activation

All three must be true, otherwise the application behaves securely:

```
SECURITY_MODE=vulnerable
ENVIRONMENT=local            # local | training | development | test
TRAINING_ACK=I_UNDERSTAND_THIS_IS_VULNERABLE
```

If `SECURITY_MODE=vulnerable` is set with any other environment (for example `production`), or without the acknowledgement, startup logs a warning and every weakness stays disabled. The active configuration is shown in `/api/health` and in the UI banner.

Weaknesses are individual toggles inside normal business workflows. There is no challenge UI, scoring, or flag. `VULN_DISABLE=a,b` turns individual toggles off so one area can be tested in isolation.

## Isolation measures

- Docker Compose binds to `127.0.0.1` only; the vulnerable profile uses its own database volume and a separate network.
- Synthetic data only; outbound requests from the SSRF-capable features still never reach link-local or cloud metadata addresses.
- Webhook delivery is disabled in tests (`VULNCRM_DISABLE_WEBHOOKS=1`).
- Do not reuse the vulnerable data volume for anything else.


Each toggle below changes one behavior in the vulnerable training configuration. Every toggle is inactive in the secure configuration and can be switched off individually with `VULN_DISABLE=toggle1,toggle2`.

| Toggle | Related test cases |
|---|---|
| `bola` | TC-API-001, TC-API-002, TC-API-012, TC-GQL-002 |
| `bfla` | TC-API-003 |
| `mass_assignment` | TC-API-004, TC-API-005 |
| `data_exposure` | TC-API-006 |
| `api_key_weak` | TC-API-007 |
| `rate_limit` | TC-API-008 |
| `method_override` | TC-API-009 |
| `legacy_api` | TC-API-010 |
| `verbose_errors` | TC-API-011 |
| `gql_introspection` | TC-GQL-001, TC-GQL-007 |
| `gql_depth` | TC-GQL-005 |
| `gql_batching` | TC-GQL-006 |
| `gql_field_authz` | TC-GQL-003 |
| `gql_mutation_authz` | TC-GQL-004 |
| `oauth_redirect` | TC-OAUTH-001 |
| `oauth_state` | TC-OAUTH-008 |
| `oauth_pkce` | TC-OAUTH-002 |
| `oauth_code_reuse` | TC-OAUTH-003 |
| `oauth_scope` | TC-OAUTH-004 |
| `oauth_refresh` | TC-OAUTH-005 |
| `oauth_client_auth` | TC-OAUTH-006 |
| `oauth_expiry` | TC-OAUTH-007 |
| `oidc_validation` | TC-OIDC-001, TC-OIDC-005 |
| `oidc_nonce` | TC-OIDC-002 |
| `oidc_linking` | TC-OIDC-003 |
| `oidc_jku` | TC-OIDC-004 |
| `saml_signature` | TC-SAML-001 |
| `saml_wrapping` | TC-SAML-002 |
| `saml_replay` | TC-SAML-003 |
| `saml_audience` | TC-SAML-004 |
| `saml_recipient` | TC-SAML-005 |
| `saml_issuer` | TC-SAML-006 |
| `saml_cert` | TC-SAML-007 |
| `saml_correlation` | TC-SAML-008, TC-SAML-009 |
| `saml_slo` | TC-SAML-010 |
| `nosql` | TC-NODE-002 |
| `proto_pollution` | TC-NODE-001 |
| `approval_bypass` | TC-BL-001 |
| `lead_convert` | TC-BL-004 |
| `reassign` | TC-BL-005 |
| `deal_value` | TC-BL-002 |
| `workflow_state` | TC-BL-003 |
| `role_change` | TC-BL-006 |
| `doc_share` | TC-BL-008 |
| `ownership` | TC-BL-009 |
| `admin_actions` | TC-BL-007 |
| `file_download` | TC-FILE-001 |
| `file_upload` | TC-FILE-002 |
| `file_name` | TC-FILE-003 |
| `file_replace` | TC-FILE-004 |
| `xss_stored` | TC-WEB-001 |
| `xss_reflected` | TC-WEB-002 |
| `xss_dom` | TC-WEB-003 |
| `csrf` | TC-WEB-004 |
| `ssrf` | TC-WEB-005 |
| `sqli` | TC-WEB-006 |
| `session_fixation` | TC-WEB-007 |
| `session_handling` | TC-WEB-008 |
| `misconfig_cors` | TC-WEB-009 |
| `misconfig_headers` | TC-WEB-010 |
| `auth_enum` | TC-AUTH-001 |
| `auth_lockout` | TC-AUTH-002 |
| `otp_bruteforce` | TC-AUTH-003 |
| `weak_reset` | TC-AUTH-004 |