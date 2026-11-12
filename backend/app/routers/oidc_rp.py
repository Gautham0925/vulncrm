import json
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from jwt.algorithms import RSAAlgorithm
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import audit, build_principal, client_ip, rate_limit
from app.mode import vuln
from app.models import IntegrationConfig, Organization, SamlConfig, SsoSession, User, now
from app.routers.auth import me_payload, new_session, set_cookies
from app.routers.saml import SamlError, provision
from app.security import rand
from app.services import safe_fetch

router = APIRouter(prefix="/api/auth/oidc", tags=["oidc"])
settings = get_settings()


def oidc_cfg(db: Session, slug: str):
    o = db.query(Organization).filter(Organization.slug == slug).first()
    c = db.query(IntegrationConfig).filter(IntegrationConfig.org_id == o.id, IntegrationConfig.kind == "oidc", IntegrationConfig.enabled.is_(True)).first() if o else None
    if not o or not c:
        raise HTTPException(404, "OpenID Connect sign-in is not configured for this organization")
    return o, c


@router.get("/{slug}/login")
def login(slug: str, request: Request, db: Session = Depends(get_db)):
    rate_limit(request, "oidc-login", 30, 60)
    o, c = oidc_cfg(db, slug)
    state, nonce = rand(18), rand(18)
    db.add(SsoSession(request_id=state, org_id=o.id, kind="oidc", state=state, nonce=nonce, status="pending"))
    db.commit()
    cfg = c.config
    q = {"response_type": "code", "client_id": cfg["client_id"], "redirect_uri": cfg["redirect_uri"], "scope": "openid email profile", "state": state, "nonce": nonce}
    return RedirectResponse(f"{cfg['authorize_url']}?{urlencode(q)}", status_code=302)


def fetch_jwks(url: str) -> dict:
    res = safe_fetch(url, "GET", timeout=3, max_bytes=100000)
    if not res.get("ok"):
        raise SamlError("Unable to retrieve signing keys")
    return json.loads(res["body"])


def validate_id_token(token: str, cfg: dict, expected_nonce: str | None) -> dict:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        raise SamlError("Malformed ID token")
    if header.get("alg") != "RS256":
        raise SamlError("Unsupported signing algorithm")
    url = cfg["jwks_url"]
    if vuln("oidc_jku") and header.get("jku"):
        url = header["jku"]
    jwks = fetch_jwks(url)
    key = next((k for k in jwks.get("keys", []) if k.get("kid") == header.get("kid")), None)
    if key is None and vuln("oidc_validation") and jwks.get("keys"):
        key = jwks["keys"][0]
    if key is None:
        raise SamlError("Signing key not found")
    pub = RSAAlgorithm.from_jwk(json.dumps(key))
    opts = {"require": ["exp", "sub"]}
    kwargs = {}
    if vuln("oidc_validation"):
        opts.update({"verify_aud": False, "verify_iss": False})
    else:
        kwargs = {"audience": cfg["client_id"], "issuer": cfg["issuer"]}
        opts["require"] += ["iss", "aud"]
    try:
        claims = jwt.decode(token, pub, algorithms=["RS256"], options=opts, **kwargs)
    except jwt.PyJWTError as e:
        raise SamlError(f"ID token validation failed: {type(e).__name__}")
    if not vuln("oidc_nonce") and (not expected_nonce or claims.get("nonce") != expected_nonce):
        raise SamlError("Nonce mismatch")
    return claims


@router.get("/{slug}/callback")
def callback(slug: str, request: Request, code: str = "", state: str = "", db: Session = Depends(get_db)):
    rate_limit(request, "oidc-cb", 30, 60)
    o, c = oidc_cfg(db, slug)
    cfg = c.config
    as_json = request.query_params.get("format") == "json"
    pending = db.query(SsoSession).filter(SsoSession.request_id == state, SsoSession.org_id == o.id, SsoSession.kind == "oidc", SsoSession.status == "pending").first()
    try:
        if not pending and not vuln("oauth_state"):
            raise SamlError("Invalid or expired sign-in state")
        try:
            r = httpx.post(cfg["token_url"], data={"grant_type": "authorization_code", "code": code, "redirect_uri": cfg["redirect_uri"], "client_id": cfg["client_id"], "client_secret": cfg["client_secret"]}, timeout=4)
        except httpx.HTTPError:
            raise SamlError("Identity provider is unreachable")
        if r.status_code != 200 or "id_token" not in r.json():
            raise SamlError("Token exchange failed")
        claims = validate_id_token(r.json()["id_token"], cfg, pending.nonce if pending else None)
        email = (claims.get("email") or "").lower()
        if not email:
            raise SamlError("The identity provider did not return an email address")
        if not claims.get("email_verified") and not vuln("oidc_linking"):
            raise SamlError("Email address is not verified")
        existing = db.query(User).filter(User.email == email).first()
        if existing and existing.external_subject and existing.external_subject != claims["sub"] and not vuln("oidc_linking"):
            raise SamlError("This account is linked to a different identity")
        scfg = db.query(SamlConfig).filter(SamlConfig.org_id == o.id).first() or SamlConfig(org_id=o.id)
        user, mem = provision(db, o, scfg, {"name_id": claims["sub"], "attributes": {"email": email, "name": claims.get("name", "")}})
        if not user.external_subject:
            user.external_subject = claims["sub"]
        if not user.active:
            raise SamlError("Account is disabled")
    except SamlError as e:
        db.rollback()
        audit(db, None, "sso.oidc_failed", "organization", o.id, {"reason": str(e)}, ip=client_ip(request), org_id=o.id, actor_label="oidc")
        db.commit()
        if as_json:
            return JSONResponse({"error": str(e)}, status_code=401)
        return HTMLResponse(f"<!doctype html><title>Sign-in failed</title><body style='font:16px system-ui;margin:48px'><h2>Single sign-on failed</h2><p>{__import__('html').escape(str(e))}</p><p><a href='/login'>Back to sign in</a></p></body>", status_code=401)
    if pending:
        pending.status = "active"
    sess = new_session(db, user, o.id, "authenticated", "oidc", request)
    user.last_login = now()
    p = build_principal(db, user, o.id, "session", sid=sess.sid)
    audit(db, p, "auth.login", "session", sess.id, {"method": "oidc"}, ip=client_ip(request))
    db.commit()
    if as_json:
        resp = JSONResponse({"ok": True, **me_payload(db, p)})
    else:
        resp = RedirectResponse("/", status_code=303)
    set_cookies(resp, sess.sid)
    return resp
