import base64, hashlib, secrets
from urllib.parse import parse_qs, urlparse
from app import mode
from tests.conftest import login

SYNC = ("vc_data_sync", "vcs_northwind_data_sync_secret_demo")
MOBILE = "vc_mobile_app"
MOBILE_URI = "com.northwind.crm://oauth/callback"


def pkce():
    v = secrets.token_urlsafe(48)
    return v, base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()


def cookie_login(client, email="rep1@northwind.test"):
    client.cookies.clear()
    client.get("/api/auth/session-init")
    r = client.post("/api/auth/login", json={"email": email, "password": "Crm#Pass2026"})
    assert r.status_code == 200
    return client.cookies.get("vc_csrf")


def code_flow(client, verifier_challenge, scope="openid customers:read"):
    csrf = cookie_login(client)
    _, challenge = verifier_challenge
    params = dict(response_type="code", client_id=MOBILE, redirect_uri=MOBILE_URI, scope=scope, state="s1", code_challenge=challenge, code_challenge_method="S256")
    r = client.post("/oauth/authorize?" + "&".join(f"{k}={v}" for k, v in params.items()), data={**params, "decision": "approve", "csrf": csrf}, follow_redirects=False)
    assert r.status_code == 302, r.text
    return parse_qs(urlparse(r.headers["location"]).query)["code"][0]


def test_client_credentials_token_works_against_api(client, cfg):
    r = client.post("/oauth/token", data={"grant_type": "client_credentials", "client_id": SYNC[0], "client_secret": SYNC[1], "scope": "customers:read"})
    assert r.status_code == 200, r.text
    tok = r.json()["access_token"]
    assert client.get("/api/customers", headers={"Authorization": f"Bearer {tok}"}).status_code == 200
    assert client.post("/api/customers", headers={"Authorization": f"Bearer {tok}"}, json={"name": "x"}).status_code in (401, 403)


def test_client_credentials_requires_valid_secret_in_secure(client, secure):
    r = client.post("/oauth/token", data={"grant_type": "client_credentials", "client_id": SYNC[0], "client_secret": "wrong"})
    assert r.status_code in (400, 401)


def test_code_flow_with_pkce_and_single_use(client, secure):
    vc = pkce()
    code = code_flow(client, vc)
    body = {"grant_type": "authorization_code", "code": code, "client_id": MOBILE, "redirect_uri": MOBILE_URI, "code_verifier": vc[0]}
    ok = client.post("/oauth/token", data=body)
    assert ok.status_code == 200 and "refresh_token" in ok.json()
    assert client.post("/oauth/token", data=body).status_code == 400


def test_wrong_pkce_verifier_rejected_in_secure(client, secure):
    vc = pkce()
    code = code_flow(client, vc)
    r = client.post("/oauth/token", data={"grant_type": "authorization_code", "code": code, "client_id": MOBILE, "redirect_uri": MOBILE_URI, "code_verifier": "x" * 50})
    assert r.status_code == 400


def test_unregistered_redirect_rejected_in_secure(client, secure):
    csrf = cookie_login(client)
    _, ch = pkce()
    qs = f"response_type=code&client_id={MOBILE}&redirect_uri=https://evil.example/cb&scope=openid&code_challenge={ch}&code_challenge_method=S256"
    r = client.get("/oauth/authorize?" + qs, follow_redirects=False)
    assert r.status_code == 400


def test_refresh_token_rotates_in_secure(client, secure):
    vc = pkce()
    code = code_flow(client, vc)
    t = client.post("/oauth/token", data={"grant_type": "authorization_code", "code": code, "client_id": MOBILE, "redirect_uri": MOBILE_URI, "code_verifier": vc[0]}).json()
    n = client.post("/oauth/token", data={"grant_type": "refresh_token", "refresh_token": t["refresh_token"], "client_id": MOBILE})
    assert n.status_code == 200 and n.json()["refresh_token"] != t["refresh_token"]
    assert client.post("/oauth/token", data={"grant_type": "refresh_token", "refresh_token": t["refresh_token"], "client_id": MOBILE}).status_code == 400


def gql(client, h, query):
    return client.post("/graphql", json={"query": query}, headers=h)


def test_graphql_scoped_customers_and_authz(client, secure):
    h = login(client, "rep1@northwind.test")
    r = gql(client, h, "{ customers { id name } }")
    assert r.status_code == 200 and r.json()["data"]["customers"]
    r = gql(client, h, "{ users { id email salary } }")
    body = r.json()
    assert "errors" in body or all(u.get("salary") is None for u in (body.get("data") or {}).get("users") or [])


def test_graphql_depth_limit_in_secure(client, secure):
    h = login(client, "rep1@northwind.test")
    q = "{ customers { owner { customers { owner { customers { owner { customers { id } } } } } } } }"
    assert "errors" in gql(client, h, q).json()


def test_graphql_batching_blocked_in_secure(client, secure):
    h = login(client, "rep1@northwind.test")
    r = client.post("/graphql", json=[{"query": "{ me { id } }"}] * 3, headers=h)
    assert r.status_code >= 400 or "errors" in (r.json() if isinstance(r.json(), dict) else {})


def test_graphql_requires_authentication(client, secure):
    r = client.post("/graphql", json={"query": "{ customers { id } }"}, headers={})
    client.cookies.clear()
    r = client.post("/graphql", json={"query": "{ customers { id } }"})
    assert r.status_code in (200, 401, 403) and (r.status_code != 200 or "errors" in r.json())


def test_document_upload_validation_and_download_scope(client, secure):
    h = login(client, "rep1@northwind.test")
    bad = client.post("/api/documents", headers=h, files={"file": ("run.exe", b"MZ....", "application/octet-stream")})
    assert bad.status_code in (400, 415, 422)
    ok = client.post("/api/documents", headers=h, files={"file": ("n.txt", b"hello", "text/plain")}, data={"name": "n"})
    assert ok.status_code in (200, 201), ok.text
    did = ok.json()["id"]
    assert client.get(f"/api/documents/{did}/download", headers=h).status_code == 200
    other = login(client, "rep2@northwind.test")
    assert client.get(f"/api/documents/{did}/download", headers=other).status_code in (403, 404)


def test_traversal_never_leaves_upload_root(client, vulnerable):
    h = login(client, "rep1@northwind.test")
    r = client.get("/api/files/../../etc/passwd", headers=h)
    assert r.status_code in (400, 403, 404)
    assert "root:" not in r.text
