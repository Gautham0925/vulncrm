import os
import random
import uuid
from datetime import timedelta

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app.idp_lib import IDP_ENTITY_ID, load_or_create
from app.models import (Activity, ApiClient, ApiKey, AuditLog, Customer, CustomerContact, Document, DocumentPermission, DocumentVersion, IntegrationConfig, Lead, Membership, Notification, OAuthClient,
                        Opportunity, Organization, Permission, Role, SamlConfig, Team, Ticket, TicketComment, User, Webhook, now)
from app.mode import mode
from app.rbac import PERMISSIONS, SYSTEM_ROLES
from app.security import ensure_keys, hash_password, sha256

settings = get_settings()
OIDC_CLIENT_ID, OIDC_CLIENT_SECRET = "vc_northwind_oidc", "oidc-demo-secret-northwind"
SEED_API_KEY = "vck_a1b2c3d4northwind-demo-key"
PARTNER_ID, PARTNER_SECRET = "vc_partner_portal", "vcs_northwind_partner_secret_demo"
MOBILE_ID, SYNC_ID, SYNC_SECRET = "vc_mobile_app", "vc_data_sync", "vcs_northwind_data_sync_secret_demo"

COMPANIES = [("Acme Industrial Supply", "Manufacturing"), ("Bluepeak Software", "Technology"), ("Cedar Ridge Hospital", "Healthcare"), ("Delta Freight Lines", "Logistics"), ("Evergreen Foods", "Retail"),
             ("Fjord Energy", "Energy"), ("Granite Capital", "Finance"), ("Harbor Retail Group", "Retail"), ("Ironwood Construction", "Construction"), ("Juniper Analytics", "Technology"),
             ("Keystone Insurance", "Finance"), ("Lumen Education", "Education"), ("Meridian Pharma", "Healthcare"), ("Northstar Aviation", "Aerospace"), ("Orchid Hospitality", "Hospitality")]
FIRST = ["Priya", "Daniel", "Maria", "Kenji", "Sofia", "Omar", "Hannah", "Liam", "Aisha", "Mateo", "Chloe", "Ravi", "Elena", "Noah", "Zara", "Lucas"]
LAST = ["Shah", "Brooks", "Garcia", "Tanaka", "Rossi", "Haddad", "Meyer", "Walsh", "Khan", "Silva", "Dubois", "Nair", "Petrov", "Quinn", "Ali", "Moreau"]
SOURCES = ["web", "referral", "event", "partner", "outbound", "webinar"]


def seed_roles(db):
    for k, d in PERMISSIONS.items():
        if not db.query(Permission).filter(Permission.key == k).first():
            db.add(Permission(key=k, description=d))
    for key, (name, desc, perms, _) in SYSTEM_ROLES.items():
        r = db.query(Role).filter(Role.key == key, Role.org_id.is_(None)).first()
        if not r:
            db.add(Role(org_id=None, key=key, name=name, description=desc, permissions=perms, system=True))
        else:
            r.permissions = perms
    db.flush()


def make_pdf(path: str, title: str, lines: list[str]):
    c = canvas.Canvas(path, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, 720, title)
    c.setFont("Helvetica", 11)
    y = 690
    for l in lines:
        c.drawString(72, y, l)
        y -= 18
    c.save()


def person(db, org, role, email, name, team=None, title=None, dept=None, mfa=False, manager=None, salary=None, color="#4F46E5"):
    u = db.query(User).filter(User.email == email).first()
    if not u:
        u = User(email=email, name=name, password_hash=hash_password(settings.superadmin_password if email == "superadmin@vulncrm.test" and settings.superadmin_password else settings.seed_password), mfa_enabled=mfa, avatar_color=color)
        db.add(u)
        db.flush()
    m = Membership(user_id=u.id, org_id=org.id, role_id=role.id, team_id=team.id if team else None, title=title, department=dept, salary=salary, manager_id=manager.id if manager else None,
                   phone=f"+1-555-01{random.randint(10, 99)}", internal_notes="Performance review: on track" if salary else None)
    db.add(m)
    db.flush()
    return m


def seed_org(db, rnd, org, roles, staff, with_extras=False):
    ts = now()
    teams = {}
    for tname, dept in (("Enterprise Sales", "Sales"), ("SMB Sales", "Sales"), ("Customer Support", "Support")):
        t = Team(org_id=org.id, name=tname, department=dept)
        db.add(t)
        db.flush()
        teams[tname] = t
    members = {}
    colors = ["#4F46E5", "#0891B2", "#16A34A", "#D97706", "#DB2777", "#7C3AED"]
    for i, (role_key, email, name, tname, title) in enumerate(staff):
        m = person(db, org, roles[role_key], email, name, teams.get(tname), title, "Sales" if "sales" in role_key else None, mfa=email.startswith("admin@northwind"), salary=round(rnd.uniform(62000, 148000), -2), color=colors[i % 6])
        members[email] = m
    mgr = next((m for e, m in members.items() if e.startswith("manager@")), None)
    if mgr:
        teams["Enterprise Sales"].manager_id = mgr.id
        teams["SMB Sales"].manager_id = mgr.id
        for e, m in members.items():
            if e.startswith("rep"):
                m.manager_id = mgr.id
    reps = [m for e, m in members.items() if e.startswith("rep")] or [mgr or next(iter(members.values()))]
    sup = next((m for e, m in members.items() if e.startswith("support")), reps[0])
    customers = []
    for i, (cname, ind) in enumerate(COMPANIES[: 12 if with_extras else 8]):
        owner = reps[i % len(reps)]
        c = Customer(org_id=org.id, name=cname, email=f"info@{cname.lower().split()[0]}.example", phone=f"+1-555-02{i:02d}", industry=ind, company=cname, website=f"https://{cname.lower().split()[0]}.example",
                     address=f"{100 + i * 7} Market Street", status=rnd.choice(["active", "active", "active", "prospect", "inactive"]), tier=rnd.choice(["standard", "gold", "platinum"]), owner_id=owner.id,
                     notes="Quarterly business review scheduled." if i % 3 == 0 else None, internal_notes="Negotiated custom payment terms (net-45).", credit_limit=float(rnd.choice([25000, 50000, 100000, 250000])), tax_id=f"TX-{rnd.randint(100000, 999999)}")
        c.created_at = ts - timedelta(days=rnd.randint(10, 400))
        db.add(c)
        db.flush()
        customers.append(c)
        for j in range(rnd.randint(1, 2)):
            n = f"{rnd.choice(FIRST)} {rnd.choice(LAST)}"
            db.add(CustomerContact(org_id=org.id, customer_id=c.id, name=n, email=f"{n.split()[0].lower()}@{cname.lower().split()[0]}.example", phone=f"+1-555-03{rnd.randint(10, 99)}", title=rnd.choice(["Procurement Lead", "CTO", "Operations Manager", "Finance Director"]), primary=j == 0))
        db.add(Activity(org_id=org.id, entity_type="customer", entity_id=c.id, kind="note", subject="Kickoff call", body="Discussed requirements and timeline. Customer is evaluating two vendors.", actor_id=owner.id, created_at=ts - timedelta(days=rnd.randint(1, 60))))
        db.add(Activity(org_id=org.id, entity_type="customer", entity_id=c.id, kind="email", subject="Proposal follow-up", body="Sent pricing sheet and asked for a decision date.", actor_id=owner.id, created_at=ts - timedelta(days=rnd.randint(1, 30))))
    stages = ["prospecting", "qualification", "proposal", "negotiation", "closed_won", "closed_won", "closed_lost"]
    probs = {"prospecting": 10, "qualification": 25, "proposal": 50, "negotiation": 75, "closed_won": 100, "closed_lost": 0}
    opps = []
    for i in range(14 if with_extras else 9):
        c = customers[i % len(customers)]
        stage = stages[i % len(stages)]
        amount = float(rnd.choice([8000, 12500, 24000, 36000, 54000, 72000, 118000]))
        o = Opportunity(org_id=org.id, customer_id=c.id, name=f"{c.name} – {rnd.choice(['Platform subscription', 'Annual renewal', 'Expansion', 'Pilot rollout', 'Support plan'])}", amount=amount, discount_pct=float(rnd.choice([0, 5, 10, 18])),
                        stage=stage, probability=probs[stage], expected_close=ts + timedelta(days=rnd.randint(-20, 90)), owner_id=c.owner_id)
        o.approval_status = "approved" if stage == "closed_won" and amount > 50000 else ("pending" if stage == "negotiation" and amount > 50000 else "not_required")
        o.approved_by = mgr.id if o.approval_status == "approved" and mgr else None
        if stage in ("closed_won", "closed_lost"):
            o.closed_at = ts - timedelta(days=rnd.randint(2, 170))
        db.add(o)
        db.flush()
        opps.append(o)
        db.add(Activity(org_id=org.id, entity_type="opportunity", entity_id=o.id, kind="system", subject="Opportunity created", actor_id=o.owner_id, created_at=ts - timedelta(days=rnd.randint(20, 120))))
    for i in range(10 if with_extras else 7):
        st = rnd.choice(["new", "contacted", "qualified", "qualified", "disqualified", "new"])
        n = f"{rnd.choice(FIRST)} {rnd.choice(LAST)}"
        co = f"{rnd.choice(['Apex', 'Nimbus', 'Vertex', 'Solstice', 'Quarry', 'Beacon'])} {rnd.choice(['Labs', 'Partners', 'Group', 'Works'])}"
        l = Lead(org_id=org.id, name=n, email=f"{n.split()[0].lower()}@{co.split()[0].lower()}.example", phone=f"+1-555-04{rnd.randint(10, 99)}", company=co, source=rnd.choice(SOURCES), status=st,
                 qualification="sales_qualified" if st == "qualified" else None, score=rnd.randint(20, 95), estimated_value=float(rnd.choice([5000, 15000, 40000, 90000])), owner_id=rnd.choice(reps).id, created_by=reps[0].id)
        l.created_at = ts - timedelta(days=rnd.randint(1, 90))
        db.add(l)
    tickets = []
    subjects = ["Cannot export invoices to CSV", "Login loop after SSO change", "Webhook deliveries failing", "Request: bulk contact import", "Incorrect currency on quote", "Slow dashboard on large accounts", "Billing contact update", "API rate limit questions"]
    for i, s in enumerate(subjects[: 8 if with_extras else 5]):
        c = customers[(i * 2) % len(customers)]
        t = Ticket(org_id=org.id, customer_id=c.id, subject=s, description="Customer reported this through the support portal and needs an update.", priority=rnd.choice(["low", "medium", "high", "urgent"]),
                   status=rnd.choice(["open", "in_progress", "waiting", "resolved"]), assignee_id=sup.id, created_by=sup.id)
        t.created_at = ts - timedelta(days=rnd.randint(1, 45))
        db.add(t)
        db.flush()
        tickets.append(t)
        db.add(TicketComment(org_id=org.id, ticket_id=t.id, author_id=sup.id, body="Thanks for reporting this. We are looking into it and will update you shortly.", internal=False))
        db.add(TicketComment(org_id=org.id, ticket_id=t.id, author_id=sup.id, body="Internal: reproduced on staging; engineering ticket opened. Customer is on the platinum tier.", internal=True))
    root = os.path.abspath(settings.upload_dir)
    folder = os.path.join(root, f"org_{org.id}")
    os.makedirs(folder, exist_ok=True)
    docs = [("Master Services Agreement", "contract", "signed", "org", reps[0], customers[0]), ("Q4 Proposal – Platform Rollout", "proposal", "in_review", "shared", reps[0], customers[1]),
            ("Pricing Sheet 2026", "general", "approved", "org", mgr or reps[0], None), ("Private negotiation notes", "general", "draft", "private", reps[-1], customers[-1])]
    for name, kind, status, vis, owner, cust in docs:
        d = Document(org_id=org.id, name=name, kind=kind, visibility=vis, status=status, owner_id=owner.id, customer_id=cust.id if cust else None)
        db.add(d)
        db.flush()
        stored = f"{uuid.uuid4().hex}.pdf"
        make_pdf(os.path.join(folder, stored), name, [f"Organization: {org.name}", f"Prepared by: {owner.user.name}", "This is a synthetic training document with no real data.", f"Document #{d.id}"])
        db.add(DocumentVersion(document_id=d.id, version=1, original_name=name.replace(" ", "_") + ".pdf", stored_name=f"org_{org.id}/{stored}", content_type="application/pdf", size=os.path.getsize(os.path.join(folder, stored)), uploaded_by=owner.id))
        if vis == "shared" and len(reps) > 1:
            db.add(DocumentPermission(document_id=d.id, membership_id=reps[1].id, level="read", granted_by=owner.id))
    for m in members.values():
        db.add(Notification(org_id=org.id, membership_id=m.id, title="Welcome to VULNCRM", body="Your workspace is ready.", link="/dashboard"))
    for i in range(6):
        db.add(AuditLog(org_id=org.id, actor_user_id=reps[0].user_id, actor_label=reps[0].user.email, action=rnd.choice(["customer.update", "lead.create", "opportunity.stage", "document.upload"]), resource_type="customer", resource_id=str(i + 1), created_at=ts - timedelta(days=rnd.randint(1, 20))))
    return members, customers, opps


def run():
    Base.metadata.create_all(engine)
    ensure_keys()
    db = SessionLocal()
    try:
        seed_roles(db)
        if db.query(Organization).count() == 0:
            rnd = random.Random(42)
            roles = {r.key: r for r in db.query(Role).filter(Role.org_id.is_(None)).all()}
            plat = Organization(name="VULNCRM Platform", slug="platform", industry="Software", plan="platform")
            db.add(plat)
            db.flush()
            person(db, plat, roles["super_admin"], "superadmin@vulncrm.test", "Sam Rivera", title="Platform Administrator", color="#111827")
            specs = [
                ("Northwind Traders", "northwind", "Wholesale", [("org_admin", "admin@northwind.test", "Avery Collins", None, "Organization Administrator"), ("sales_manager", "manager@northwind.test", "Morgan Ellis", "Enterprise Sales", "Sales Manager"),
                         ("sales_rep", "rep1@northwind.test", "Riley Chen", "Enterprise Sales", "Account Executive"), ("sales_rep", "rep2@northwind.test", "Jordan Blake", "SMB Sales", "Account Executive"),
                         ("support_agent", "support@northwind.test", "Casey Murphy", "Customer Support", "Support Specialist"), ("auditor", "auditor@northwind.test", "Taylor Reed", None, "Compliance Auditor"),
                         ("integration_dev", "dev@northwind.test", "Quinn Foster", None, "Integration Engineer")], True),
                ("Contoso Health", "contoso", "Healthcare", [("org_admin", "admin@contoso.test", "Dana Whitfield", None, "Organization Administrator"), ("sales_manager", "manager@contoso.test", "Skyler Boone", "Enterprise Sales", "Sales Manager"),
                         ("sales_rep", "rep1@contoso.test", "Emerson Hale", "Enterprise Sales", "Account Executive"), ("support_agent", "support@contoso.test", "Rowan Pierce", "Customer Support", "Support Specialist"),
                         ("auditor", "auditor@contoso.test", "Parker Lowe", None, "Compliance Auditor")], False),
                ("Globex Logistics", "globex", "Logistics", [("org_admin", "admin@globex.test", "Harper Stone", None, "Organization Administrator"), ("sales_manager", "manager@globex.test", "Blair Nash", "Enterprise Sales", "Sales Manager"),
                         ("sales_rep", "rep1@globex.test", "Finley Gray", "Enterprise Sales", "Account Executive"), ("support_agent", "support@globex.test", "Sage Holt", "Customer Support", "Support Specialist")], False),
            ]
            created = {}
            for name, slug, ind, staff, extras in specs:
                o = Organization(name=name, slug=slug, industry=ind)
                db.add(o)
                db.flush()
                created[slug] = (o, *seed_org(db, rnd, o, roles, staff, extras))
            nw, nw_members, nw_customers, nw_opps = created["northwind"]
            ct = created["contoso"][0]
            consultant = person(db, nw, roles["sales_rep"], "consultant@vulncrm.test", "Jamie Okafor", None, "Channel Consultant")
            person(db, ct, roles["auditor"], "consultant@vulncrm.test", "Jamie Okafor", None, "External Auditor")
            custom = Role(org_id=nw.id, key="regional_lead", name="Regional Lead", description="Custom role for regional leads", permissions=["customers.read", "customers.write", "leads.read", "opportunities.read", "reports.read"])
            db.add(custom)
            admin_m = nw_members["admin@northwind.test"]
            dev_m = nw_members["dev@northwind.test"]
            client = ApiClient(org_id=nw.id, name="Zapier connector", description="Syncs new leads from marketing forms", scopes=["leads:read", "leads:write", "customers:read"], owner_id=dev_m.id)
            db.add(client)
            db.flush()
            db.add(ApiKey(org_id=nw.id, client_id=client.id, prefix=SEED_API_KEY[:12], key_hash=sha256(SEED_API_KEY), plaintext=SEED_API_KEY if mode() == "vulnerable" else None, scopes=["leads:read", "customers:read"]))
            db.add(OAuthClient(org_id=nw.id, client_id=PARTNER_ID, client_secret_hash=sha256(PARTNER_SECRET), client_secret_plain=PARTNER_SECRET if mode() == "vulnerable" else None, name="Partner Portal",
                               redirect_uris=["https://partners.northwind.test/callback"], grant_types=["authorization_code", "refresh_token"], scopes=["openid", "profile", "email", "customers:read", "reports:read"], require_pkce=False))
            db.add(OAuthClient(org_id=nw.id, client_id=MOBILE_ID, name="Mobile App", redirect_uris=["com.northwind.crm://oauth/callback"], grant_types=["authorization_code", "refresh_token"], scopes=["openid", "profile", "email", "customers:read", "leads:read"], public=True, require_pkce=True))
            db.add(OAuthClient(org_id=nw.id, client_id=SYNC_ID, client_secret_hash=sha256(SYNC_SECRET), client_secret_plain=SYNC_SECRET if mode() == "vulnerable" else None, name="Data Sync Service",
                               redirect_uris=[], grant_types=["client_credentials"], scopes=["customers:read", "opportunities:read", "reports:read"]))
            db.add(Webhook(org_id=nw.id, url=f"{settings.node_service_url}/hooks", events=["*"], secret="whsec_demo_northwind"))
            idp_dir = os.environ.get("IDP_CERT_DIR", "./idp-certs")
            _, cert = load_or_create(idp_dir)
            base = settings.public_base_url.rstrip("/")
            db.add(SamlConfig(org_id=nw.id, enabled=True, idp_entity_id=IDP_ENTITY_ID, sso_url=f"{settings.idp_base_url.rstrip('/')}/saml/sso", slo_url=f"{settings.idp_base_url.rstrip('/')}/saml/slo", x509_cert=cert.decode(),
                              sp_entity_id=f"{base}/saml/northwind/metadata", acs_url=f"{base}/saml/northwind/acs", jit_provisioning=True, default_role_key="sales_rep"))
            idp = settings.idp_base_url.rstrip("/")
            idp_internal = (settings.idp_internal_url or settings.idp_base_url).rstrip("/")
            db.add(IntegrationConfig(org_id=nw.id, kind="oidc", name="Corporate OpenID Connect", config={"issuer": f"{idp}/oidc", "client_id": OIDC_CLIENT_ID, "client_secret": OIDC_CLIENT_SECRET, "authorize_url": f"{idp}/oidc/authorize",
                                                                                                          "token_url": f"{idp_internal}/oidc/token", "jwks_url": f"{idp_internal}/oidc/jwks.json", "redirect_uri": f"{base}/api/auth/oidc/northwind/callback"}))
            db.add(IntegrationConfig(org_id=nw.id, kind="slack", name="Sales alerts", config={"channel": "#sales-alerts"}, enabled=False))
            nw.settings = {"mfa_required": False, "allowed_email_domains": ["northwind.test", "vulncrm.test", "idp.test"]}
            from app.testcases_seed import seed_testcases
            seed_testcases(db)
        db.commit()
        from app.testcases_seed import seed_testcases as ensure_cases
        ensure_cases(db)
        db.commit()
    finally:
        db.close()
