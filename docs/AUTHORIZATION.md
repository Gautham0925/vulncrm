# Authorization

Authorization is enforced on the backend in three layers. The UI hides actions a role cannot use, but never relies on that.

1. **Permission** (function level). Each route declares `require("customers.write")` and similar. Roles are sets of permissions.
2. **Scope** (object level). Each role has a scope level: `org`, `team` or `own`. `scoped()` filters queries by organization and, for team and own levels, by owner or team membership. `get_or_404()` resolves a single record through the same filter and returns 404 for anything out of scope.
3. **Property level.** Update handlers use allow-lists per role. Manager-controlled fields (approval status, approver, owner, probability, stage) are ignored for representatives. Response serializers omit compensation, internal notes and credential material unless the role holds the matching permission.

## Roles

System roles (organization-defined roles can also be created with a subset of the creator's own permissions):

| Role | Scope | Permissions |
|---|---|---|
| Super Administrator (`super_admin`) | org | customers.read, customers.write, customers.delete, customers.reassign, leads.read, leads.write, leads.assign, leads.convert, opportunities.read, opportunities.write, opportunities.approve, employees.read, employees.manage, teams.manage, documents.read, documents.write, documents.share, tickets.read, tickets.write, tickets.escalate, reports.read, reports.export, integrations.manage, oauth.manage, sso.manage, org.manage, roles.manage, audit.read, platform.manage, testlib.read, testlib.manage |
| Organization Administrator (`org_admin`) | org | customers.read, customers.write, customers.delete, customers.reassign, leads.read, leads.write, leads.assign, leads.convert, opportunities.read, opportunities.write, opportunities.approve, employees.read, employees.manage, teams.manage, documents.read, documents.write, documents.share, tickets.read, tickets.write, tickets.escalate, reports.read, reports.export, integrations.manage, oauth.manage, sso.manage, org.manage, roles.manage, audit.read, testlib.read |
| Sales Manager (`sales_manager`) | team | customers.read, customers.write, customers.reassign, leads.read, leads.write, leads.assign, leads.convert, opportunities.read, opportunities.write, opportunities.approve, employees.read, documents.read, documents.write, documents.share, tickets.read, reports.read, reports.export |
| Sales Representative (`sales_rep`) | own | customers.read, customers.write, leads.read, leads.write, leads.convert, opportunities.read, opportunities.write, documents.read, documents.write, tickets.read, reports.read |
| Support Agent (`support_agent`) | org | customers.read, tickets.read, tickets.write, tickets.escalate, documents.read, documents.write |
| Auditor (`auditor`) | org | customers.read, leads.read, opportunities.read, employees.read, documents.read, tickets.read, reports.read, audit.read, testlib.read, audit.read, reports.export |
| Integration Developer (`integration_dev`) | org | integrations.manage, oauth.manage, customers.read, reports.read, documents.read |
## Business rules enforced server-side

- Deals above $50,000 net of discount, or with discounts over 15%, need manager approval before `closed_won`. Changing amount or discount after approval returns the deal to pending. Owners cannot approve their own deals.
- Stages advance one step at a time; closed deals cannot be reopened.
- Only qualified leads that the caller owns can be converted, once.
- Reassigning customers or leads, changing roles, deactivating members and changing organization settings need the matching management permission, and a role cannot grant permissions above the actor's own.
- Documents are visible to the owner, shared members, and by visibility level (`private`, `team`, `organization`). Writes need write access; ownership transfer needs the owner or share permission and a same-tenant target.

## Where it lives

`backend/app/rbac.py` (roles and permissions), `backend/app/deps.py` (`require`, `scoped`, `get_or_404`), and the per-module routers. Tests: `backend/tests/test_core.py`, `test_oauth_graphql_files.py`; browser tests in `e2e/tests`.
