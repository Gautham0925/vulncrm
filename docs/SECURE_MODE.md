# Secure configuration

`SECURITY_MODE=secure` (the default) disables every toggle regardless of other settings. It is the baseline for comparing behavior and for regression testing.

## Controls

| Area | Behavior |
|---|---|
| Passwords | ≥ 12 characters with upper case and digits; bcrypt; generic login errors |
| Throttling | 10 logins / 5 min per client, 5 / 15 min per account; forwarding headers ignored |
| Sessions | Opaque server-side, 12 h, rotated at login, revoked on logout/password change; `HttpOnly`, `SameSite=Lax` |
| CSRF | `vc_csrf` cookie plus `X-CSRF-Token` required on cookie-authenticated writes |
| MFA | Email OTP, 5 attempts, 5 min |
| Reset | 256-bit single-use token, 30 min, no account disclosure |
| Authorization | Permission + object scope + property allow-lists on every route; 404 for out-of-scope objects |
| Business rules | Approval for deals > $50,000 net or > 15% discount, single-step stages, one-time conversion |
| API | Per-role field filtering, no verbose errors, no method override, no legacy routes, hashed API keys |
| GraphQL | Introspection off, depth/cost/alias/batch limits, field and mutation authorization |
| OAuth | Exact redirect match, PKCE for public clients, code single use, refresh rotation, scope intersection |
| OIDC | Full ID-token validation, nonce, verified email for linking, configured JWKS only |
| SAML | Signature against configured cert, signed-element-only, issuer/audience/recipient/destination, time window, replay, InResponseTo, signed SLO |
| Files | ≤ 10 MB, extension and content-type allow-list, generated names, no execution or inline HTML, authorization per download |
| Web | Strict CSP, `nosniff`, frame restrictions, no open redirects, output encoding, CORS allow-list |
| SSRF | Private, loopback, link-local and metadata destinations blocked; redirects re-checked |
| Audit | Security-relevant events recorded with actor, org, IP and object |

## Verification

Backend tests run with the secure configuration by default; `e2e/tests/modes.spec.ts` runs the same workflows against both configurations and asserts the secure one rejects each tested weakness.
