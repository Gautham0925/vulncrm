# API documentation

Generated from the running application by `tools/gen_docs.py`. Every `/api` route requires authentication (session cookie, bearer JWT, `vck_` API key, or `vco_` OAuth token) unless noted. Writes using a cookie session also require the `X-CSRF-Token` header in the secure configuration.

Interactive OpenAPI is served at `/api/docs` and the machine-readable spec at `/api/openapi.json`.

## auth

| Method | Path |
|---|---|
| POST | `/api/auth/change-password` |
| POST | `/api/auth/forgot-password` |
| POST | `/api/auth/login` |
| POST | `/api/auth/logout` |
| GET | `/api/auth/me` |
| POST | `/api/auth/reset-password` |
| GET | `/api/auth/session-init` |
| GET | `/api/auth/sessions` |
| DELETE | `/api/auth/sessions/{sid_id}` |
| POST | `/api/auth/switch-org` |
| POST | `/api/auth/verify-otp` |

## customers

| Method | Path |
|---|---|
| GET | `/api/customers` |
| POST | `/api/customers` |
| GET | `/api/customers/{cid}` |
| PATCH | `/api/customers/{cid}` |
| DELETE | `/api/customers/{cid}` |
| GET | `/api/customers/{cid}/activities` |
| POST | `/api/customers/{cid}/activities` |
| POST | `/api/customers/{cid}/contacts` |
| DELETE | `/api/customers/{cid}/contacts/{contact_id}` |
| PUT | `/api/customers/{cid}/owner` |

## documents

| Method | Path |
|---|---|
| GET | `/api/documents` |
| POST | `/api/documents` |
| GET | `/api/documents/{did}` |
| PATCH | `/api/documents/{did}` |
| DELETE | `/api/documents/{did}` |
| GET | `/api/documents/{did}/download` |
| PUT | `/api/documents/{did}/owner` |
| GET | `/api/documents/{did}/preview` |
| POST | `/api/documents/{did}/share` |
| DELETE | `/api/documents/{did}/share/{mid}` |
| POST | `/api/documents/{did}/versions` |
| GET | `/api/files/{path}` |

## graphql

| Method | Path |
|---|---|
| POST | `/graphql` |

## integrations

| Method | Path |
|---|---|
| GET | `/api/audit` |
| GET | `/api/audit/export` |
| GET | `/api/integrations/clients` |
| POST | `/api/integrations/clients` |
| PATCH | `/api/integrations/clients/{cid}` |
| DELETE | `/api/integrations/clients/{cid}` |
| GET | `/api/integrations/clients/{cid}/keys` |
| POST | `/api/integrations/clients/{cid}/keys` |
| GET | `/api/integrations/configs` |
| POST | `/api/integrations/configs` |
| PATCH | `/api/integrations/configs/{iid}` |
| DELETE | `/api/integrations/configs/{iid}` |
| POST | `/api/integrations/connector/{action}` |
| POST | `/api/integrations/import-url` |
| DELETE | `/api/integrations/keys/{kid}` |
| GET | `/api/integrations/requests` |
| GET | `/api/integrations/webhooks` |
| POST | `/api/integrations/webhooks` |
| DELETE | `/api/integrations/webhooks/{wid}` |
| POST | `/api/integrations/webhooks/{wid}/test` |

## leads

| Method | Path |
|---|---|
| GET | `/api/leads` |
| POST | `/api/leads` |
| GET | `/api/leads/{lid}` |
| PATCH | `/api/leads/{lid}` |
| DELETE | `/api/leads/{lid}` |
| PUT | `/api/leads/{lid}/assign` |
| POST | `/api/leads/{lid}/convert` |
| GET | `/api/leads/{lid}/history` |
| POST | `/api/leads/{lid}/status` |

## misc

| Method | Path |
|---|---|
| GET | `/__internal/service-config` |
| GET | `/api/dev/mailbox` |
| GET | `/api/health` |
| GET | `/api/meta` |
| GET | `/api/notifications/read-all` |
| GET | `/api/search` |
| GET | `/api/system/info` |
| GET | `/api/v0/customers` |
| GET | `/api/v0/users` |

## oauth

| Method | Path |
|---|---|
| GET | `/.well-known/openid-configuration` |
| GET | `/api/oauth/clients` |
| POST | `/api/oauth/clients` |
| PATCH | `/api/oauth/clients/{cid}` |
| DELETE | `/api/oauth/clients/{cid}` |
| POST | `/api/oauth/clients/{cid}/rotate-secret` |
| GET | `/api/oauth/tokens` |
| DELETE | `/api/oauth/tokens/{tid}` |
| GET | `/oauth/authorize` |
| POST | `/oauth/authorize` |
| POST | `/oauth/introspect` |
| POST | `/oauth/revoke` |
| POST | `/oauth/token` |
| GET | `/oauth/userinfo` |
| GET | `/oidc/jwks.json` |

## oidc

| Method | Path |
|---|---|
| GET | `/api/auth/oidc/{slug}/callback` |
| GET | `/api/auth/oidc/{slug}/login` |

## opportunities

| Method | Path |
|---|---|
| GET | `/api/opportunities` |
| POST | `/api/opportunities` |
| GET | `/api/opportunities/forecast` |
| GET | `/api/opportunities/pipeline` |
| GET | `/api/opportunities/{oid}` |
| PATCH | `/api/opportunities/{oid}` |
| DELETE | `/api/opportunities/{oid}` |
| POST | `/api/opportunities/{oid}/approval` |
| GET | `/api/opportunities/{oid}/history` |
| POST | `/api/opportunities/{oid}/request-approval` |
| POST | `/api/opportunities/{oid}/stage` |

## people

| Method | Path |
|---|---|
| GET | `/api/employees` |
| POST | `/api/employees` |
| GET | `/api/employees/{mid}` |
| PATCH | `/api/employees/{mid}` |
| POST | `/api/employees/{mid}/activate` |
| GET | `/api/employees/{mid}/activity` |
| POST | `/api/employees/{mid}/deactivate` |
| PUT | `/api/employees/{mid}/role` |
| GET | `/api/notifications` |
| POST | `/api/notifications/read` |
| GET | `/api/org` |
| PATCH | `/api/org` |
| GET | `/api/permissions` |
| GET | `/api/platform/orgs` |
| POST | `/api/platform/orgs` |
| GET | `/api/profile` |
| PATCH | `/api/profile` |
| GET | `/api/roles` |
| POST | `/api/roles` |
| PATCH | `/api/roles/{rid}` |
| DELETE | `/api/roles/{rid}` |
| GET | `/api/teams` |
| POST | `/api/teams` |
| PATCH | `/api/teams/{tid}` |
| DELETE | `/api/teams/{tid}` |

## reports

| Method | Path |
|---|---|
| GET | `/api/dashboard` |
| GET | `/api/reports` |
| GET | `/api/reports/{kind}` |
| GET | `/api/reports/{kind}/export` |
| GET | `/api/reports/{kind}/print` |

## saml

| Method | Path |
|---|---|
| POST | `/saml/{slug}/acs` |
| GET | `/saml/{slug}/login` |
| GET | `/saml/{slug}/logout` |
| GET | `/saml/{slug}/metadata` |
| POST | `/saml/{slug}/slo` |

## security-test-library

| Method | Path |
|---|---|
| GET | `/api/testlib/cases` |
| POST | `/api/testlib/cases` |
| GET | `/api/testlib/cases/{tid}` |
| PATCH | `/api/testlib/cases/{tid}` |
| DELETE | `/api/testlib/cases/{tid}` |
| POST | `/api/testlib/cases/{tid}/restore/{version}` |
| GET | `/api/testlib/cases/{tid}/versions` |
| GET | `/api/testlib/export` |
| GET | `/api/testlib/facets` |
| POST | `/api/testlib/import` |

## sso

| Method | Path |
|---|---|
| GET | `/api/sso/saml` |
| PUT | `/api/sso/saml` |
| GET | `/api/sso/sessions` |
| DELETE | `/api/sso/sessions/{sid}` |

## tickets

| Method | Path |
|---|---|
| GET | `/api/tickets` |
| POST | `/api/tickets` |
| GET | `/api/tickets/{tid}` |
| PATCH | `/api/tickets/{tid}` |
| POST | `/api/tickets/{tid}/comments` |
| POST | `/api/tickets/{tid}/escalate` |

## GraphQL

`POST /graphql` with `{ "query": "..." }`. Queries: `me`, `customers`, `customer(id)`, `users`, `organization`. Mutations: `updateCustomer`, `deleteCustomer`, `setUserRole`. Depth, cost, alias and batching limits and introspection are enforced in the secure configuration.
