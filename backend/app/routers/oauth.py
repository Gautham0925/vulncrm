import base64
import hashlib
import hmac
import html
import secrets
from datetime import timedelta
from urllib.parse import quote, urlencode, urlparse

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import Principal, _from_session, audit, build_principal, client_ip, rate_limit, require, to_dict
from app.mode import vuln
from app.models import Membership, OAuthClient, OAuthCode, OAuthToken, Organization, User, now
from app.rbac import OAUTH_SCOPES, perm_to_scope
from app.security import ensure_keys, issue_jwt, keys, rand, sha256

router = APIRouter(tags=["oauth"])
api = APIRouter(prefix="/api/oauth", tags=["oauth"])
settings = get_settings()


def aware(dt):
    return dt if dt.tzinfo else dt.replace(tzinfo=now().tzinfo)


def cookie_principal(request: Request, db: Session):
    sid = request.cookies.get("vc_session")
    if not sid:
        return None
    try:
        p = _from_session(db, sid, request)
    except HTTPException:
        return None
    return p if p.stage == "authenticated" else None


def find_client(db: Session, client_id: str) -> OAuthClient | None:
    return db.query(OAuthClient).filter(OAuthClient.client_id == client_id, OAuthClient.active.is_(True)).first()


def redirect_allowed(c: OAuthClient, uri: str) -> bool:
    if vuln("oauth_redirect"):
        return any(uri.startswith(r) for r in c.redirect_uris)
    return uri in c.redirect_uris


def user_scopes(p: Principal) -> set:
    return {perm_to_scope(x) for x in p.perms} | {"openid", "profile", "email"} | ({"admin"} if p.role.key in ("org_admin", "super_admin") else set())


def error_page(msg: str, status=400):
    return HTMLResponse(f"<!doctype html><title>Authorization error</title><body style='font:16px system-ui;margin:48px'><h2>Authorization error</h2><p>{html.escape(msg)}</p></body>", status_code=status)


def authorize_params(request: Request, q: dict):
    return {k: q.get(k) for k in ("response_type", "client_id", "redirect_uri", "scope", "state", "code_challenge", "code_challenge_method", "nonce")}


def validate_authz(db: Session, q: dict):
    c = find_client(db, q.get("client_id") or "")
    if not c:
        return None, error_page("Unknown client")
    uri = q.get("redirect_uri") or (c.redirect_uris[0] if len(c.redirect_uris) == 1 else None)
    if not uri or not redirect_allowed(c, uri):
        if vuln("oauth_redirect") and uri:
            return None, RedirectResponse(f"{uri}?{urlencode({'error': 'invalid_request', 'state': q.get('state') or ''})}", status_code=302)
        return None, error_page("Invalid redirect URI")
    q["redirect_uri"] = uri
    if q.get("response_type") != "code":
        return None, RedirectResponse(f"{uri}?{urlencode({'error': 'unsupported_response_type', 'state': q.get('state') or ''})}", status_code=302)
    if c.require_pkce and not vuln("oauth_pkce"):
        if not q.get("code_challenge") or q.get("code_challenge_method") != "S256":
            return None, RedirectResponse(f"{uri}?{urlencode({'error': 'invalid_request', 'error_description': 'PKCE with S256 is required', 'state': q.get('state') or ''})}", status_code=302)
    return c, None


@router.get("/oauth/authorize")
def authorize(request: Request, db: Session = Depends(get_db)):
    q = authorize_params(request, dict(request.query_params))
    c, err = validate_authz(db, q)
    if err:
        return err
    p = cookie_principal(request, db)
    if not p:
        return RedirectResponse(f"/login?next={quote(str(request.url.path) + '?' + request.url.query)}", status_code=302)
    requested = [s for s in (q.get("scope") or "").split() if s]
    allowed = user_scopes(p)
    granted = requested if vuln("oauth_scope") else [s for s in requested if s in (c.scopes or []) and s in allowed]
    csrf = request.cookies.get("vc_csrf", "")
    hidden = "".join(f"<input type='hidden' name='{k}' value=\"{html.escape(v or '')}\">" for k, v in q.items() if k not in ("scope",))
    items = "".join(f"<li><b>{html.escape(s)}</b> — {html.escape(OAUTH_SCOPES.get(s, 'Custom scope'))}</li>" for s in granted) or "<li>No permissions requested</li>"
    page = (f"<!doctype html><html><head><meta charset='utf-8'><title>Authorize {html.escape(c.name)}</title><style>body{{font:15px system-ui;background:#f8fafc;display:grid;place-items:center;min-height:100vh;margin:0}}"
            f".card{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:32px;width:420px}}button{{padding:10px 16px;border-radius:8px;border:0;cursor:pointer;font-weight:600}}.ok{{background:#4F46E5;color:#fff}}.no{{background:#f1f5f9}}</style></head>"
            f"<body><form class='card' method='post' action='/oauth/authorize'><h2 style='margin-top:0'>Authorize {html.escape(c.name)}</h2><p>Signed in as <b>{html.escape(p.user.email)}</b> in <b>{html.escape(db.get(Organization, p.org_id).name)}</b>.</p>"
            f"<p>This application is requesting:</p><ul>{items}</ul>{hidden}<input type='hidden' name='scope' value=\"{html.escape(' '.join(granted))}\"><input type='hidden' name='csrf' value=\"{html.escape(csrf)}\">"
            f"<div style='display:flex;gap:8px;margin-top:20px'><button class='ok' name='decision' value='approve'>Allow</button><button class='no' name='decision' value='deny'>Deny</button></div></form></body></html>")
    return HTMLResponse(page, headers={"X-Frame-Options": "DENY"} if not vuln("misconfig_headers") else {})


@router.post("/oauth/authorize")
async def authorize_decision(request: Request, db: Session = Depends(get_db)):
    form = dict((await request.form()).items())
    p = cookie_principal(request, db)
    if not p:
        raise HTTPException(401, "Authentication required")
    if not vuln("csrf") and form.get("csrf") != request.cookies.get("vc_csrf"):
        raise HTTPException(403, "CSRF token missing or invalid")
    q = authorize_params(request, form)
    c, err = validate_authz(db, q)
    if err:
        return err
    uri, state = q["redirect_uri"], q.get("state")
    sep = "&" if "?" in uri else "?"
    if form.get("decision") != "approve":
        return RedirectResponse(f"{uri}{sep}{urlencode({'error': 'access_denied', **({'state': state} if state else {})})}", status_code=302)
    requested = [s for s in (form.get("scope") or "").split() if s]
    scope = requested if vuln("oauth_scope") else [s for s in requested if s in (c.scopes or []) and s in user_scopes(p)]
    code = rand(24)
    db.add(OAuthCode(code=code, client_id=c.client_id, user_id=p.user.id, org_id=p.org_id, scope=" ".join(scope), redirect_uri=uri, code_challenge=q.get("code_challenge"),
                     code_challenge_method=q.get("code_challenge_method"), nonce=q.get("nonce"), expires_at=now() + timedelta(seconds=settings.oauth_code_ttl)))
    audit(db, p, "oauth.authorize", "oauth_client", c.client_id, {"scope": scope}, ip=client_ip(request))
    db.commit()
    return RedirectResponse(f"{uri}{sep}{urlencode({'code': code, **({'state': state} if state else {})})}", status_code=302)


def err(code: str, desc: str, status: int = 400):
    return JSONResponse({"error": code, "error_description": desc}, status_code=status, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})


def client_credentials(request: Request, form: dict, db: Session):
    cid, secret = form.get("client_id"), form.get("client_secret")
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("basic "):
        try:
            cid, secret = base64.b64decode(auth[6:]).decode().split(":", 1)
        except Exception:
            return None, err("invalid_client", "Malformed credentials", 401)
    if vuln("oauth_client_auth") and not secret:
        secret = request.query_params.get("client_secret")
    c = find_client(db, cid or "")
    if not c:
        return None, err("invalid_client", "Unknown client", 401)
    if c.public:
        return c, None
    if not secret:
        if vuln("oauth_client_auth") and form.get("grant_type") in ("authorization_code", "refresh_token"):
            return c, None
        return None, err("invalid_client", "Client authentication required", 401)
    ok = (secret == c.client_secret_plain) if vuln("oauth_client_auth") and c.client_secret_plain else hmac.compare_digest(sha256(secret), c.client_secret_hash or "")
    if not ok:
        return None, err("invalid_client", "Invalid client credentials", 401)
    return c, None


def mint(db: Session, c: OAuthClient, user_id, org_id: int, scope: str, family: str | None = None, nonce: str | None = None, with_refresh: bool = True):
    access, refresh = "vco_" + rand(32), "vcr_" + rand(32)
    long = vuln("oauth_expiry")
    access_ttl = 315360000 if long else min(settings.oauth_access_ttl, 900)
    t = OAuthToken(access_hash=sha256(access), refresh_hash=sha256(refresh) if with_refresh else None, client_id=c.client_id, user_id=user_id, org_id=org_id, scope=scope, family=family or rand(8),
                   expires_at=now() + timedelta(seconds=access_ttl), refresh_expires_at=(now() + timedelta(seconds=315360000 if long else settings.oauth_refresh_ttl)) if with_refresh else None)
    db.add(t)
    out = {"access_token": access, "token_type": "Bearer", "expires_in": access_ttl, "scope": scope}
    if with_refresh:
        out["refresh_token"] = refresh
    if "openid" in scope.split() and user_id:
        u = db.get(User, user_id)
        claims = {"sub": str(u.id), "nonce": nonce, "auth_time": int(now().timestamp()), "org": org_id}
        if "email" in scope.split():
            claims.update({"email": u.email, "email_verified": True})
        if "profile" in scope.split():
            claims["name"] = u.name
        out["id_token"] = issue_jwt({k: v for k, v in claims.items() if v is not None}, access_ttl if access_ttl < 3600 else 3600, audience=c.client_id)
    return out


@router.post("/oauth/token")
async def token(request: Request, db: Session = Depends(get_db)):
    form = dict((await request.form()).items())
    rate_limit(request, "oauth-token", 60, 60)
    grant = form.get("grant_type")
    c, e = client_credentials(request, form, db)
    if e:
        return e
    if grant not in (c.grant_types or []):
        return err("unauthorized_client", "Grant type not allowed for this client")
    if grant == "authorization_code":
        code = db.query(OAuthCode).filter(OAuthCode.code == (form.get("code") or "")).first()
        if not code or code.client_id != c.client_id:
            return err("invalid_grant", "Invalid authorization code")
        if code.used:
            if not vuln("oauth_code_reuse"):
                db.query(OAuthToken).filter(OAuthToken.client_id == c.client_id, OAuthToken.user_id == code.user_id, OAuthToken.created_at >= code.expires_at - timedelta(seconds=settings.oauth_code_ttl + 5)).update({"revoked": True})
                db.commit()
                return err("invalid_grant", "Authorization code already used")
        elif aware(code.expires_at) < now():
            return err("invalid_grant", "Authorization code expired")
        if (form.get("redirect_uri") or code.redirect_uri) != code.redirect_uri:
            return err("invalid_grant", "redirect_uri mismatch")
        if code.code_challenge:
            ver = form.get("code_verifier") or ""
            if code.code_challenge_method == "S256":
                calc = base64.urlsafe_b64encode(hashlib.sha256(ver.encode()).digest()).rstrip(b"=").decode()
            else:
                calc = ver
            if not hmac.compare_digest(calc, code.code_challenge):
                return err("invalid_grant", "PKCE verification failed")
        elif c.require_pkce and not vuln("oauth_pkce"):
            return err("invalid_grant", "PKCE is required")
        code.used = True
        out = mint(db, c, code.user_id, code.org_id, code.scope, nonce=code.nonce)
        db.commit()
        return JSONResponse(out, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})
    if grant == "refresh_token":
        rt = form.get("refresh_token") or ""
        tok = db.query(OAuthToken).filter(OAuthToken.refresh_hash == sha256(rt)).first()
        if not tok or tok.client_id != c.client_id:
            if not vuln("oauth_refresh"):
                reused = db.query(OAuthToken).filter(OAuthToken.client_id == c.client_id, OAuthToken.revoked.is_(True), OAuthToken.refresh_hash == sha256(rt)).first()
            return err("invalid_grant", "Invalid refresh token")
        if tok.revoked and not vuln("oauth_refresh"):
            db.query(OAuthToken).filter(OAuthToken.family == tok.family).update({"revoked": True})
            db.commit()
            return err("invalid_grant", "Refresh token reuse detected. All tokens in this session were revoked.")
        if tok.refresh_expires_at and aware(tok.refresh_expires_at) < now():
            return err("invalid_grant", "Refresh token expired")
        scope = tok.scope
        if form.get("scope"):
            req = form["scope"].split()
            scope = " ".join(req) if vuln("oauth_scope") else " ".join(s for s in req if s in tok.scope.split())
        if not vuln("oauth_refresh"):
            tok.revoked = True
        out = mint(db, c, tok.user_id, tok.org_id, scope, family=tok.family)
        db.commit()
        return JSONResponse(out, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})
    if grant == "client_credentials":
        req = (form.get("scope") or "").split()
        scope = " ".join(req) if vuln("oauth_scope") else " ".join(s for s in req if s in (c.scopes or []))
        out = mint(db, c, None, c.org_id, scope, with_refresh=False)
        db.commit()
        return JSONResponse(out, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})
    return err("unsupported_grant_type", "Unsupported grant type")


@router.post("/oauth/revoke")
async def revoke(request: Request, db: Session = Depends(get_db)):
    form = dict((await request.form()).items())
    c, e = client_credentials(request, form, db)
    if e:
        return e
    tok = form.get("token") or ""
    h = sha256(tok)
    t = db.query(OAuthToken).filter((OAuthToken.access_hash == h) | (OAuthToken.refresh_hash == h)).first()
    if t and t.client_id == c.client_id:
        db.query(OAuthToken).filter(OAuthToken.family == t.family).update({"revoked": True})
        db.commit()
    return JSONResponse({})


@router.post("/oauth/introspect")
async def introspect(request: Request, db: Session = Depends(get_db)):
    form = dict((await request.form()).items())
    c, e = client_credentials(request, form, db)
    if e:
        return e
    t = db.query(OAuthToken).filter(OAuthToken.access_hash == sha256(form.get("token") or "")).first()
    if not t or t.revoked or aware(t.expires_at) < now() or t.client_id != c.client_id:
        return {"active": False}
    return {"active": True, "scope": t.scope, "client_id": t.client_id, "sub": str(t.user_id) if t.user_id else None, "exp": int(aware(t.expires_at).timestamp()), "token_type": "Bearer"}


@router.get("/oauth/userinfo")
def userinfo(request: Request, db: Session = Depends(get_db)):
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer vco_"):
        raise HTTPException(401, "Bearer access token required", headers={"WWW-Authenticate": "Bearer"})
    t = db.query(OAuthToken).filter(OAuthToken.access_hash == sha256(auth[7:].strip())).first()
    if not t or t.revoked or aware(t.expires_at) < now() or not t.user_id:
        raise HTTPException(401, "Invalid token", headers={"WWW-Authenticate": "Bearer"})
    scopes = t.scope.split()
    if "openid" not in scopes:
        raise HTTPException(403, "The openid scope is required")
    u = db.get(User, t.user_id)
    out = {"sub": str(u.id)}
    if "profile" in scopes:
        out["name"] = u.name
    if "email" in scopes:
        out.update({"email": u.email, "email_verified": True})
    return out


@router.get("/.well-known/openid-configuration")
def discovery():
    base = settings.public_base_url.rstrip("/")
    return {"issuer": settings.jwt_issuer, "authorization_endpoint": f"{base}/oauth/authorize", "token_endpoint": f"{base}/oauth/token", "userinfo_endpoint": f"{base}/oauth/userinfo",
            "jwks_uri": f"{base}/oidc/jwks.json", "revocation_endpoint": f"{base}/oauth/revoke", "introspection_endpoint": f"{base}/oauth/introspect",
            "response_types_supported": ["code"], "grant_types_supported": ["authorization_code", "refresh_token", "client_credentials"], "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"], "scopes_supported": list(OAUTH_SCOPES), "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post", "none"],
            "code_challenge_methods_supported": ["S256"], "claims_supported": ["sub", "name", "email", "email_verified", "nonce", "org"]}


@router.get("/oidc/jwks.json")
def jwks():
    ensure_keys()
    return keys.jwks()


def client_ser(c: OAuthClient) -> dict:
    return to_dict(c, exclude=("client_secret_hash", "client_secret_plain"))


@api.get("/clients")
def list_clients(p: Principal = Depends(require("oauth.manage")), db: Session = Depends(get_db)):
    return {"items": [client_ser(c) for c in db.query(OAuthClient).filter(OAuthClient.org_id == p.org_id).order_by(OAuthClient.name).all()], "available_scopes": OAUTH_SCOPES}


@api.post("/clients", status_code=201)
def create_client(body: dict, request: Request, p: Principal = Depends(require("oauth.manage")), db: Session = Depends(get_db)):
    if not body.get("name"):
        raise HTTPException(422, "Name is required")
    uris = [u for u in body.get("redirect_uris", []) if urlparse(u).scheme in ("http", "https")]
    grants = [g for g in body.get("grant_types", ["authorization_code", "refresh_token"]) if g in ("authorization_code", "refresh_token", "client_credentials")]
    public = bool(body.get("public"))
    secret = None if public else "vcs_" + rand(32)
    c = OAuthClient(org_id=p.org_id, client_id="vc_" + secrets.token_hex(8), client_secret_hash=sha256(secret) if secret else None, client_secret_plain=secret if vuln("oauth_client_auth") else None,
                    name=body["name"], redirect_uris=uris, grant_types=grants, scopes=[s for s in body.get("scopes", []) if s in OAUTH_SCOPES], public=public, require_pkce=bool(body.get("require_pkce", True)))
    db.add(c)
    db.flush()
    audit(db, p, "oauth_client.create", "oauth_client", c.client_id, {"redirect_uris": uris}, ip=client_ip(request))
    db.commit()
    return {**client_ser(c), "client_secret": secret}


@api.patch("/clients/{cid}")
def update_client(cid: int, body: dict, request: Request, p: Principal = Depends(require("oauth.manage")), db: Session = Depends(get_db)):
    c = db.get(OAuthClient, cid) if vuln("bola") else db.query(OAuthClient).filter(OAuthClient.id == cid, OAuthClient.org_id == p.org_id).first()
    if not c:
        raise HTTPException(404, "Not found")
    if "redirect_uris" in body:
        c.redirect_uris = [u for u in body["redirect_uris"] if urlparse(u).scheme in ("http", "https")]
    if "scopes" in body:
        c.scopes = [s for s in body["scopes"] if s in OAUTH_SCOPES]
    for k in ("name", "active", "require_pkce"):
        if k in body:
            setattr(c, k, body[k])
    audit(db, p, "oauth_client.update", "oauth_client", c.client_id, {"fields": list(body)}, ip=client_ip(request))
    db.commit()
    return client_ser(c)


@api.post("/clients/{cid}/rotate-secret")
def rotate(cid: int, request: Request, p: Principal = Depends(require("oauth.manage")), db: Session = Depends(get_db)):
    c = db.query(OAuthClient).filter(OAuthClient.id == cid, OAuthClient.org_id == p.org_id).first()
    if not c or c.public:
        raise HTTPException(404, "Not found")
    secret = "vcs_" + rand(32)
    c.client_secret_hash, c.client_secret_plain = sha256(secret), secret if vuln("oauth_client_auth") else None
    db.query(OAuthToken).filter(OAuthToken.client_id == c.client_id).update({"revoked": True})
    audit(db, p, "oauth_client.secret_rotated", "oauth_client", c.client_id, ip=client_ip(request))
    db.commit()
    return {"client_secret": secret}


@api.delete("/clients/{cid}")
def delete_client(cid: int, p: Principal = Depends(require("oauth.manage")), db: Session = Depends(get_db)):
    c = db.query(OAuthClient).filter(OAuthClient.id == cid, OAuthClient.org_id == p.org_id).first()
    if not c:
        raise HTTPException(404, "Not found")
    c.active = False
    db.query(OAuthToken).filter(OAuthToken.client_id == c.client_id).update({"revoked": True})
    audit(db, p, "oauth_client.delete", "oauth_client", c.client_id)
    db.commit()
    return {"ok": True}


@api.get("/tokens")
def list_tokens(p: Principal = Depends(require("oauth.manage")), db: Session = Depends(get_db)):
    rows = db.query(OAuthToken).filter(OAuthToken.org_id == p.org_id).order_by(OAuthToken.created_at.desc()).limit(100).all()
    return {"items": [to_dict(t, exclude=("access_hash", "refresh_hash")) for t in rows]}


@api.delete("/tokens/{tid}")
def revoke_token(tid: int, p: Principal = Depends(require("oauth.manage")), db: Session = Depends(get_db)):
    t = db.query(OAuthToken).filter(OAuthToken.id == tid, OAuthToken.org_id == p.org_id).first()
    if not t:
        raise HTTPException(404, "Not found")
    db.query(OAuthToken).filter(OAuthToken.family == t.family).update({"revoked": True})
    audit(db, p, "oauth_token.revoke", "oauth_token", tid)
    db.commit()
    return {"ok": True}
