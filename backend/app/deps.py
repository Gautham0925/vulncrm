import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.mode import vuln
from app.models import ApiKey, AuditLog, AuthSession, Membership, OAuthToken, Role, Team, User, now
from app.rbac import ALL, SCOPE_LEVEL, perm_to_scope
from app.security import sha256, verify_jwt

settings = get_settings()
SENSITIVE_KEYS = ("password", "token", "secret", "key", "authorization", "code", "otp")


@dataclass
class Principal:
    user: User
    membership: Membership
    role: Role
    org_id: int
    perms: set = field(default_factory=set)
    kind: str = "session"
    scopes: set | None = None
    sid: str | None = None
    stage: str = "authenticated"
    super_admin: bool = False
    actor_label: str = ""

    @property
    def level(self) -> str:
        return SCOPE_LEVEL.get(self.role.key, "own")

    def can(self, perm: str) -> bool:
        if perm not in self.perms:
            return False
        if self.scopes is not None and "*" not in self.scopes and perm_to_scope(perm) not in self.scopes and "admin" not in self.scopes:
            return False
        return True


def client_ip(request: Request) -> str:
    if vuln("rate_limit"):
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")


_buckets: dict = defaultdict(deque)


def reset_rate_limits():
    _buckets.clear()


def rate_limit(request: Request, bucket: str, limit: int, window: int, key: str = ""):
    k = (bucket, client_ip(request), key)
    q = _buckets[k]
    t = time.time()
    while q and q[0] < t - window:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(429, "Too many requests. Try again later.", headers={"Retry-After": str(window)})
    q.append(t)


def clean(detail):
    if isinstance(detail, dict):
        return {k: ("[redacted]" if any(s in k.lower() for s in SENSITIVE_KEYS) else clean(v)) for k, v in detail.items()}
    if isinstance(detail, list):
        return [clean(v) for v in detail]
    return detail


def audit(db: Session, p: Principal | None, action: str, rtype: str | None = None, rid=None, detail: dict | None = None, ip: str | None = None, org_id: int | None = None, actor_label: str | None = None):
    db.add(AuditLog(
        org_id=org_id if org_id is not None else (p.org_id if p else None),
        actor_user_id=p.user.id if p else None,
        actor_label=actor_label or (p.user.email if p else None),
        action=action, resource_type=rtype, resource_id=str(rid) if rid is not None else None,
        detail=clean(detail) if detail else None, ip=ip,
    ))


def _aware(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def resolve_membership(db: Session, user: User, org_id: int | None):
    ms = db.query(Membership).filter(Membership.user_id == user.id, Membership.status == "active").all()
    if not ms:
        return None, None, False
    sup = next((m for m in ms if db.get(Role, m.role_id).key == "super_admin"), None)
    if org_id is not None:
        m = next((x for x in ms if x.org_id == org_id), None)
        if m:
            return m, db.get(Role, m.role_id), db.get(Role, m.role_id).key == "super_admin"
        if sup:
            return sup, db.get(Role, sup.role_id), True
        return None, None, False
    m = ms[0]
    return m, db.get(Role, m.role_id), db.get(Role, m.role_id).key == "super_admin"


def build_principal(db: Session, user: User, org_id: int | None, kind: str, sid=None, scopes=None, stage="authenticated") -> Principal:
    m, role, sup = resolve_membership(db, user, org_id)
    if not m:
        raise HTTPException(403, "No active membership")
    perms = set(role.permissions or [])
    if sup:
        perms = set(ALL)
    return Principal(user=user, membership=m, role=role, org_id=org_id or m.org_id, perms=perms, kind=kind, scopes=scopes, sid=sid, stage=stage, super_admin=sup, actor_label=user.email)


def _from_session(db: Session, sid: str, request: Request) -> Principal:
    s = db.query(AuthSession).filter(AuthSession.sid == sid).first()
    if not s or s.revoked or not s.user_id:
        raise HTTPException(401, "Not authenticated")
    if s.expires_at and _aware(s.expires_at) < now():
        raise HTTPException(401, "Session expired")
    user = db.get(User, s.user_id)
    if not user or not user.active:
        raise HTTPException(401, "Account disabled")
    s.last_seen = now()
    p = build_principal(db, user, s.org_id, "session", sid=sid, stage=s.stage)
    return p


def _from_api_key(db: Session, raw: str) -> Principal:
    prefix = raw[:12]
    k = db.query(ApiKey).filter(ApiKey.prefix == prefix).first()
    if vuln("api_key_weak"):
        ok = k is not None and (k.plaintext == raw or k.key_hash == sha256(raw))
    else:
        ok = k is not None and k.key_hash == sha256(raw)
    if not ok or k.revoked:
        raise HTTPException(401, "Invalid API key")
    if k.expires_at and _aware(k.expires_at) < now() and not vuln("api_key_weak"):
        raise HTTPException(401, "API key expired")
    k.last_used_at = now()
    from app.models import ApiClient
    c = db.get(ApiClient, k.client_id)
    if not c or not c.active:
        raise HTTPException(401, "API client disabled")
    owner = db.get(Membership, c.owner_id) if c.owner_id else None
    if owner is None:
        raise HTTPException(401, "API client has no owner")
    user = db.get(User, owner.user_id)
    p = build_principal(db, user, k.org_id, "api_key", scopes=set(k.scopes or c.scopes or []))
    if vuln("api_key_weak"):
        p.scopes = None
    p.actor_label = f"apikey:{k.prefix}"
    return p


def _from_oauth(db: Session, raw: str) -> Principal:
    t = db.query(OAuthToken).filter(OAuthToken.access_hash == sha256(raw)).first()
    if not t or t.revoked or _aware(t.expires_at) < now():
        raise HTTPException(401, "Invalid or expired access token")
    if t.user_id:
        user = db.get(User, t.user_id)
    else:
        from app.models import OAuthClient
        c = db.query(OAuthClient).filter(OAuthClient.client_id == t.client_id).first()
        owner = db.query(Membership).filter(Membership.org_id == t.org_id, Membership.status == "active").join(Role, Role.id == Membership.role_id).filter(Role.key == "integration_dev").first()
        user = db.get(User, owner.user_id) if owner else None
    if not user:
        raise HTTPException(401, "Token has no subject")
    p = build_principal(db, user, t.org_id, "oauth", scopes=set((t.scope or "").split()))
    p.actor_label = f"oauth:{t.client_id}"
    return p


def current_principal(request: Request, db: Session = Depends(get_db)) -> Principal:
    cached = getattr(request.state, "principal", None)
    if cached:
        return cached
    auth = request.headers.get("authorization", "")
    api_key = request.headers.get("x-api-key")
    p = None
    if auth.lower().startswith("bearer "):
        tok = auth[7:].strip()
        if tok.startswith("vck_"):
            p = _from_api_key(db, tok)
        elif tok.startswith("vco_"):
            p = _from_oauth(db, tok)
        else:
            try:
                claims = verify_jwt(tok)
            except jwt.PyJWTError:
                raise HTTPException(401, "Invalid token")
            if claims.get("typ") != "user":
                raise HTTPException(401, "Invalid token type")
            p = _from_session(db, claims["sid"], request)
            p.kind = "bearer"
    elif api_key:
        p = _from_api_key(db, api_key)
    else:
        sid = request.cookies.get("vc_session")
        if sid:
            p = _from_session(db, sid, request)
            if request.method not in ("GET", "HEAD", "OPTIONS") and not vuln("csrf"):
                tok = request.headers.get("x-csrf-token")
                if not tok or tok != request.cookies.get("vc_csrf"):
                    raise HTTPException(403, "CSRF token missing or invalid")
    if p is None:
        raise HTTPException(401, "Authentication required")
    if p.stage != "authenticated":
        raise HTTPException(403, "Multi-factor verification required")
    request.state.principal = p
    return p


def partial_principal(request: Request, db: Session = Depends(get_db)) -> Principal:
    sid = request.cookies.get("vc_session")
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        try:
            sid = verify_jwt(auth[7:].strip()).get("sid")
        except jwt.PyJWTError:
            raise HTTPException(401, "Invalid token")
    if not sid:
        raise HTTPException(401, "Authentication required")
    return _from_session(db, sid, request)


def require(*perms: str):
    def dep(p: Principal = Depends(current_principal)) -> Principal:
        for perm in perms:
            if not p.can(perm):
                raise HTTPException(403, "Insufficient permissions")
        return p
    return dep


def require_any(*perms: str):
    def dep(p: Principal = Depends(current_principal)) -> Principal:
        if not any(p.can(x) for x in perms):
            raise HTTPException(403, "Insufficient permissions")
        return p
    return dep


def team_member_ids(db: Session, p: Principal) -> list[int]:
    ids = [p.membership.id]
    teams = db.query(Team).filter(Team.org_id == p.org_id, Team.manager_id == p.membership.id).all()
    for t in teams:
        ids += [m.id for m in db.query(Membership).filter(Membership.team_id == t.id).all()]
    ids += [m.id for m in db.query(Membership).filter(Membership.manager_id == p.membership.id).all()]
    return list(set(ids))


def scoped(db: Session, q, model, p: Principal, owner_attr: str = "owner_id"):
    q = q.filter(model.org_id == p.org_id)
    if p.level == "org":
        return q
    col = getattr(model, owner_attr)
    if p.level == "team":
        return q.filter(col.in_(team_member_ids(db, p)))
    return q.filter(col == p.membership.id)


def get_or_404(db: Session, model, oid: int, p: Principal, owner_attr: str | None = "owner_id", flag: str = "bola"):
    if vuln(flag):
        obj = db.get(model, oid)
    else:
        q = db.query(model).filter(model.id == oid)
        if owner_attr and hasattr(model, owner_attr):
            q = scoped(db, q, model, p, owner_attr)
        else:
            q = q.filter(model.org_id == p.org_id)
        obj = q.first()
    if obj is None or getattr(obj, "deleted_at", None):
        raise HTTPException(404, "Not found")
    return obj


def to_dict(obj, exclude: tuple = (), include_only: tuple | None = None) -> dict:
    out = {}
    for c in obj.__table__.columns:
        if c.name in exclude:
            continue
        if include_only is not None and c.name not in include_only:
            continue
        v = getattr(obj, c.name)
        out[c.name] = v.isoformat() if isinstance(v, datetime) else v
    return out


def paginate(q, page: int, size: int):
    size = max(1, min(size, 200))
    page = max(1, page)
    total = q.count()
    return q.offset((page - 1) * size).limit(size).all(), {"page": page, "size": size, "total": total}


def page_params(page: int = 1, size: int = 25):
    return page, size


def like(q: str):
    return f"%{q.replace('%', '').replace('_', '')}%"
