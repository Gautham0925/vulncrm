# Installation

## Requirements

Python 3.12, Node.js 20 or newer, and `libxml2`/`libxmlsec1` system libraries for SAML signing (present on most distributions). PostgreSQL 16 is optional.

## Backend

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

By default the backend uses SQLite (`./vulncrm.db`), creates tables, generates signing keys in `./keys`, and seeds synthetic data on first start (`SEED_ON_START=true`).

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `SECURITY_MODE` | `vulnerable` | `vulnerable` or `secure` |
| `ENVIRONMENT` | `local` | Must be `local`, `training`, `development` or `test` for any weakness to activate |
| `TRAINING_ACK` | `true` | Explicit acknowledgement required to activate weaknesses |
| `VULN_DISABLE` | empty | Comma-separated toggles to switch off |
| `DATABASE_URL` | `sqlite:///./vulncrm.db` | `postgresql://user:pass@host/db` also supported |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | Used for SAML/OIDC URLs and the `Secure` cookie attribute |
| `CORS_ORIGINS` | `http://localhost:5173` | Allow-list used in the secure configuration |
| `IDP_BASE_URL` | `http://localhost:9000` | Browser-facing IdP URL |
| `IDP_INTERNAL_URL` | empty | Server-side IdP URL (defaults to `IDP_BASE_URL`) |
| `NODE_SERVICE_URL` | `http://localhost:3100` | Connector service |
| `UPLOAD_DIR`, `KEYS_DIR`, `IDP_CERT_DIR`, `STATIC_DIR` | `./uploads`, `./keys`, `./idp-certs`, `./static` | Storage paths |
| `SEED_ON_START` | `true` | Seed synthetic data when the database is empty |
| `RATE_LIMIT_MULTIPLIER` | `1` | Test harnesses may raise throttling ceilings; leave at 1 otherwise |
| `ACCESS_TTL_SECONDS`, `SESSION_TTL_HOURS`, `BCRYPT_ROUNDS` | 3600, 12, 10 | Token and session tuning |

### Migrations

```bash
cd backend && alembic upgrade head
```

`alembic check` reports no drift between models and the migration. Generate new revisions with `alembic revision --autogenerate -m "message"`.

## Frontend

```bash
cd frontend
npm ci
npm run dev          # http://localhost:5173, proxies API routes to :8000
npm run build        # output in dist/, served by the backend via STATIC_DIR
```

## Synthetic IdP and connector

```bash
cd idp && pip install -r requirements.txt && IDP_CERT_DIR=./idp-certs uvicorn main:app --port 9000
cd node-service && CONNECTOR_TRAINING=1 node server.js
```

The IdP and the backend must share `IDP_CERT_DIR` so that the SAML configuration seeded into the backend contains the IdP's signing certificate.

## Running both configurations side by side

```bash
SECURITY_MODE=vulnerable uvicorn app.main:app --port 8000
SECURITY_MODE=secure PUBLIC_BASE_URL=http://localhost:8001 DATABASE_URL=sqlite:///./secure.db uvicorn app.main:app --port 8001
```
