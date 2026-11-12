# VULNCRM

**Manage Relationships. Secure Every Interaction.**

VULNCRM is an enterprise-style CRM SaaS used as a realistic target for **authorized** web, API, authentication and authorization testing. It is a working product: customers, leads, a sales pipeline, support tickets, documents, reports, employees and teams, API and OAuth management, SSO, and audit logs.

It is **not a CTF**. There are no flags, scores, leaderboards or challenge screens. Weaknesses exist inside real business workflows and only in an isolated *vulnerable training configuration*. A *secure configuration* of the same code base is provided for comparison and regression testing.

> Never expose the vulnerable configuration to the internet or to untrusted networks. All data is synthetic.

## Quick start (no Docker)

```bash
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
cd ../frontend && npm ci && npm run build
cd ../backend && STATIC_DIR=../frontend/dist uvicorn app.main:app --port 8000
# optional, in separate terminals (needed for SSO and the data connector)
cd idp && pip install -r requirements.txt && uvicorn main:app --port 9000
cd node-service && CONNECTOR_TRAINING=1 node server.js
```

Open http://localhost:8000. The first start creates the SQLite database and seeds synthetic data.

## Quick start (Docker)

```bash
cp .env.vulnerable.example .env      # or .env.secure.example
docker compose up --build
```

Open http://localhost:8080. See [Docker setup](docs/DOCKER_SETUP.md).

## Seeded accounts

All CRM accounts use the password `Crm#Pass2026`. The synthetic identity provider uses `Idp#Pass2026`.

| Account | Role | Notes |
|---|---|---|
| `superadmin@vulncrm.test` | Super Administrator | Every organization, platform admin, test library management |
| `admin@northwind.test` | Organization Administrator | Has email MFA (codes appear in `/dev/mailbox`) |
| `manager@northwind.test` | Sales Manager | Approves deals |
| `rep1@northwind.test`, `rep2@northwind.test` | Sales Representative | Own-record scope |
| `support@northwind.test` | Support Agent | Ticket queue |
| `auditor@northwind.test` | Auditor | Read-only plus audit logs |
| `dev@northwind.test` | Integration Developer | API clients, OAuth apps |
| `admin@contoso.test`, `rep1@contoso.test` | Contoso Health | Second tenant |
| `consultant@vulncrm.test` | Member of two organizations | Tenant-switching |

Organizations: Northwind Traders, Contoso Health, Globex Logistics, and the VULNCRM Platform.

## Documentation

| Topic | File |
|---|---|
| Architecture | [ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Installation | [INSTALLATION.md](docs/INSTALLATION.md) |
| Docker | [DOCKER_SETUP.md](docs/DOCKER_SETUP.md) |
| Database | [DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) |
| REST and GraphQL API | [API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md) |
| Authentication | [AUTHENTICATION.md](docs/AUTHENTICATION.md) |
| Authorization | [AUTHORIZATION.md](docs/AUTHORIZATION.md) |
| Multi-tenancy | [MULTI_TENANCY.md](docs/MULTI_TENANCY.md) |
| OAuth 2.0 | [OAUTH_IMPLEMENTATION.md](docs/OAUTH_IMPLEMENTATION.md) |
| OpenID Connect | [OIDC_IMPLEMENTATION.md](docs/OIDC_IMPLEMENTATION.md) |
| SAML 2.0 | [SAML_IMPLEMENTATION.md](docs/SAML_IMPLEMENTATION.md) |
| Security test case library | [SECURITY_TEST_CASES.md](docs/SECURITY_TEST_CASES.md) |
| Vulnerable configuration | [VULNERABLE_MODE.md](docs/VULNERABLE_MODE.md) |
| Secure configuration | [SECURE_MODE.md](docs/SECURE_MODE.md) |
| Troubleshooting | [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) |
| Development | [DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md) |

## Tests

```bash
cd backend && python -m pytest -q          # 35+ tests, both configurations
cd node-service && npm test                # connector service
cd frontend && npm test                    # component tests
cd e2e && npm run test:vulnerable          # Playwright against :8000
cd e2e && npm run test:secure              # Playwright against :8001
```

## Intended use

Use VULNCRM only on systems you own or are explicitly authorized to test, on isolated networks, for training, tooling evaluation and regression testing. The security test case library documents what to verify and how a secure implementation behaves; it contains no automation claims.
