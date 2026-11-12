# Architecture

```
Browser ──► Nginx (compose) ──► Frontend static assets (React)
                         └────► Backend (FastAPI)  ──► PostgreSQL / SQLite
                                   │  │
                                   │  └──► Connector service (Node.js, isolated "lab" network)
                                   └─────► Synthetic IdP (SAML 2.0 + OIDC)
```

| Component | Technology | Port | Notes |
|---|---|---|---|
| Backend | FastAPI, SQLAlchemy, Alembic | 8000 | REST, GraphQL, OAuth server, SAML SP, OIDC relying party |
| Frontend | React, TypeScript, Vite, Tailwind, TanStack Query, React Hook Form, Zod, Recharts | 5173 (dev) | Served by the backend in single-container mode |
| Synthetic IdP | FastAPI, signxml | 9000 | Signs SAML assertions and issues OIDC tokens for synthetic users |
| Connector | Node.js (no dependencies) | 3100 | Data-sync connector with a Mongo-style query layer |
| Database | PostgreSQL 16 (compose) or SQLite | 5432 | 36 tables, migrated with Alembic |

## Request path

1. The middleware stack applies CORS, security headers, method-override handling and API request logging. Behavior differs per configuration.
2. `current_principal` resolves the caller from a session cookie, bearer JWT, `vck_` API key or `vco_` OAuth token, into a `Principal` (user, membership, organization, role, permissions, scope level).
3. Routes declare permissions with `require("permission.name")`.
4. Data access goes through `scoped()` and `get_or_404()`, which apply organization and role-scope filters.
5. Mutations write an audit record with secrets redacted.

## Configuration switch

`app/mode.py` exposes `mode()` and `vuln(flag)`. A weakness is active only when **all** are true: `SECURITY_MODE=vulnerable`, `ENVIRONMENT` is one of `local`, `training`, `development`, `test`, and `TRAINING_ACK=true`. Individual weaknesses can be disabled with `VULN_DISABLE`. See [VULNERABLE_MODE.md](VULNERABLE_MODE.md).

## Modules

Dashboard, customers, leads, pipeline (stages, forecast, approvals), tickets, documents (versions, sharing), reports (CSV, PDF, print view), employees, teams, roles, API clients and keys, webhooks, connector, OAuth applications, SSO, audit, organization settings, platform administration, security test case library.

## Isolation

In Docker Compose the backend, database and connector sit on internal networks. Only Nginx (8080) and the synthetic IdP (9000) are published, on `127.0.0.1`. See [DOCKER_SETUP.md](DOCKER_SETUP.md).

## Process-local state

Rate limiting, the SAML assertion replay cache (also persisted in `saml_assertions_seen`) and webhooks dispatch run inside the backend process. Run a single backend replica.
