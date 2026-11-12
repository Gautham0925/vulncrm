# Docker setup

```bash
cp .env.vulnerable.example .env     # training configuration
docker compose up --build
# or
cp .env.secure.example .env         # secure configuration
docker compose up --build
```

Open http://localhost:8080. The synthetic IdP is on http://localhost:9000. Both are bound to `127.0.0.1` only.

## Services

| Service | Image | Networks | Published |
|---|---|---|---|
| `nginx` | nginx:1.27 | app, edge | 127.0.0.1:8080 |
| `frontend` | built from `frontend/Dockerfile` | app | no |
| `backend` | built from `backend/Dockerfile` | app, data, lab | no |
| `postgres` | postgres:16 | data | no |
| `idp` | built from `idp/Dockerfile` | lab, edge | 127.0.0.1:9000 |
| `connector` | built from `node-service/Dockerfile` | lab | no |
| `mongo` | mongo:7 (profile `mongo`, optional) | lab | no |

`app`, `data` and `lab` are Docker `internal` networks with no outbound route. Only `edge` reaches the host. The backend runs as a non-root user and applies migrations on start (`RUN_MIGRATIONS=1`).

## Single container (for example a PaaS)

The root `Dockerfile` builds the frontend and serves it from the backend on `$PORT`. Provide `DATABASE_URL`, `PUBLIC_BASE_URL`, and `SECURITY_MODE`. Without an IdP and connector, SSO login and the connector tab report that the service is unavailable. Do not publish the vulnerable configuration on a public host.

## Data

Named volumes: `pgdata`, `uploads`, `keys`, `idpcerts`. Reset everything with `docker compose down -v`.

## Notes

- Rate limiting is in-process, so no Redis service is provided.
- The Mongo service is not required: the connector uses an in-memory Mongo-style matcher. The profile exists for exercises that replace it.

## Single-link hosting (Render free tier)

`render.yaml` deploys one container (API plus built frontend) in the vulnerable training configuration behind a shared lab password.

1. In Render choose **New → Blueprint**, connect `Gautham0925/vulncrm`, and apply `render.yaml`.
2. When prompted, set `LAB_GATE_PASSWORD` to the password you will share with learners.
3. Share the `https://…onrender.com` link. Visitors enter the lab password once, then sign in with the seeded accounts.

Notes:

- With `LAB_GATE_PASSWORD` set, every request except `/api/health` needs the gate cookie (or an `X-Lab-Key` header carrying the password, for proxies and scripts). Leave it unset for local use.
- The database is SQLite on the container's ephemeral disk; it reseeds on every restart or redeploy, which also resets lab data.
- The synthetic IdP is embedded under `/idp` (`EMBED_IDP=1`), so SAML and OIDC sign-in work on the same link. Its lab tools are at `/idp/lab/saml/issue` and `/idp/lab/oidc/issue`. The Node connector is not included, so Node/NoSQL scenarios need the full `docker compose` stack.
- Requests from inside the container (the OIDC token exchange) bypass the password gate; requests arriving through the platform proxy do not.
- The free tier sleeps when idle; the first request after a pause takes about a minute.
- All learners share one dataset and one process (and its rate limits).

- Set `SUPERADMIN_PASSWORD` (any environment) to give `superadmin@vulncrm.test` its own password instead of the shared seed password. It is applied when the account is first seeded, so on Render it takes effect on the next deploy.
