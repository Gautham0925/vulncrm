PERMISSIONS = {
    "customers.read": "View customers", "customers.write": "Create and edit customers", "customers.delete": "Delete customers",
    "customers.reassign": "Reassign customer ownership",
    "leads.read": "View leads", "leads.write": "Create and edit leads", "leads.assign": "Assign leads", "leads.convert": "Convert leads",
    "opportunities.read": "View opportunities", "opportunities.write": "Create and edit opportunities", "opportunities.approve": "Approve deals",
    "employees.read": "View employees", "employees.manage": "Manage employees",
    "teams.manage": "Manage teams",
    "documents.read": "View documents", "documents.write": "Upload and edit documents", "documents.share": "Share documents",
    "tickets.read": "View tickets", "tickets.write": "Create and edit tickets", "tickets.escalate": "Escalate tickets",
    "reports.read": "View reports", "reports.export": "Export reports",
    "integrations.manage": "Manage API clients, keys, webhooks and integrations",
    "oauth.manage": "Manage OAuth applications",
    "sso.manage": "Configure SSO",
    "org.manage": "Manage organization settings",
    "roles.manage": "Manage roles and permissions",
    "audit.read": "View audit logs",
    "platform.manage": "Manage the platform and all organizations",
    "testlib.read": "View security test case library",
    "testlib.manage": "Manage security test case library",
}

ALL = list(PERMISSIONS)
READ = [p for p in ALL if p.endswith(".read")]

SYSTEM_ROLES = {
    "super_admin": ("Super Administrator", "Manages the platform and every organization", ALL, "org"),
    "org_admin": ("Organization Administrator", "Manages their own organization", [p for p in ALL if p not in ("platform.manage", "testlib.manage")], "org"),
    "sales_manager": ("Sales Manager", "Manages sales teams and approves deals", [
        "customers.read", "customers.write", "customers.reassign", "leads.read", "leads.write", "leads.assign", "leads.convert",
        "opportunities.read", "opportunities.write", "opportunities.approve", "employees.read", "documents.read", "documents.write",
        "documents.share", "tickets.read", "reports.read", "reports.export"], "team"),
    "sales_rep": ("Sales Representative", "Works assigned customers, leads and deals", [
        "customers.read", "customers.write", "leads.read", "leads.write", "leads.convert", "opportunities.read", "opportunities.write",
        "documents.read", "documents.write", "tickets.read", "reports.read"], "own"),
    "support_agent": ("Support Agent", "Handles customer support tickets", [
        "customers.read", "tickets.read", "tickets.write", "tickets.escalate", "documents.read", "documents.write"], "org"),
    "auditor": ("Auditor", "Read-only access for compliance reviews", READ + ["audit.read", "reports.export"], "org"),
    "integration_dev": ("Integration Developer", "Manages integrations and API clients", [
        "integrations.manage", "oauth.manage", "customers.read", "reports.read", "documents.read"], "org"),
}

SCOPE_LEVEL = {k: v[3] for k, v in SYSTEM_ROLES.items()}

OAUTH_SCOPES = {
    "openid": "Sign in with your identity", "profile": "Basic profile", "email": "Email address",
    "customers:read": "Read customers", "customers:write": "Write customers", "leads:read": "Read leads", "leads:write": "Write leads",
    "opportunities:read": "Read opportunities", "reports:read": "Read reports", "documents:read": "Read documents",
    "admin": "Administrative access",
}


def perm_to_scope(p: str) -> str:
    return p.replace(".", ":")
