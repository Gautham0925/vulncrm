# OpenID Connect implementation

VULNCRM acts as an **OIDC relying party** for organization sign-in against a configured identity provider (the bundled synthetic IdP by default), and as an OIDC provider through its OAuth server (discovery, JWKS, userinfo).

## Relying-party flow

1. `GET /api/auth/oidc/{org}/login` creates `state` and `nonce`, stores them in `sso_sessions`, and redirects to the IdP authorize URL.
2. The IdP redirects to `/api/auth/oidc/{org}/callback?code=…&state=…`.
3. The backend exchanges the code at the token endpoint (server to server, using `IDP_INTERNAL_URL` in Docker).
4. `validate_id_token` checks the signature using the configured JWKS URL, `alg=RS256`, `kid` selection, `iss`, `aud`, `exp`, and `nonce`.
5. The email must be verified, and an existing account linked to a different external subject is rejected.
6. The user is provisioned if needed (organization JIT settings), and a session is issued.

The configuration lives in the organization's `integration_configs` row of kind `oidc` (client ID, secret, authorize/token/JWKS URLs, issuer, redirect URI).

## Key retrieval

Keys come only from the configured JWKS URL. The URL is administrator-controlled and may point at a private address; link-local and metadata addresses are always blocked. A `jku` header in a token is ignored in the secure configuration.

## Synthetic IdP

`idp/main.py` implements authorize, token, userinfo, discovery and JWKS for a small directory of synthetic users. Password for all: `Idp#Pass2026`. `temp.contractor@northwind.test` has an unverified email for account-linking exercises. When `IDP_LAB_TOOLS=1`, `POST /lab/oidc/issue` mints ID tokens with arbitrary claims for validation testing; disable it with `IDP_LAB_TOOLS=0`.

## Toggles and test cases

`oidc_validation`, `oidc_nonce`, `oidc_linking`, `oidc_jku`, `oauth_state`; `TC-OIDC-001` to `TC-OIDC-005`.
