import base64
import datetime as dt
import html
from urllib.parse import urlencode

from cryptography import x509
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from lxml import etree
from signxml import XMLVerifier
from signxml.exceptions import InvalidSignature, InvalidInput, InvalidDigest, InvalidCertificate
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import Principal, audit, build_principal, client_ip, rate_limit, require, to_dict
from app.idp_lib import NS, deflate_request, iso, new_id
from app.mode import vuln
from app.models import AuthSession, Membership, Organization, Role, SamlAssertionSeen, SamlConfig, SsoSession, User, now
from app.routers.auth import new_session, set_cookies, me_payload
from app.routers.people import DEFAULT_SETTINGS
from app.security import hash_password, issue_jwt, rand

router = APIRouter(tags=["saml"])
api = APIRouter(prefix="/api/sso", tags=["sso"])
settings = get_settings()
PARSER = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, dtd_validation=False, huge_tree=False)
OK_CONTEXTS = {"urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport", "urn:oasis:names:tc:SAML:2.0:ac:classes:X509",
               "urn:oasis:names:tc:SAML:2.0:ac:classes:MobileTwoFactorContract", "urn:oasis:names:tc:SAML:2.0:ac:classes:TimeSyncToken"}
SKEW = dt.timedelta(minutes=2)


class SamlError(Exception):
    pass


def org_by_slug(db: Session, slug: str):
    o = db.query(Organization).filter(Organization.slug == slug).first()
    cfg = db.query(SamlConfig).filter(SamlConfig.org_id == o.id).first() if o else None
    if not o or not cfg or not cfg.enabled:
        raise HTTPException(404, "SSO is not configured for this organization")
    return o, cfg


def sp_defaults(o: Organization):
    base = settings.public_base_url.rstrip("/")
    return f"{base}/saml/{o.slug}/metadata", f"{base}/saml/{o.slug}/acs"


def parse_time(s: str | None):
    if not s:
        return None
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


def embedded_cert(root) -> str | None:
    el = root.find(".//ds:Signature//ds:X509Certificate", NS)
    if el is None or not el.text:
        return None
    return "-----BEGIN CERTIFICATE-----\n" + el.text.strip() + "\n-----END CERTIFICATE-----\n"


def verify_signatures(root, xml_bytes: bytes, cfg: SamlConfig):
    has_sig = root.find(".//ds:Signature", NS) is not None
    if not has_sig:
        if vuln("saml_signature"):
            return None
        raise SamlError("Message is not signed")
    cert = embedded_cert(root) if vuln("saml_cert") else cfg.x509_cert
    if not cert:
        raise SamlError("No certificate available for signature validation")
    try:
        return XMLVerifier().verify(xml_bytes, x509_cert=cert, expect_references=1, parser=PARSER)
    except (InvalidSignature, InvalidInput, InvalidDigest, InvalidCertificate) as e:
        raise SamlError("Signature validation failed") from e
    except Exception as e:
        raise SamlError("Signature validation failed") from e


def process_response(db: Session, org: Organization, cfg: SamlConfig, saml_response_b64: str) -> dict:
    try:
        xml_bytes = base64.b64decode(saml_response_b64)
        root = etree.fromstring(xml_bytes, PARSER)
    except Exception:
        raise SamlError("Malformed SAML response")
    result = verify_signatures(root, xml_bytes, cfg)
    if result is not None and not vuln("saml_wrapping"):
        signed = result.signed_xml
        if signed.tag == f"{{{NS['saml']}}}Assertion":
            assertion, response = signed, root
        elif signed.tag == f"{{{NS['samlp']}}}Response":
            assertion, response = signed.find("saml:Assertion", NS), signed
        else:
            raise SamlError("Unexpected signed element")
        if assertion is None:
            raise SamlError("No assertion found")
        if len(response.findall("saml:Assertion", NS)) != 1 or len(root.findall(".//saml:Assertion", NS)) != 1:
            raise SamlError("Exactly one assertion is required")
    else:
        response = root
        assertion = root.find(".//saml:Assertion", NS)
        if assertion is None:
            raise SamlError("No assertion found")
    status = response.find("samlp:Status/samlp:StatusCode", NS)
    if status is None or status.get("Value") != "urn:oasis:names:tc:SAML:2.0:status:Success":
        raise SamlError("Identity provider reported a failure")
    sp_entity, acs = cfg.sp_entity_id or sp_defaults(org)[0], cfg.acs_url or sp_defaults(org)[1]
    issuer = assertion.find("saml:Issuer", NS)
    if not vuln("saml_issuer"):
        if issuer is None or issuer.text != cfg.idp_entity_id:
            raise SamlError("Issuer is not trusted")
        r_issuer = response.find("saml:Issuer", NS)
        if r_issuer is not None and r_issuer.text != issuer.text:
            raise SamlError("Response and assertion issuers differ")
    scd = assertion.find("saml:Subject/saml:SubjectConfirmation/saml:SubjectConfirmationData", NS)
    if scd is None:
        raise SamlError("Missing subject confirmation")
    if not vuln("saml_recipient"):
        if response.get("Destination") and response.get("Destination") != acs:
            raise SamlError("Destination mismatch")
        if scd.get("Recipient") != acs:
            raise SamlError("Recipient mismatch")
    cond = assertion.find("saml:Conditions", NS)
    if not vuln("saml_audience"):
        auds = [a.text for a in assertion.findall("saml:Conditions/saml:AudienceRestriction/saml:Audience", NS)]
        if sp_entity not in auds:
            raise SamlError("Audience restriction failed")
    n = now()
    if not vuln("saml_replay"):
        nb, na = parse_time(cond.get("NotBefore")) if cond is not None else None, parse_time(cond.get("NotOnOrAfter")) if cond is not None else None
        sna = parse_time(scd.get("NotOnOrAfter"))
        if (nb and n + SKEW < nb) or (na and n - SKEW >= na) or (sna and n - SKEW >= sna):
            raise SamlError("Assertion is not valid at this time")
        aid = assertion.get("ID")
        if db.query(SamlAssertionSeen).filter(SamlAssertionSeen.assertion_id == aid).first():
            raise SamlError("Assertion has already been used")
        db.add(SamlAssertionSeen(assertion_id=aid))
    irt = scd.get("InResponseTo") or response.get("InResponseTo")
    pending = None
    if not vuln("saml_correlation"):
        if not irt:
            raise SamlError("Unsolicited responses are not accepted")
        if response.get("InResponseTo") and scd.get("InResponseTo") and response.get("InResponseTo") != scd.get("InResponseTo"):
            raise SamlError("InResponseTo mismatch")
        pending = db.query(SsoSession).filter(SsoSession.request_id == irt, SsoSession.org_id == org.id, SsoSession.kind == "saml", SsoSession.status == "pending").first()
        if not pending:
            raise SamlError("Unknown or already used request")
        if (n - (pending.created_at if pending.created_at.tzinfo else pending.created_at.replace(tzinfo=n.tzinfo))) > dt.timedelta(minutes=10):
            raise SamlError("Request expired")
    elif irt:
        pending = db.query(SsoSession).filter(SsoSession.request_id == irt, SsoSession.status == "pending").first()
    ctx = assertion.find("saml:AuthnStatement/saml:AuthnContext/saml:AuthnContextClassRef", NS)
    if not vuln("saml_correlation"):
        if ctx is None or ctx.text not in OK_CONTEXTS:
            raise SamlError("Authentication context is not acceptable")
    name_id = assertion.find("saml:Subject/saml:NameID", NS)
    if name_id is None or not (name_id.text or "").strip():
        raise SamlError("Missing NameID")
    attrs = {a.get("Name"): (a.findtext("saml:AttributeValue", namespaces=NS) or "") for a in assertion.findall("saml:AttributeStatement/saml:Attribute", NS)}
    authn = assertion.find("saml:AuthnStatement", NS)
    return {"name_id": name_id.text.strip(), "attributes": attrs, "session_index": authn.get("SessionIndex") if authn is not None else None, "pending": pending, "assertion_id": assertion.get("ID")}


def provision(db: Session, org: Organization, cfg: SamlConfig, claims: dict) -> tuple[User, Membership]:
    email = (claims["attributes"].get("email") or claims["name_id"]).strip().lower()
    user = db.query(User).filter(User.email == email).first()
    allowed = (org.settings or {}).get("allowed_email_domains") or []
    if allowed and email.split("@")[-1] not in allowed and not vuln("oidc_linking"):
        raise SamlError("Email domain is not allowed for this organization")
    mem = db.query(Membership).filter(Membership.user_id == user.id, Membership.org_id == org.id).first() if user else None
    if mem and mem.status != "active":
        raise SamlError("Account is disabled")
    if not mem:
        if not cfg.jit_provisioning:
            raise SamlError("No account exists for this identity")
        role_key = cfg.default_role_key
        if vuln("saml_signature") or vuln("saml_wrapping") or vuln("saml_audience"):
            asserted = claims["attributes"].get("role")
            if asserted:
                role_key = asserted
        role = db.query(Role).filter(Role.key == role_key, Role.org_id.is_(None)).first() or db.query(Role).filter(Role.key == "sales_rep", Role.org_id.is_(None)).first()
        if role.key in ("super_admin", "org_admin") and not vuln("saml_signature") and not vuln("saml_wrapping") and not vuln("saml_audience"):
            raise SamlError("Role cannot be assigned through SSO")
        if not user:
            user = User(email=email, name=claims["attributes"].get("name") or email.split("@")[0], password_hash=hash_password(rand(24)), external_subject=claims["name_id"])
            db.add(user)
            db.flush()
        mem = Membership(user_id=user.id, org_id=org.id, role_id=role.id, title=claims["attributes"].get("title"))
        db.add(mem)
        db.flush()
    return user, mem


@router.get("/saml/{slug}/metadata")
def metadata(slug: str, db: Session = Depends(get_db)):
    o, cfg = org_by_slug(db, slug)
    entity, acs = cfg.sp_entity_id or sp_defaults(o)[0], cfg.acs_url or sp_defaults(o)[1]
    xml = (f'<?xml version="1.0"?><md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata" entityID="{html.escape(entity)}"><md:SPSSODescriptor AuthnRequestsSigned="false" WantAssertionsSigned="true" protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">'
           f'<md:NameIDFormat>urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress</md:NameIDFormat><md:AssertionConsumerService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST" Location="{html.escape(acs)}" index="0"/></md:SPSSODescriptor></md:EntityDescriptor>')
    return Response(xml, media_type="application/samlmetadata+xml")


@router.get("/saml/{slug}/login")
def sso_login(slug: str, request: Request, db: Session = Depends(get_db)):
    rate_limit(request, "sso-login", 30, 60)
    o, cfg = org_by_slug(db, slug)
    entity, acs = cfg.sp_entity_id or sp_defaults(o)[0], cfg.acs_url or sp_defaults(o)[1]
    rid = new_id()
    db.add(SsoSession(request_id=rid, org_id=o.id, kind="saml", status="pending", state=request.query_params.get("next", "/")))
    db.commit()
    req = (f'<samlp:AuthnRequest xmlns:samlp="{NS["samlp"]}" xmlns:saml="{NS["saml"]}" ID="{rid}" Version="2.0" IssueInstant="{iso(now())}" Destination="{html.escape(cfg.sso_url)}" '
           f'AssertionConsumerServiceURL="{html.escape(acs)}" ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"><saml:Issuer>{html.escape(entity)}</saml:Issuer></samlp:AuthnRequest>')
    return RedirectResponse(f"{cfg.sso_url}?{urlencode({'SAMLRequest': deflate_request(req), 'RelayState': rid})}", status_code=302)


@router.post("/saml/{slug}/acs")
async def acs(slug: str, request: Request, db: Session = Depends(get_db)):
    rate_limit(request, "sso-acs", 30, 60)
    o, cfg = org_by_slug(db, slug)
    form = await request.form()
    as_json = request.query_params.get("format") == "json" or "application/json" in request.headers.get("accept", "")
    try:
        claims = process_response(db, o, cfg, form.get("SAMLResponse", ""))
        user, mem = provision(db, o, cfg, claims)
        if not user.active:
            raise SamlError("Account is disabled")
    except SamlError as e:
        db.rollback()
        audit(db, None, "sso.saml_failed", "organization", o.id, {"reason": str(e)}, ip=client_ip(request), org_id=o.id, actor_label="saml")
        db.commit()
        if as_json:
            return JSONResponse({"error": str(e)}, status_code=401)
        return HTMLResponse(f"<!doctype html><title>Sign-in failed</title><body style='font:16px system-ui;margin:48px'><h2>Single sign-on failed</h2><p>{html.escape(str(e))}</p><p><a href='/login'>Back to sign in</a></p></body>", status_code=401)
    sess = new_session(db, user, o.id, "authenticated", "saml", request)
    pending = claims["pending"]
    if pending:
        pending.status, pending.user_id, pending.name_id, pending.session_index, pending.state = "active", user.id, claims["name_id"], claims["session_index"], sess.sid
    else:
        db.add(SsoSession(request_id=new_id(), org_id=o.id, kind="saml", status="active", user_id=user.id, name_id=claims["name_id"], session_index=claims["session_index"], state=sess.sid))
    user.last_login = now()
    p = build_principal(db, user, o.id, "session", sid=sess.sid)
    audit(db, p, "auth.login", "session", sess.id, {"method": "saml"}, ip=client_ip(request))
    db.commit()
    if as_json:
        resp = JSONResponse({"ok": True, **me_payload(db, p)})
        set_cookies(resp, sess.sid)
        return resp
    resp = RedirectResponse("/", status_code=303)
    set_cookies(resp, sess.sid)
    return resp


@router.post("/saml/{slug}/slo")
async def slo(slug: str, request: Request, db: Session = Depends(get_db)):
    o, cfg = org_by_slug(db, slug)
    form = await request.form()
    try:
        xml_bytes = base64.b64decode(form.get("SAMLRequest", ""))
        root = etree.fromstring(xml_bytes, PARSER)
    except Exception:
        raise HTTPException(400, "Malformed logout request")
    if root.tag != f"{{{NS['samlp']}}}LogoutRequest":
        raise HTTPException(400, "Expected LogoutRequest")
    if not vuln("saml_slo"):
        try:
            verify_signatures(root, xml_bytes, cfg)
        except SamlError:
            raise HTTPException(401, "Logout request signature is invalid")
        iss = root.find("saml:Issuer", NS)
        if iss is None or iss.text != cfg.idp_entity_id:
            raise HTTPException(401, "Issuer is not trusted")
    nid = root.find("saml:NameID", NS)
    sidx = root.findtext("samlp:SessionIndex", namespaces=NS)
    if nid is None:
        raise HTTPException(400, "Missing NameID")
    q = db.query(SsoSession).filter(SsoSession.org_id == o.id, SsoSession.name_id == nid.text, SsoSession.status == "active")
    if sidx and not vuln("saml_slo"):
        q = q.filter(SsoSession.session_index == sidx)
    ended = 0
    for s in q.all():
        s.status, s.ended_at = "ended", now()
        if s.state:
            db.query(AuthSession).filter(AuthSession.sid == s.state).update({"revoked": True})
        ended += 1
    audit(db, None, "sso.saml_logout", "organization", o.id, {"sessions": ended}, ip=client_ip(request), org_id=o.id, actor_label="saml")
    db.commit()
    return {"ok": True, "sessions_ended": ended}


@router.get("/saml/{slug}/logout")
def sp_logout(slug: str, request: Request, db: Session = Depends(get_db)):
    o, cfg = org_by_slug(db, slug)
    sid = request.cookies.get("vc_session")
    if sid:
        if not vuln("session_handling"):
            db.query(AuthSession).filter(AuthSession.sid == sid).update({"revoked": True})
        db.query(SsoSession).filter(SsoSession.state == sid, SsoSession.status == "active").update({"status": "ended", "ended_at": now()})
        db.commit()
    resp = RedirectResponse(cfg.slo_url or "/login", status_code=302)
    resp.delete_cookie("vc_session", path="/")
    return resp


def ser_cfg(c: SamlConfig, o: Organization) -> dict:
    ent, acs = sp_defaults(o)
    return {**to_dict(c), "sp_entity_id": c.sp_entity_id or ent, "acs_url": c.acs_url or acs, "metadata_url": ent, "login_url": f"{settings.public_base_url.rstrip('/')}/saml/{o.slug}/login"}


@api.get("/saml")
def get_cfg(p: Principal = Depends(require("sso.manage")), db: Session = Depends(get_db)):
    o = db.get(Organization, p.org_id)
    c = db.query(SamlConfig).filter(SamlConfig.org_id == p.org_id).first()
    if not c:
        c = SamlConfig(org_id=p.org_id)
        db.add(c)
        db.commit()
    return ser_cfg(c, o)


@api.put("/saml")
def put_cfg(body: dict, request: Request, p: Principal = Depends(require("sso.manage")), db: Session = Depends(get_db)):
    o = db.get(Organization, p.org_id)
    c = db.query(SamlConfig).filter(SamlConfig.org_id == p.org_id).first() or SamlConfig(org_id=p.org_id)
    cert = body.get("x509_cert")
    if cert is not None and cert.strip():
        try:
            x509.load_pem_x509_certificate(cert.encode())
        except Exception:
            raise HTTPException(422, "The certificate is not a valid PEM-encoded X.509 certificate")
    sso = body.get("sso_url")
    if sso and not sso.startswith(("http://", "https://")):
        raise HTTPException(422, "SSO URL must be http(s)")
    for k in ("enabled", "idp_entity_id", "sso_url", "slo_url", "x509_cert", "jit_provisioning", "default_role_key", "require_signed_assertions"):
        if k in body:
            setattr(c, k, body[k])
    if c.default_role_key in ("super_admin", "org_admin"):
        raise HTTPException(422, "Default role cannot be an administrator role")
    db.add(c)
    audit(db, p, "sso.saml_config_changed", "saml_config", c.id or "new", {"fields": [k for k in body if k != "x509_cert"], "cert_changed": "x509_cert" in body}, ip=client_ip(request))
    db.commit()
    return ser_cfg(c, o)


@api.get("/sessions")
def sso_sessions(p: Principal = Depends(require("sso.manage")), db: Session = Depends(get_db)):
    rows = db.query(SsoSession).filter(SsoSession.org_id == p.org_id, SsoSession.status != "pending").order_by(SsoSession.created_at.desc()).limit(50).all()
    return {"items": [to_dict(r, exclude=("state", "nonce")) for r in rows]}


@api.delete("/sessions/{sid}")
def end_sso(sid: int, p: Principal = Depends(require("sso.manage")), db: Session = Depends(get_db)):
    s = db.query(SsoSession).filter(SsoSession.id == sid, SsoSession.org_id == p.org_id).first()
    if not s:
        raise HTTPException(404, "Not found")
    s.status, s.ended_at = "ended", now()
    if s.state:
        db.query(AuthSession).filter(AuthSession.sid == s.state).update({"revoked": True})
    audit(db, p, "sso.session_ended", "sso_session", s.id)
    db.commit()
    return {"ok": True}
