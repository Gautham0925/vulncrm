# Security test-case library

VULNCRM includes a documentation module (**Security test cases**, `/test-cases`, `/api/testcases`) holding 71 structured test cases for authorized testers. Each case records objective, affected module, role needed, severity, procedure, indicators of a weakness, expected secure behavior, remediation and references. Cases are versioned (`security_test_case_versions`) and can carry tester notes, status and linked audit-log references.

The library is documentation. It contains no flags, scoring or automated pass/fail claims; findings are judged by the tester.

## Using the library

1. Pick a case and read the objective, role and prerequisites.
2. Run the procedure against the **vulnerable training configuration** (see [VULNERABLE_MODE.md](VULNERABLE_MODE.md)) to observe the weakness, using your own tooling (browser, Burp Suite, curl).
3. Repeat against the **secure configuration** and compare with the expected secure behavior.
4. Record notes and status; review the audit log for what the application recorded.

Roles with `testcases.read` can view cases; `testcases.write` can edit notes and status.

## Index


### API Security

| ID | Title | Module | Role | Severity | Toggle |
|---|---|---|---|---|---|
| TC-API-001 | Cross-tenant customer record access (BOLA) | Customers | sales_rep | high | `bola` |
| TC-API-002 | Object-level access to opportunities and tickets | Pipeline | sales_rep | high | `bola` |
| TC-API-003 | Function-level authorization on destructive calls (BFLA) | Customers | sales_rep | high | `bfla` |
| TC-API-004 | Property-level authorization on opportunities | Pipeline | sales_rep | high | `mass_assignment` |
| TC-API-005 | Mass assignment on profile and organization settings | Profile | sales_rep | high | `mass_assignment` |
| TC-API-006 | Excessive data exposure in employee records | Employees | sales_manager | medium | `data_exposure` |
| TC-API-007 | API key strength and storage | API Management | integration_dev | high | `api_key_weak` |
| TC-API-008 | Rate limiting on authentication endpoints | Authentication | anonymous | medium | `rate_limit` |
| TC-API-009 | HTTP method override handling | Platform | sales_rep | medium | `method_override` |
| TC-API-010 | Retired API versions remain reachable | Platform | anonymous | high | `legacy_api` |
| TC-API-011 | Verbose error handling | Platform | anonymous | medium | `verbose_errors` |
| TC-API-012 | Object-level checks on session management | Authentication | sales_rep | medium | `bola` |

### GraphQL Security

| ID | Title | Module | Role | Severity | Toggle |
|---|---|---|---|---|---|
| TC-GQL-001 | Introspection exposure | GraphQL | anonymous | medium | `gql_introspection` |
| TC-GQL-002 | Object-level authorization in queries | GraphQL | sales_rep | high | `bola` |
| TC-GQL-003 | Field-level authorization | GraphQL | sales_rep | high | `gql_field_authz` |
| TC-GQL-004 | Mutation authorization | GraphQL | sales_rep | critical | `gql_mutation_authz` |
| TC-GQL-005 | Nested query depth | GraphQL | sales_rep | medium | `gql_depth` |
| TC-GQL-006 | Batching and alias abuse | GraphQL | anonymous | medium | `gql_batching` |
| TC-GQL-007 | GraphQL authentication | GraphQL | anonymous | high | `gql_introspection` |

### OAuth 2.0

| ID | Title | Module | Role | Severity | Toggle |
|---|---|---|---|---|---|
| TC-OAUTH-001 | Redirect URI validation | OAuth | anonymous | high | `oauth_redirect` |
| TC-OAUTH-002 | PKCE enforcement | OAuth | anonymous | high | `oauth_pkce` |
| TC-OAUTH-003 | Authorization code reuse | OAuth | anonymous | high | `oauth_code_reuse` |
| TC-OAUTH-004 | Scope escalation | OAuth | anonymous | high | `oauth_scope` |
| TC-OAUTH-005 | Refresh token rotation and reuse detection | OAuth | anonymous | high | `oauth_refresh` |
| TC-OAUTH-006 | Client authentication weaknesses | OAuth | anonymous | medium | `oauth_client_auth` |
| TC-OAUTH-007 | Token lifetime | OAuth | anonymous | medium | `oauth_expiry` |
| TC-OAUTH-008 | State parameter handling in sign-in | OAuth | anonymous | medium | `oauth_state` |

### OpenID Connect

| ID | Title | Module | Role | Severity | Toggle |
|---|---|---|---|---|---|
| TC-OIDC-001 | ID token validation | OIDC | anonymous | high | `oidc_validation` |
| TC-OIDC-002 | Nonce validation | OIDC | anonymous | medium | `oidc_nonce` |
| TC-OIDC-003 | Account linking by email | OIDC | anonymous | high | `oidc_linking` |
| TC-OIDC-004 | JWKS URL trust (jku header) | OIDC | anonymous | critical | `oidc_jku` |
| TC-OIDC-005 | Key rotation and unknown key IDs | OIDC | anonymous | medium | `oidc_validation` |

### SAML 2.0

| ID | Title | Module | Role | Severity | Toggle |
|---|---|---|---|---|---|
| TC-SAML-001 | Missing signature handling | SAML | anonymous | critical | `saml_signature` |
| TC-SAML-002 | XML signature wrapping | SAML | anonymous | critical | `saml_wrapping` |
| TC-SAML-003 | Assertion replay | SAML | anonymous | high | `saml_replay` |
| TC-SAML-004 | Audience restriction | SAML | anonymous | high | `saml_audience` |
| TC-SAML-005 | Recipient and destination validation | SAML | anonymous | medium | `saml_recipient` |
| TC-SAML-006 | Issuer validation | SAML | anonymous | high | `saml_issuer` |
| TC-SAML-007 | Certificate trust | SAML | anonymous | critical | `saml_cert` |
| TC-SAML-008 | Request correlation (InResponseTo) | SAML | anonymous | medium | `saml_correlation` |
| TC-SAML-009 | Authentication context | SAML | anonymous | low | `saml_correlation` |
| TC-SAML-010 | Single logout authorization | SAML | anonymous | medium | `saml_slo` |

### Business Logic

| ID | Title | Module | Role | Severity | Toggle |
|---|---|---|---|---|---|
| TC-BL-001 | Approval bypass on large deals | Pipeline | sales_rep | high | `approval_bypass` |
| TC-BL-002 | Deal value manipulation after approval | Pipeline | sales_rep | high | `deal_value` |
| TC-BL-003 | Workflow state skipping | Pipeline | sales_rep | medium | `workflow_state` |
| TC-BL-004 | Unauthorized lead conversion | Leads | sales_rep | high | `lead_convert` |
| TC-BL-005 | Customer and lead reassignment | Customers | sales_rep | high | `reassign` |
| TC-BL-006 | Role modification | Employees | sales_manager | critical | `role_change` |
| TC-BL-007 | Unauthorized administrative actions | Administration | sales_rep | high | `admin_actions` |
| TC-BL-008 | Unauthorized document sharing and ownership change | Documents | sales_rep | high | `doc_share` |
| TC-BL-009 | Document ownership transfer | Documents | sales_rep | high | `ownership` |

### File Security

| ID | Title | Module | Role | Severity | Toggle |
|---|---|---|---|---|---|
| TC-FILE-001 | Unauthorized file download | Documents | sales_rep | high | `file_download` |
| TC-FILE-002 | Upload validation | Documents | sales_rep | high | `file_upload` |
| TC-FILE-003 | Filename handling and storage path | Documents | sales_rep | high | `file_name` |
| TC-FILE-004 | File replacement authorization | Documents | sales_rep | high | `file_replace` |

### Web Application

| ID | Title | Module | Role | Severity | Toggle |
|---|---|---|---|---|---|
| TC-WEB-001 | Stored XSS in notes and ticket comments | Customers | sales_rep | high | `xss_stored` |
| TC-WEB-002 | Reflected XSS in report print view | Reports | auditor | medium | `xss_reflected` |
| TC-WEB-003 | DOM XSS from URL search term | Customers | sales_rep | medium | `xss_dom` |
| TC-WEB-004 | CSRF on state-changing requests | Platform | sales_rep | high | `csrf` |
| TC-WEB-005 | SSRF through webhook tests and URL import | Integrations | integration_dev | high | `ssrf` |
| TC-WEB-006 | SQL injection in customer search | Customers | sales_rep | critical | `sqli` |
| TC-WEB-007 | Session fixation | Authentication | anonymous | high | `session_fixation` |
| TC-WEB-008 | Session lifecycle | Authentication | sales_rep | medium | `session_handling` |
| TC-WEB-009 | CORS policy | Platform | anonymous | medium | `misconfig_cors` |
| TC-WEB-010 | Security headers and information disclosure | Platform | anonymous | low | `misconfig_headers` |

### Authentication

| ID | Title | Module | Role | Severity | Toggle |
|---|---|---|---|---|---|
| TC-AUTH-001 | Account enumeration | Authentication | anonymous | medium | `auth_enum` |
| TC-AUTH-002 | Account lockout and password policy | Authentication | anonymous | medium | `auth_lockout` |
| TC-AUTH-003 | One-time passcode brute force | Authentication | anonymous | high | `otp_bruteforce` |
| TC-AUTH-004 | Password reset token strength | Authentication | anonymous | high | `weak_reset` |

### Node.js and NoSQL

| ID | Title | Module | Role | Severity | Toggle |
|---|---|---|---|---|---|
| TC-NODE-001 | Prototype pollution in connector configuration | Integrations | integration_dev | high | `proto_pollution` |
| TC-NODE-002 | NoSQL operator injection in connector lookup | Integrations | integration_dev | high | `nosql` |
