# Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Vulnerable behavior not appearing | All three activation variables must match exactly (see VULNERABLE_MODE.md). Check `/api/health`. |
| 429 during automated testing | Rate limits are per process. Restart the backend or set `RATE_LIMIT_MULTIPLIER` for a test harness. |
| 403 on writes from scripts | Secure configuration requires `X-CSRF-Token` for cookie sessions; use a Bearer token or API key. |
| OIDC login fails with a connection error in Docker | Set `IDP_INTERNAL_URL` to the service name URL (`http://idp:9000`). |
| SAML assertion rejected | Compare IdP entity ID, SP entity ID and ACS URL with the SSO settings; check clock skew. |
| Alembic reports missing tables | Run `alembic upgrade head`,. |
| Uploads fail | Size ≤ 10 MB and an allowed extension; `UPLOAD_DIR` must be writable. |
| Frontend cannot reach the API | Vite proxies to `:8000`; check the backend is running. In Docker the nginx container proxies `/api`. |
| Emails/OTP not arriving | Open `/dev/mailbox`; there is no external mail. |
| Multiple backend replicas misbehave | Rate limits and some caches are in-process; run a single replica. |
| Docker build fails | Images were validated by configuration only in the authoring environment; report errors with `docker compose build` output. |
