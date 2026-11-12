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
