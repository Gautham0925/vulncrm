# OAuth 2.0 implementation

VULNCRM is an OAuth 2.0 authorization server for third-party applications that call its API. Applications are managed in **OAuth applications** (`/oauth-apps`) or through `/api/oauth/clients`.

## Endpoints

| Endpoint | Purpose |
|---|---|
| `GET/POST /oauth/authorize` | Authorization code flow with an HTML consent page |
| `POST /oauth/token` | `authorization_code`, `refresh_token`, `client_credentials` |
| `POST /oauth/revoke` | Revoke access or refresh tokens |
| `POST /oauth/introspect` | Token introspection |
| `GET /oauth/userinfo` | Claims for the token's user |
| `GET /.well-known/openid-configuration` | Discovery document |
| `GET /oidc/jwks.json` | Signing keys |

## Clients

Confidential clients authenticate with a secret (hashed at rest, shown once, rotatable). Public clients have no secret and must use PKCE. Each client has registered redirect URIs, grant types and an allowed scope list. Seeded: Partner Portal, Mobile App (public, PKCE), Data Sync (client credentials).

## Scopes

`openid`, `profile`, `email`, `customers:read`, `customers:write`, `leads:read`, `leads:write`, `opportunities:read`, `reports:read`, `documents:read`, `admin`. The granted scope is the intersection of the request, the client registration and the user's permissions.

## Secure behavior

Exact redirect URI matching, mandatory S256 PKCE for public clients, single-use authorization codes (reuse revokes issued tokens), refresh token rotation with family revocation on reuse, short access token lifetimes, client authentication required, secrets never accepted in query strings, scope intersection at every grant, and CSRF protection on the consent form.

## Related toggles and test cases

`oauth_redirect`, `oauth_pkce`, `oauth_code_reuse`, `oauth_scope`, `oauth_refresh`, `oauth_client_auth`, `oauth_expiry`, `oauth_state`; test cases `TC-OAUTH-001` to `TC-OAUTH-008`.

Tests: `backend/tests/test_oauth_graphql_files.py`.
