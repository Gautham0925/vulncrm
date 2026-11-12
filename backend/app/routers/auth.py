import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import Principal, audit, build_principal, client_ip, current_principal, partial_principal, rate_limit, to_dict
from app.mode import mode, vuln
from app.models import AuthSession, Membership, Organization, OtpChallenge, PasswordReset, SimulatedEmail, User, now
from app.security import check_password, hash_password, issue_jwt, rand, sha256

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()
_dummy_hash = hash_password("dummy-password-for-timing")


class LoginIn(BaseModel):
    email: str
    password: str


class OtpIn(BaseModel):
    challenge_id: str
    code: str


class ForgotIn(BaseModel):
    email: str


class ResetIn(BaseModel):
    token: str
    password: str


class ChangePwIn(BaseModel):
    current_password: str
    new_password: str


class SwitchIn(BaseModel):
    org_id: int


def password_ok(pw: str):
    if vuln("auth_lockout"):
        if len(pw) < 6:
            raise HTTPException(422, "Password must be at least 6 characters")
        return
    if len(pw) < 12 or pw.lower() == pw or not any(c.isdigit() for c in pw):
        raise HTTPException(422, "Password must be at least 12 characters and include upper case letters and digits")


def set_cookies(response: Response, sid: str):
    secure_cookie = settings.public_base_url.startswith("https")
    if vuln("session_handling") or vuln("csrf"):
        response.set_cookie("vc_session", sid, max_age=86400 * 30, path="/", httponly=False)
    else:
        response.set_cookie("vc_session", sid, max_age=settings.session_ttl_hours * 3600, path="/", httponly=True, samesite="strict", secure=secure_cookie)
    response.set_cookie("vc_csrf", secrets.token_urlsafe(24), path="/", httponly=False, samesite="strict" if not vuln("csrf") else None, secure=secure_cookie)


def new_session(db: Session, user: User, org_id: int | None, stage: str, method: str, request: Request, reuse_sid: str | None = None) -> AuthSession:
    ttl = timedelta(days=30) if vuln("session_handling") else timedelta(hours=settings.session_ttl_hours)
    if reuse_sid:
        s = db.query(AuthSession).filter(AuthSession.sid == reuse_sid, AuthSession.user_id.is_(None), AuthSession.revoked.is_(False)).first()
        if s:
            s.user_id, s.org_id, s.stage, s.method, s.expires_at = user.id, org_id, stage, method, now() + ttl
            s.ip = client_ip(request)
            return s
    s = AuthSession(sid=rand(24), user_id=user.id, org_id=org_id, stage=stage, method=method, ip=client_ip(request),
                    user_agent=(request.headers.get("user-agent") or "")[:300], expires_at=now() + ttl)
    db.add(s)
    db.flush()
    return s


def me_payload(db: Session, p: Principal) -> dict:
    ms = db.query(Membership, Organization).join(Organization, Organization.id == Membership.org_id).filter(Membership.user_id == p.user.id, Membership.status == "active").all()
    orgs = [{"id": o.id, "name": o.name, "slug": o.slug, "role": m.role.key} for m, o in ms]
    if p.super_admin:
        orgs = [{"id": o.id, "name": o.name, "slug": o.slug, "role": "super_admin"} for o in db.query(Organization).order_by(Organization.id).all()]
    org = db.get(Organization, p.org_id)
    return {
        "user": {"id": p.user.id, "email": p.user.email, "name": p.user.name, "mfa_enabled": p.user.mfa_enabled, "avatar_color": p.user.avatar_color, "preferences": p.user.preferences},
        "membership": {"id": p.membership.id, "title": p.membership.title, "department": p.membership.department, "team_id": p.membership.team_id},
        "organization": {"id": org.id, "name": org.name, "slug": org.slug, "plan": org.plan},
        "role": {"key": p.role.key, "name": p.role.name},
        "permissions": sorted(p.perms),
        "organizations": orgs,
        "level": p.level,
    }


def finish_login(db: Session, user: User, request: Request, response: Response, method: str = "password", org_id: int | None = None) -> dict:
    reuse = request.cookies.get("vc_session") if vuln("session_fixation") else None
    ms = db.query(Membership).filter(Membership.user_id == user.id, Membership.status == "active").order_by(Membership.id).all()
    if not ms:
        raise HTTPException(403, "Your account has no active organization membership")
    org = org_id or ms[0].org_id
    if not vuln("session_fixation"):
        old = request.cookies.get("vc_session")
        if old:
            db.query(AuthSession).filter(AuthSession.sid == old, AuthSession.user_id.is_(None)).update({"revoked": True})
    s = new_session(db, user, org, "authenticated", method, request, reuse_sid=reuse)
    user.last_login = now()
    p = build_principal(db, user, org, "session", sid=s.sid)
    audit(db, p, "auth.login", "session", s.id, {"method": method}, ip=client_ip(request))
    db.commit()
    set_cookies(response, s.sid)
    token = issue_jwt({"sub": str(user.id), "org": org, "sid": s.sid, "typ": "user"}, settings.access_ttl_seconds)
    return {"mfa_required": False, "access_token": token, "token_type": "Bearer", **me_payload(db, p)}


def send_otp(db: Session, user: User) -> OtpChallenge:
    code = f"{secrets.randbelow(1000000):06d}"
    ch = OtpChallenge(challenge_id=rand(18), user_id=user.id, code_hash=sha256(code), expires_at=now() + timedelta(seconds=settings.otp_ttl_seconds))
    db.add(ch)
    db.add(SimulatedEmail(to_email=user.email, subject="Your VULNCRM verification code", body=f"Your verification code is {code}. It expires in 5 minutes."))
    return ch


@router.get("/session-init")
def session_init(request: Request, response: Response, db: Session = Depends(get_db)):
    sid = request.cookies.get("vc_session")
    existing = db.query(AuthSession).filter(AuthSession.sid == sid).first() if sid else None
    if existing and existing.user_id is None and not existing.revoked:
        set_cookies(response, existing.sid)
        return {"sid_issued": False}
    s = AuthSession(sid=rand(24), user_id=None, stage="anonymous", ip=client_ip(request), expires_at=now() + timedelta(hours=1))
    db.add(s)
    db.commit()
    set_cookies(response, s.sid)
    return {"sid_issued": True}


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if not vuln("auth_lockout"):
        rate_limit(request, "login", 10, 300)
        rate_limit(request, "login-user", 5, 900, key=email)
    user = db.query(User).filter(User.email == email).first()
    if vuln("auth_enum"):
        if not user:
            raise HTTPException(404, "No account found for this email address")
        if not check_password(body.password, user.password_hash):
            audit(db, None, "auth.login_failed", "user", user.id, {"email": email}, ip=client_ip(request), org_id=None)
            db.commit()
            raise HTTPException(401, "Incorrect password")
    else:
        ok = check_password(body.password, user.password_hash if user else _dummy_hash)
        if not user or not ok:
            audit(db, None, "auth.login_failed", "user", user.id if user else None, {"email": email}, ip=client_ip(request), org_id=None)
            db.commit()
            raise HTTPException(401, "Invalid email or password")
    if not user.active:
        raise HTTPException(403, "Account disabled")
    if user.mfa_enabled:
        ch = send_otp(db, user)
        ms = db.query(Membership).filter(Membership.user_id == user.id, Membership.status == "active").first()
        s = new_session(db, user, ms.org_id if ms else None, "mfa_pending", "password", request)
        db.commit()
        set_cookies(response, s.sid)
        return {"mfa_required": True, "challenge_id": ch.challenge_id, "message": "Enter the verification code sent to your email"}
    return finish_login(db, user, request, response)


@router.post("/verify-otp")
def verify_otp(body: OtpIn, request: Request, response: Response, p: Principal = Depends(partial_principal), db: Session = Depends(get_db)):
    if not vuln("otp_bruteforce"):
        rate_limit(request, "otp", 10, 600, key=str(p.user.id))
    ch = db.query(OtpChallenge).filter(OtpChallenge.challenge_id == body.challenge_id, OtpChallenge.user_id == p.user.id).first()
    if not ch or ch.consumed:
        raise HTTPException(400, "Verification challenge is no longer valid")
    exp = ch.expires_at if ch.expires_at.tzinfo else ch.expires_at.replace(tzinfo=now().tzinfo)
    if exp < now():
        raise HTTPException(400, "Verification code expired")
    if not vuln("otp_bruteforce") and ch.attempts >= 5:
        ch.consumed = True
        db.commit()
        raise HTTPException(429, "Too many incorrect codes")
    ch.attempts += 1
    if sha256(body.code.strip()) != ch.code_hash:
        db.commit()
        raise HTTPException(401, "Incorrect verification code")
    ch.consumed = True
    sess = db.query(AuthSession).filter(AuthSession.sid == p.sid).first()
    if vuln("session_fixation"):
        sess.stage = "authenticated"
        sid = sess.sid
    else:
        sess.revoked = True
        sess = new_session(db, p.user, sess.org_id, "authenticated", "password+otp", request)
        sid = sess.sid
    sess.stage = "authenticated"
    p.user.last_login = now()
    pr = build_principal(db, p.user, sess.org_id, "session", sid=sid)
    audit(db, pr, "auth.login", "session", sess.id, {"method": "password+otp"}, ip=client_ip(request))
    db.commit()
    set_cookies(response, sid)
    token = issue_jwt({"sub": str(p.user.id), "org": sess.org_id, "sid": sid, "typ": "user"}, settings.access_ttl_seconds)
    return {"mfa_required": False, "access_token": token, "token_type": "Bearer", **me_payload(db, pr)}


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    sid = request.cookies.get("vc_session")
    if sid:
        s = db.query(AuthSession).filter(AuthSession.sid == sid).first()
        if s and s.user_id:
            if not vuln("session_handling"):
                s.revoked = True
            db.add(__import__("app.models", fromlist=["AuditLog"]).AuditLog(org_id=s.org_id, actor_user_id=s.user_id, action="auth.logout", resource_type="session", resource_id=str(s.id), ip=client_ip(request)))
            db.commit()
    response.delete_cookie("vc_session", path="/")
    response.delete_cookie("vc_csrf", path="/")
    return {"ok": True}


@router.get("/me")
def me(p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    return me_payload(db, p)


@router.post("/switch-org")
def switch_org(body: SwitchIn, request: Request, response: Response, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    target = db.get(Organization, body.org_id)
    if not target:
        raise HTTPException(404, "Organization not found")
    m = db.query(Membership).filter(Membership.user_id == p.user.id, Membership.org_id == target.id, Membership.status == "active").first()
    if not m and not p.super_admin:
        raise HTTPException(403, "You are not a member of that organization")
    s = db.query(AuthSession).filter(AuthSession.sid == p.sid).first()
    s.org_id = target.id
    pr = build_principal(db, p.user, target.id, "session", sid=p.sid)
    audit(db, pr, "auth.switch_org", "organization", target.id, ip=client_ip(request))
    db.commit()
    token = issue_jwt({"sub": str(p.user.id), "org": target.id, "sid": p.sid, "typ": "user"}, settings.access_ttl_seconds)
    return {"access_token": token, **me_payload(db, pr)}


@router.get("/sessions")
def sessions(p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    rows = db.query(AuthSession).filter(AuthSession.user_id == p.user.id, AuthSession.revoked.is_(False)).order_by(AuthSession.created_at.desc()).all()
    return {"items": [{"id": s.id, "ip": s.ip, "user_agent": s.user_agent, "method": s.method, "created_at": s.created_at.isoformat(), "last_seen": s.last_seen.isoformat(), "current": s.sid == p.sid} for s in rows]}


@router.delete("/sessions/{sid_id}")
def revoke_session(sid_id: int, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    s = db.get(AuthSession, sid_id)
    if not s or (s.user_id != p.user.id and not vuln("bola")):
        raise HTTPException(404, "Not found")
    s.revoked = True
    audit(db, p, "auth.session_revoked", "session", s.id)
    db.commit()
    return {"ok": True}


@router.post("/forgot-password")
def forgot(body: ForgotIn, request: Request, db: Session = Depends(get_db)):
    if not vuln("rate_limit"):
        rate_limit(request, "forgot", 5, 900)
    email = body.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        if vuln("auth_enum"):
            raise HTTPException(404, "No account found for this email address")
        return {"message": "If the account exists, a reset link has been sent."}
    token = f"{secrets.randbelow(1000000):06d}" if vuln("weak_reset") else secrets.token_urlsafe(32)
    db.add(PasswordReset(user_id=user.id, token=token, expires_at=now() + timedelta(hours=24 if vuln("weak_reset") else 0, minutes=0 if vuln("weak_reset") else 30)))
    db.add(SimulatedEmail(to_email=user.email, subject="Reset your VULNCRM password", body=f"Use this code or link to reset your password: {settings.public_base_url}/reset-password?token={token}"))
    audit(db, None, "auth.password_reset_requested", "user", user.id, ip=client_ip(request), org_id=None, actor_label=email)
    db.commit()
    return {"message": "If the account exists, a reset link has been sent."}


@router.post("/reset-password")
def reset(body: ResetIn, request: Request, db: Session = Depends(get_db)):
    if not vuln("rate_limit"):
        rate_limit(request, "reset", 10, 900)
    pr = db.query(PasswordReset).filter(PasswordReset.token == body.token).first()
    exp = pr.expires_at if pr and pr.expires_at.tzinfo else (pr.expires_at.replace(tzinfo=now().tzinfo) if pr else None)
    if not pr or (pr.used and not vuln("weak_reset")) or exp < now():
        raise HTTPException(400, "This reset link is invalid or has expired")
    password_ok(body.password)
    user = db.get(User, pr.user_id)
    user.password_hash = hash_password(body.password)
    pr.used = True
    if not vuln("session_handling"):
        db.query(AuthSession).filter(AuthSession.user_id == user.id).update({"revoked": True})
    audit(db, None, "auth.password_reset", "user", user.id, ip=client_ip(request), org_id=None, actor_label=user.email)
    db.commit()
    return {"ok": True}


@router.post("/change-password")
def change_password(body: ChangePwIn, request: Request, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    if not check_password(body.current_password, p.user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    password_ok(body.new_password)
    p.user.password_hash = hash_password(body.new_password)
    if not vuln("session_handling"):
        db.query(AuthSession).filter(AuthSession.user_id == p.user.id, AuthSession.sid != p.sid).update({"revoked": True})
    audit(db, p, "auth.password_changed", "user", p.user.id, ip=client_ip(request))
    db.commit()
    return {"ok": True}
