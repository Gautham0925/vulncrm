# Authentication

## Credential types

| Type | Format | Used for | Lifetime |
|---|---|---|---|
| Session cookie | opaque `vc_session` (server-side `auth_sessions` row) | Browser UI | 12 hours |
| CSRF token | `vc_csrf` cookie echoed in `X-CSRF-Token` | Cookie-authenticated writes (enforced in the secure configuration) | session |
| Access JWT | RS256, `kid` header, `typ=user`, audience `vulncrm-api` | API calls (`Authorization: Bearer`) | 1 hour |
| API key | `vck_…`, stored as SHA-256 hash | Server-to-server | per key, default 90 days |
| OAuth token | `vco_…`, hashed | Third-party apps | access 1 hour, refresh 30 days |

Public signing keys are published at `/oidc/jwks.json`.

## Login flow

1. `GET /api/auth/session-init` issues an anonymous session and CSRF cookie.
2. `POST /api/auth/login` with email and password. Passwords are bcrypt hashes.
3. If the user has MFA enabled, the response contains `mfa_required` and a `challenge_id`. A six-digit code is delivered to the development mailbox (`/dev/mailbox`) and verified with `POST /api/auth/verify-otp` (5 attempts per challenge, 5 minute expiry).
4. A fresh session identifier is issued at successful login, and the response carries the user, organization, role and permissions.
5. `POST /api/auth/logout` revokes the server-side session.

Other endpoints: `/api/auth/me`, `/api/auth/switch-org`, `/api/auth/sessions` (list and revoke), `/api/auth/forgot-password`, `/api/auth/reset-password`, `/api/auth/change-password`.

## Single sign-on

SAML 2.0 and OpenID Connect sign-in are available per organization. See [SAML_IMPLEMENTATION.md](SAML_IMPLEMENTATION.md) and [OIDC_IMPLEMENTATION.md](OIDC_IMPLEMENTATION.md).

## Secure configuration controls

- Login throttling: 10 attempts per 5 minutes per client address and 5 per 15 minutes per account. Client-supplied forwarding headers are ignored.
- Generic failure messages that do not reveal whether an account exists.
- Password policy: at least 12 characters with upper case letters and digits.
- Reset tokens: 256-bit random, single use, 30 minutes.
- Session rotation at login; sessions are revoked on logout and password change.
- `HttpOnly`, `SameSite=Lax` cookies (and `Secure` when `PUBLIC_BASE_URL` is https).

The vulnerable configuration relaxes these individually (`auth_enum`, `auth_lockout`, `otp_bruteforce`, `weak_reset`, `session_fixation`, `session_handling`, `rate_limit`, `csrf`). See [VULNERABLE_MODE.md](VULNERABLE_MODE.md).
