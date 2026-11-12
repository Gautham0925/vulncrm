import base64, datetime as dt, hashlib, html, json, os, secrets, sys, time
from urllib.parse import urlencode

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", "app"))

import jwt
from cryptography.hazmat.primitives import serialization
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from lxml import etree

from idp_lib import IDP_ENTITY_ID, NS, b64, build_response, inflate_request, load_or_create

BASE = os.environ.get("IDP_BASE_URL", "http://localhost:9000").rstrip("/")
CERT_DIR = os.environ.get("IDP_CERT_DIR", "./idp-certs")
LAB_TOOLS = os.environ.get("IDP_LAB_TOOLS", "1") == "1"
OIDC_CLIENTS = {os.environ.get("OIDC_CLIENT_ID", "vc_northwind_oidc"): os.environ.get("OIDC_CLIENT_SECRET", "oidc-demo-secret-northwind")}
PASSWORD = os.environ.get("IDP_USER_PASSWORD", "Idp#Pass2026")

DIRECTORY = {
    "alice.meyer@northwind.test": {"name": "Alice Meyer", "role": "sales_rep", "verified": True},
    "ben.ortiz@northwind.test": {"name": "Ben Ortiz", "role": "sales_manager", "verified": True},
    "admin@northwind.test": {"name": "Nora Admin", "role": "org_admin", "verified": True},
    "rep1@northwind.test": {"name": "Northwind Rep", "role": "sales_rep", "verified": True},
    "temp.contractor@northwind.test": {"name": "Temp Contractor", "role": "sales_rep", "verified": False},
}

KEY_PEM, CERT_PEM = load_or_create(CERT_DIR)
PRIV = serialization.load_pem_private_key(KEY_PEM, None)
PUB = PRIV.public_key().public_numbers()
KID = hashlib.sha256(CERT_PEM).hexdigest()[:16]


def b64u(n: int) -> str:
    return base64.urlsafe_b64encode(n.to_bytes((n.bit_length() + 7) // 8, "big")).rstrip(b"=").decode()


JWK = {"kty": "RSA", "use": "sig", "alg": "RS256", "kid": KID, "n": b64u(PUB.n), "e": b64u(PUB.e)}
CODES: dict = {}
TOKENS: dict = {}
SAML_PENDING: dict = {}

app = FastAPI(title="VULNCRM Synthetic IdP", docs_url=None, redoc_url=None, openapi_url=None)

PAGE = """<!doctype html><meta charset=utf-8><title>Synthetic Identity Provider</title>
<style>body{{font:15px system-ui;background:#f4f6fa;display:flex;justify-content:center;padding-top:8vh;color:#14213d}}
.c{{background:#fff;border:1px solid #d9dfeb;border-radius:12px;padding:32px;width:380px}}h1{{font-size:18px;margin:0 0 4px}}p{{color:#5b6785;margin:0 0 20px;font-size:13px}}
label{{display:block;font-size:12px;font-weight:600;margin:12px 0 4px}}input,select{{width:100%;padding:9px;border:1px solid #c5cde0;border-radius:6px;box-sizing:border-box}}
button{{margin-top:20px;width:100%;padding:10px;border:0;border-radius:6px;background:#1d4ed8;color:#fff;font-weight:600;cursor:pointer}}.e{{color:#b42318;font-size:13px;margin-top:10px}}</style>
<div class=c><h1>Northwind Identity</h1><p>Synthetic identity provider for the VULNCRM training environment.</p>
<form method=post action="{action}">{hidden}<label>Account</label><select name=email>{options}</select><label>Password</label><input type=password name=password autocomplete=off>
<button>Sign in</button></form>{error}</div>"""


def login_page(action: str, hidden: dict, error: str = "", status: int = 200):
    opts = "".join(f"<option>{html.escape(e)}</option>" for e in DIRECTORY)
    hid = "".join(f'<input type=hidden name="{html.escape(k)}" value="{html.escape(v)}">' for k, v in hidden.items())
    err = f'<div class=e>{html.escape(error)}</div>' if error else ""
    return HTMLResponse(PAGE.format(action=action, hidden=hid, options=opts, error=err), status_code=status)


def check(email: str, password: str) -> dict | None:
    u = DIRECTORY.get(email)
    return u if u and secrets.compare_digest(password, PASSWORD) else None


@app.get("/health")
def health():
    return {"status": "ok", "service": "synthetic-idp"}


@app.get("/saml/metadata")
def saml_metadata():
    cert = "".join(CERT_PEM.decode().splitlines()[1:-1])
    xml = (f'<EntityDescriptor xmlns="urn:oasis:names:tc:SAML:2.0:metadata" entityID="{IDP_ENTITY_ID}"><IDPSSODescriptor protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">'
           f'<KeyDescriptor use="signing"><KeyInfo xmlns="http://www.w3.org/2000/09/xmldsig#"><X509Data><X509Certificate>{cert}</X509Certificate></X509Data></KeyInfo></KeyDescriptor>'
           f'<SingleSignOnService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect" Location="{BASE}/saml/sso"/>'
           f'<SingleLogoutService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect" Location="{BASE}/saml/slo"/></IDPSSODescriptor></EntityDescriptor>')
    return HTMLResponse(xml, media_type="application/xml")


def parse_authn(saml_request: str) -> dict:
    try:
        root = etree.fromstring(inflate_request(saml_request).encode(), etree.XMLParser(resolve_entities=False, no_network=True))
    except Exception:
        raise HTTPException(400, "Malformed SAML request")
    issuer = root.find("saml:Issuer", NS)
    return {"id": root.get("ID"), "acs": root.get("AssertionConsumerServiceURL"), "issuer": issuer.text if issuer is not None else None}


@app.get("/saml/sso")
def saml_sso(SAMLRequest: str = "", RelayState: str = ""):
    if not SAMLRequest:
        raise HTTPException(400, "Missing SAMLRequest")
    info = parse_authn(SAMLRequest)
    if not info["acs"] or not info["id"]:
        raise HTTPException(400, "Incomplete authentication request")
    return login_page("/saml/sso", {"SAMLRequest": SAMLRequest, "RelayState": RelayState})


@app.post("/saml/sso")
def saml_sso_post(SAMLRequest: str = Form(...), RelayState: str = Form(""), email: str = Form(...), password: str = Form(...)):
    info = parse_authn(SAMLRequest)
    user = check(email, password)
    if not user:
        return login_page("/saml/sso", {"SAMLRequest": SAMLRequest, "RelayState": RelayState}, "Incorrect account or password", 401)
    xml = build_response(KEY_PEM, CERT_PEM, destination=info["acs"], audience=info["issuer"] or info["acs"], in_response_to=info["id"], name_id=email,
                         attributes={"email": email, "name": user["name"], "role": user["role"]})
    form = (f'<!doctype html><body onload="document.forms[0].submit()"><form method=post action="{html.escape(info["acs"])}"><input type=hidden name=SAMLResponse value="{b64(xml)}">'
            f'<input type=hidden name=RelayState value="{html.escape(RelayState)}"><noscript><button>Continue</button></noscript></form>')
    return HTMLResponse(form)


@app.api_route("/saml/slo", methods=["GET", "POST"])
def saml_slo():
    return HTMLResponse("<!doctype html><title>Signed out</title><body style='font:16px system-ui;margin:48px'><h2>You have been signed out of the identity provider.</h2>")


@app.get("/oidc/.well-known/openid-configuration")
def oidc_discovery():
    return {"issuer": f"{BASE}/oidc", "authorization_endpoint": f"{BASE}/oidc/authorize", "token_endpoint": f"{BASE}/oidc/token", "jwks_uri": f"{BASE}/oidc/jwks.json",
            "userinfo_endpoint": f"{BASE}/oidc/userinfo", "response_types_supported": ["code"], "subject_types_supported": ["public"], "id_token_signing_alg_values_supported": ["RS256"],
            "scopes_supported": ["openid", "email", "profile"]}


@app.get("/oidc/jwks.json")
def oidc_jwks():
    return {"keys": [JWK]}


@app.get("/oidc/authorize")
def oidc_authorize(client_id: str, redirect_uri: str, state: str = "", nonce: str = "", response_type: str = "code", scope: str = "openid"):
    if client_id not in OIDC_CLIENTS or response_type != "code":
        raise HTTPException(400, "Unknown client or unsupported response type")
    return login_page("/oidc/authorize", {"client_id": client_id, "redirect_uri": redirect_uri, "state": state, "nonce": nonce, "scope": scope})


@app.post("/oidc/authorize")
def oidc_authorize_post(client_id: str = Form(...), redirect_uri: str = Form(...), state: str = Form(""), nonce: str = Form(""), scope: str = Form("openid"), email: str = Form(...), password: str = Form(...)):
    hidden = {"client_id": client_id, "redirect_uri": redirect_uri, "state": state, "nonce": nonce, "scope": scope}
    if client_id not in OIDC_CLIENTS:
        raise HTTPException(400, "Unknown client")
    if not check(email, password):
        return login_page("/oidc/authorize", hidden, "Incorrect account or password", 401)
    code = secrets.token_urlsafe(24)
    CODES[code] = {"email": email, "client_id": client_id, "redirect_uri": redirect_uri, "nonce": nonce, "exp": time.time() + 120}
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(f"{redirect_uri}{sep}{urlencode({'code': code, 'state': state})}", status_code=302)


def id_token(email: str, client_id: str, nonce: str, **extra) -> str:
    u = DIRECTORY[email]
    now = int(time.time())
    claims = {"iss": f"{BASE}/oidc", "aud": client_id, "sub": "idp|" + hashlib.sha256(email.encode()).hexdigest()[:12], "iat": now, "exp": now + 300, "email": email,
              "email_verified": u["verified"], "name": u["name"]}
    if nonce:
        claims["nonce"] = nonce
    claims.update(extra)
    return jwt.encode(claims, KEY_PEM, algorithm="RS256", headers={"kid": KID})


@app.post("/oidc/token")
def oidc_token(grant_type: str = Form(...), code: str = Form(""), redirect_uri: str = Form(""), client_id: str = Form(""), client_secret: str = Form("")):
    c = CODES.pop(code, None)
    if grant_type != "authorization_code" or not c or c["exp"] < time.time():
        return JSONResponse({"error": "invalid_grant"}, status_code=400)
    if OIDC_CLIENTS.get(client_id) != client_secret or c["client_id"] != client_id or c["redirect_uri"] != redirect_uri:
        return JSONResponse({"error": "invalid_client"}, status_code=401)
    at = secrets.token_urlsafe(24)
    TOKENS[at] = c["email"]
    return {"access_token": at, "token_type": "Bearer", "expires_in": 300, "id_token": id_token(c["email"], client_id, c["nonce"])}


@app.get("/oidc/userinfo")
def oidc_userinfo(request: Request):
    email = TOKENS.get(request.headers.get("authorization", "")[7:])
    if not email:
        raise HTTPException(401, "Invalid token")
    u = DIRECTORY[email]
    return {"sub": "idp|" + hashlib.sha256(email.encode()).hexdigest()[:12], "email": email, "email_verified": u["verified"], "name": u["name"]}


if LAB_TOOLS:
    @app.post("/lab/saml/issue")
    async def lab_saml_issue(request: Request):
        body = await request.json()
        xml = build_response(KEY_PEM, CERT_PEM, destination=body["destination"], audience=body["audience"], recipient=body.get("recipient"), in_response_to=body.get("in_response_to"),
                             name_id=body["name_id"], attributes=body.get("attributes"), issuer=body.get("issuer", IDP_ENTITY_ID), sign=body.get("sign", "assertion"),
                             authn_context=body.get("authn_context", "urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport"))
        return {"saml_response": b64(xml)}

    @app.post("/lab/oidc/issue")
    async def lab_oidc_issue(request: Request):
        b = await request.json()
        extra = {k: v for k, v in b.items() if k not in ("email", "client_id", "nonce")}
        email = b.get("email", "rep1@northwind.test")
        if email not in DIRECTORY:
            DIRECTORY[email] = {"name": b.get("name", email), "role": "sales_rep", "verified": bool(b.get("email_verified", False))}
        return {"id_token": id_token(email, b.get("client_id", "vc_northwind_oidc"), b.get("nonce", ""), **extra)}
