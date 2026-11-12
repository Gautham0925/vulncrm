# Multi-tenancy

Every business record carries `org_id`. A user can belong to several organizations through `memberships`; each membership has its own role, team and manager.

## Active organization

The active organization is stored on the session and embedded in access JWTs (`org` claim). `POST /api/auth/switch-org` changes it after verifying a membership exists. The UI exposes this in the account menu for users with more than one membership. Super administrators can act in any organization.

## Isolation rules

- Queries are built from `scoped(query, model, principal)`, which adds `org_id = principal.org_id` and the role scope.
- Single-record lookups use `get_or_404`, returning 404 (not 403) for other tenants, so record existence is not disclosed.
- Reports accept a `target_org` only for platform administrators.
- File storage is partitioned by organization, and download authorization is checked per request.
- API keys, OAuth clients, webhooks, integration configs, SSO configuration and audit logs are organization scoped.
- GraphQL resolvers reuse the same scoping.
- The Node connector receives the organization in `X-Org-Id` and scopes lookups.

## Seed data

Northwind Traders, Contoso Health and Globex Logistics each have their own users, customers, deals, tickets and documents. `consultant@vulncrm.test` belongs to Northwind and Contoso for switching tests.

## Test coverage

`test_core.py::test_cross_tenant_customer` and `e2e/tests/modes.spec.ts` verify that cross-tenant reads return 404 in the secure configuration and succeed only in the vulnerable one (`bola`).
