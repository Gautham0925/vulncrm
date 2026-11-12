import re

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import Principal, audit, client_ip, current_principal, like, paginate, require, to_dict
from app.mode import vuln
from app.models import AuditLog, Membership, Notification, Organization, Role, SimulatedEmail, Team, User
from app.rbac import PERMISSIONS, SYSTEM_ROLES
from app.security import hash_password, rand

router = APIRouter(prefix="/api", tags=["people"])
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def ser_emp(m: Membership, p: Principal, detail: bool = False) -> dict:
    d = {"id": m.id, "user_id": m.user_id, "org_id": m.org_id, "name": m.user.name, "email": m.user.email, "role_id": m.role_id, "role_key": m.role.key, "role_name": m.role.name,
         "team_id": m.team_id, "team_name": m.team.name if m.team else None, "manager_id": m.manager_id, "title": m.title, "department": m.department, "phone": m.phone,
         "status": m.status, "active": m.user.active, "last_login": m.user.last_login.isoformat() if m.user.last_login else None, "avatar_color": m.user.avatar_color}
    if vuln("data_exposure") or p.can("employees.manage"):
        d["salary"], d["internal_notes"] = m.salary, m.internal_notes
    if vuln("data_exposure") and detail:
        d["user"] = {"id": m.user.id, "email": m.user.email, "password_hash": m.user.password_hash, "mfa_enabled": m.user.mfa_enabled, "mfa_secret": m.user.mfa_secret, "external_subject": m.user.external_subject}
    return d


def get_member(db, mid, p, flag="bola"):
    m = db.get(Membership, mid) if vuln(flag) else db.query(Membership).filter(Membership.id == mid, Membership.org_id == p.org_id).first()
    if not m:
        raise HTTPException(404, "Not found")
    return m


@router.get("/employees")
def list_employees(q: str = "", team_id: int | None = None, role: str = "", status: str = "", page: int = 1, size: int = 25, p: Principal = Depends(require("employees.read")), db: Session = Depends(get_db)):
    qs = db.query(Membership).join(User, User.id == Membership.user_id).join(Role, Role.id == Membership.role_id).filter(Membership.org_id == p.org_id)
    if q:
        qs = qs.filter(or_(User.name.ilike(like(q)), User.email.ilike(like(q)), Membership.title.ilike(like(q))))
    if team_id:
        qs = qs.filter(Membership.team_id == team_id)
    if role:
        qs = qs.filter(Role.key == role)
    if status:
        qs = qs.filter(Membership.status == status)
    rows, meta = paginate(qs.order_by(User.name), page, size)
    return {"items": [ser_emp(m, p) for m in rows], "meta": meta}


@router.post("/employees", status_code=201)
def create_employee(body: dict, request: Request, p: Principal = Depends(require("employees.read")), db: Session = Depends(get_db)):
    if not p.can("employees.manage") and not vuln("bfla"):
        raise HTTPException(403, "Insufficient permissions")
    email = (body.get("email") or "").strip().lower()
    if not EMAIL_RE.match(email) or not body.get("name"):
        raise HTTPException(422, "Name and a valid email are required")
    role = db.query(Role).filter(Role.key == body.get("role_key", "sales_rep"), Role.org_id.is_(None)).first() or db.query(Role).filter(Role.id == body.get("role_id")).first()
    if not role:
        raise HTTPException(422, "Unknown role")
    check_role_grant(p, role, db)
    user = db.query(User).filter(User.email == email).first()
    temp = None
    if not user:
        temp = rand(10) + "9Aa"
        user = User(email=email, name=body["name"], password_hash=hash_password(temp))
        db.add(user)
        db.flush()
    if db.query(Membership).filter(Membership.user_id == user.id, Membership.org_id == p.org_id).first():
        raise HTTPException(409, "This person is already a member of the organization")
    m = Membership(user_id=user.id, org_id=p.org_id, role_id=role.id, team_id=body.get("team_id"), manager_id=body.get("manager_id"), title=body.get("title"), department=body.get("department"), phone=body.get("phone"))
    db.add(m)
    db.add(SimulatedEmail(to_email=email, subject="You have been invited to VULNCRM", body=f"{p.user.name} invited you. Temporary password: {temp or '(use your existing password)'}"))
    db.flush()
    audit(db, p, "employee.invite", "membership", m.id, {"email": email, "role": role.key}, ip=client_ip(request))
    db.commit()
    return ser_emp(m, p)


def check_role_grant(p: Principal, role: Role, db: Session):
    if vuln("role_change"):
        return
    if role.key == "super_admin" and not p.super_admin:
        raise HTTPException(403, "You cannot grant that role")
    if role.org_id is not None and role.org_id != p.org_id:
        raise HTTPException(422, "Unknown role")
    if not set(role.permissions or []).issubset(p.perms):
        raise HTTPException(403, "You cannot grant permissions you do not hold")


@router.get("/employees/{mid}")
def get_employee(mid: int, p: Principal = Depends(require("employees.read")), db: Session = Depends(get_db)):
    return ser_emp(get_member(db, mid, p), p, detail=True)


@router.patch("/employees/{mid}")
def update_employee(mid: int, body: dict, request: Request, p: Principal = Depends(require("employees.read")), db: Session = Depends(get_db)):
    if not p.can("employees.manage") and not vuln("bfla"):
        raise HTTPException(403, "Insufficient permissions")
    m = get_member(db, mid, p)
    allowed = {"title", "department", "team_id", "manager_id", "phone"}
    if p.can("employees.manage"):
        allowed |= {"salary", "internal_notes"}
    if vuln("mass_assignment"):
        allowed |= {"role_id", "org_id", "salary", "internal_notes", "status"}
    for k, v in body.items():
        if k in allowed:
            setattr(m, k, v)
    if "name" in body and body["name"]:
        m.user.name = body["name"]
    audit(db, p, "employee.update", "membership", m.id, {"fields": list(body)}, ip=client_ip(request))
    db.commit()
    return ser_emp(m, p)


@router.put("/employees/{mid}/role")
def change_role(mid: int, body: dict, request: Request, p: Principal = Depends(require("employees.read")), db: Session = Depends(get_db)):
    if not p.can("employees.manage") and not vuln("role_change"):
        raise HTTPException(403, "Insufficient permissions")
    m = get_member(db, mid, p, flag="role_change")
    role = db.get(Role, body.get("role_id"))
    if not role:
        raise HTTPException(422, "Unknown role")
    check_role_grant(p, role, db)
    if m.user_id == p.user.id and not vuln("role_change"):
        raise HTTPException(403, "You cannot change your own role")
    old = m.role.key
    m.role_id = role.id
    audit(db, p, "employee.role_changed", "membership", m.id, {"from": old, "to": role.key}, ip=client_ip(request))
    db.commit()
    return ser_emp(m, p)


def set_active(mid, active, request, p, db):
    if not p.can("employees.manage") and not vuln("admin_actions"):
        raise HTTPException(403, "Insufficient permissions")
    m = get_member(db, mid, p, flag="admin_actions")
    if m.user_id == p.user.id:
        raise HTTPException(409, "You cannot change your own status")
    m.status = "active" if active else "inactive"
    if not active:
        from app.models import AuthSession
        db.query(AuthSession).filter(AuthSession.user_id == m.user_id).update({"revoked": True})
    audit(db, p, "employee.activated" if active else "employee.deactivated", "membership", m.id, ip=client_ip(request))
    db.commit()
    return ser_emp(m, p)


@router.post("/employees/{mid}/deactivate")
def deactivate(mid: int, request: Request, p: Principal = Depends(require("employees.read")), db: Session = Depends(get_db)):
    return set_active(mid, False, request, p, db)


@router.post("/employees/{mid}/activate")
def activate(mid: int, request: Request, p: Principal = Depends(require("employees.read")), db: Session = Depends(get_db)):
    return set_active(mid, True, request, p, db)


@router.get("/employees/{mid}/activity")
def employee_activity(mid: int, p: Principal = Depends(require("employees.read")), db: Session = Depends(get_db)):
    m = get_member(db, mid, p)
    rows = db.query(AuditLog).filter(AuditLog.actor_user_id == m.user_id, AuditLog.org_id == m.org_id).order_by(AuditLog.created_at.desc()).limit(50).all()
    return {"items": [to_dict(r) for r in rows]}


@router.get("/teams")
def list_teams(p: Principal = Depends(require("employees.read")), db: Session = Depends(get_db)):
    out = []
    for t in db.query(Team).filter(Team.org_id == p.org_id).order_by(Team.name).all():
        mgr = db.get(Membership, t.manager_id) if t.manager_id else None
        count = db.query(Membership).filter(Membership.team_id == t.id).count()
        out.append({**to_dict(t), "manager_name": mgr.user.name if mgr else None, "member_count": count})
    return {"items": out}


@router.post("/teams", status_code=201)
def create_team(body: dict, request: Request, p: Principal = Depends(require("teams.manage")), db: Session = Depends(get_db)):
    if not body.get("name"):
        raise HTTPException(422, "Name is required")
    t = Team(org_id=p.org_id, name=body["name"], department=body.get("department"), manager_id=body.get("manager_id"), description=body.get("description"))
    db.add(t)
    db.flush()
    audit(db, p, "team.create", "team", t.id, ip=client_ip(request))
    db.commit()
    return to_dict(t)


@router.patch("/teams/{tid}")
def update_team(tid: int, body: dict, p: Principal = Depends(require("teams.manage")), db: Session = Depends(get_db)):
    t = db.query(Team).filter(Team.id == tid, Team.org_id == p.org_id).first()
    if not t:
        raise HTTPException(404, "Not found")
    for k in ("name", "department", "manager_id", "description"):
        if k in body:
            setattr(t, k, body[k])
    audit(db, p, "team.update", "team", t.id)
    db.commit()
    return to_dict(t)


@router.delete("/teams/{tid}")
def delete_team(tid: int, p: Principal = Depends(require("teams.manage")), db: Session = Depends(get_db)):
    t = db.query(Team).filter(Team.id == tid, Team.org_id == p.org_id).first()
    if not t:
        raise HTTPException(404, "Not found")
    db.query(Membership).filter(Membership.team_id == t.id).update({"team_id": None})
    db.delete(t)
    audit(db, p, "team.delete", "team", tid)
    db.commit()
    return {"ok": True}


@router.get("/permissions")
def permissions(p: Principal = Depends(current_principal)):
    return {"items": [{"key": k, "description": v} for k, v in PERMISSIONS.items()]}


@router.get("/roles")
def list_roles(p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    if not (p.can("roles.manage") or p.can("employees.read")):
        raise HTTPException(403, "Insufficient permissions")
    rows = db.query(Role).filter(or_(Role.org_id.is_(None), Role.org_id == p.org_id)).order_by(Role.system.desc(), Role.name).all()
    counts = {r.id: db.query(Membership).filter(Membership.role_id == r.id, Membership.org_id == p.org_id).count() for r in rows}
    return {"items": [{**to_dict(r), "member_count": counts[r.id]} for r in rows]}


def validate_perms(p: Principal, perms: list):
    unknown = [x for x in perms if x not in PERMISSIONS]
    if unknown:
        raise HTTPException(422, f"Unknown permissions: {', '.join(unknown)}")
    if not vuln("role_change") and not set(perms).issubset(p.perms):
        raise HTTPException(403, "You cannot grant permissions you do not hold")


@router.post("/roles", status_code=201)
def create_role(body: dict, request: Request, p: Principal = Depends(require("roles.manage")), db: Session = Depends(get_db)):
    key = re.sub(r"[^a-z0-9_]", "_", (body.get("name") or "").lower())
    if not key:
        raise HTTPException(422, "Name is required")
    perms = body.get("permissions", [])
    validate_perms(p, perms)
    if db.query(Role).filter(Role.org_id == p.org_id, Role.key == key).first():
        raise HTTPException(409, "A role with that name exists")
    r = Role(org_id=p.org_id, key=key, name=body["name"], description=body.get("description", ""), permissions=perms)
    db.add(r)
    db.flush()
    audit(db, p, "role.create", "role", r.id, {"permissions": perms}, ip=client_ip(request))
    db.commit()
    return to_dict(r)


@router.patch("/roles/{rid}")
def update_role(rid: int, body: dict, request: Request, p: Principal = Depends(require("roles.manage")), db: Session = Depends(get_db)):
    r = db.get(Role, rid)
    if not r or r.system or r.org_id != p.org_id:
        raise HTTPException(404, "Not found")
    if "permissions" in body:
        validate_perms(p, body["permissions"])
        r.permissions = body["permissions"]
    for k in ("name", "description"):
        if k in body:
            setattr(r, k, body[k])
    audit(db, p, "role.update", "role", r.id, {"permissions": r.permissions}, ip=client_ip(request))
    db.commit()
    return to_dict(r)


@router.delete("/roles/{rid}")
def delete_role(rid: int, p: Principal = Depends(require("roles.manage")), db: Session = Depends(get_db)):
    r = db.get(Role, rid)
    if not r or r.system or r.org_id != p.org_id:
        raise HTTPException(404, "Not found")
    if db.query(Membership).filter(Membership.role_id == r.id).count():
        raise HTTPException(409, "Role is assigned to members")
    db.delete(r)
    audit(db, p, "role.delete", "role", rid)
    db.commit()
    return {"ok": True}


DEFAULT_SETTINGS = {"mfa_required": False, "session_timeout_minutes": 720, "min_password_length": 12, "ip_allowlist": [], "allowed_email_domains": []}


@router.get("/org")
def get_org(p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    o = db.get(Organization, p.org_id)
    return {**to_dict(o, exclude=("settings",)), "settings": {**DEFAULT_SETTINGS, **(o.settings or {})}}


@router.patch("/org")
def update_org(body: dict, request: Request, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    if not p.can("org.manage") and not vuln("admin_actions"):
        raise HTTPException(403, "Insufficient permissions")
    o = db.get(Organization, p.org_id)
    for k in ("name", "industry", "timezone"):
        if k in body:
            setattr(o, k, body[k])
    if isinstance(body.get("settings"), dict):
        o.settings = {**(o.settings or {}), **{k: v for k, v in body["settings"].items() if k in DEFAULT_SETTINGS}}
    if vuln("mass_assignment") and "plan" in body:
        o.plan = body["plan"]
    audit(db, p, "org.settings_changed", "organization", o.id, {"fields": list(body)}, ip=client_ip(request))
    db.commit()
    return {**to_dict(o, exclude=("settings",)), "settings": {**DEFAULT_SETTINGS, **(o.settings or {})}}


@router.get("/platform/orgs")
def platform_orgs(p: Principal = Depends(require("platform.manage")), db: Session = Depends(get_db)):
    rows = db.query(Organization).order_by(Organization.id).all()
    return {"items": [{**to_dict(o, exclude=("settings",)), "members": db.query(Membership).filter(Membership.org_id == o.id).count()} for o in rows]}


@router.post("/platform/orgs", status_code=201)
def platform_create_org(body: dict, request: Request, p: Principal = Depends(require("platform.manage")), db: Session = Depends(get_db)):
    name, admin_email, admin_name = body.get("name"), (body.get("admin_email") or "").strip().lower(), body.get("admin_name")
    if not name or not EMAIL_RE.match(admin_email or "") or not admin_name:
        raise HTTPException(422, "Organization name, admin name and a valid admin email are required")
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if db.query(Organization).filter(Organization.slug == slug).first():
        raise HTTPException(409, "An organization with that name already exists")
    o = Organization(name=name, slug=slug, industry=body.get("industry"), plan=body.get("plan", "enterprise"))
    db.add(o)
    db.flush()
    role = db.query(Role).filter(Role.key == "org_admin", Role.org_id.is_(None)).first()
    user = db.query(User).filter(User.email == admin_email).first()
    temp = None
    if not user:
        temp = rand(10) + "9Aa"
        user = User(email=admin_email, name=admin_name, password_hash=hash_password(temp))
        db.add(user)
        db.flush()
    db.add(Membership(user_id=user.id, org_id=o.id, role_id=role.id, title="Organization Administrator"))
    db.add(SimulatedEmail(to_email=admin_email, subject=f"Your {name} workspace is ready", body=f"Temporary password: {temp or '(use your existing password)'}"))
    audit(db, p, "platform.org_created", "organization", o.id, {"name": name}, ip=client_ip(request), org_id=o.id)
    db.commit()
    return to_dict(o, exclude=("settings",))


@router.get("/profile")
def get_profile(p: Principal = Depends(current_principal)):
    m = p.membership
    return {"id": p.user.id, "email": p.user.email, "name": p.user.name, "mfa_enabled": p.user.mfa_enabled, "preferences": p.user.preferences, "title": m.title, "department": m.department, "phone": m.phone, "avatar_color": p.user.avatar_color}


@router.patch("/profile")
def update_profile(body: dict, request: Request, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    user_fields = {"name", "preferences", "avatar_color"}
    mem_fields = {"title", "phone", "department"}
    if vuln("mass_assignment"):
        user_fields |= {"mfa_enabled", "active", "email"}
        mem_fields |= {"role_id", "salary", "org_id"}
    if "mfa_enabled" in body and not vuln("mass_assignment"):
        user_fields.add("mfa_enabled")
    for k, v in body.items():
        if k in user_fields:
            setattr(p.user, k, v)
        elif k in mem_fields:
            setattr(p.membership, k, v)
    audit(db, p, "profile.update", "user", p.user.id, {"fields": list(body)}, ip=client_ip(request))
    db.commit()
    return get_profile(p)


@router.get("/notifications")
def notifications(p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    rows = db.query(Notification).filter(Notification.org_id == p.org_id, or_(Notification.membership_id == p.membership.id, Notification.membership_id.is_(None))).order_by(Notification.created_at.desc()).limit(30).all()
    return {"items": [to_dict(n) for n in rows], "unread": sum(1 for n in rows if not n.read)}


@router.post("/notifications/read")
def mark_read(p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    db.query(Notification).filter(Notification.org_id == p.org_id, Notification.membership_id == p.membership.id).update({"read": True})
    db.commit()
    return {"ok": True}
