from tests.conftest import login

def test_login_and_me(client, cfg):
    h = login(client, "rep1@northwind.test")
    r = client.get("/api/auth/me", headers=h)
    assert r.status_code == 200 and r.json()["user"]["email"] == "rep1@northwind.test"

def test_bad_password(client, cfg):
    r = client.post("/api/auth/login", json={"email": "rep1@northwind.test", "password": "nope"})
    assert r.status_code in (401, 429)

def test_cross_tenant_customer(client):
    from app import mode
    h = login(client, "rep1@northwind.test")
    other = login(client, "rep1@contoso.test")
    cid = client.get("/api/customers", headers=other).json()["items"][0]["id"]
    mode.set_override("secure")
    assert client.get(f"/api/customers/{cid}", headers=h).status_code == 404
    mode.set_override("vulnerable")
    assert client.get(f"/api/customers/{cid}", headers=h).status_code == 200
    mode.set_override(None)

def test_bfla_delete(client):
    from app import mode
    h = login(client, "rep1@northwind.test")
    cid = client.get("/api/customers", headers=h).json()["items"][0]["id"]
    mode.set_override("secure")
    assert client.delete(f"/api/customers/{cid}", headers=h).status_code == 403
    mode.set_override(None)

def test_mass_assignment(client):
    from app import mode
    h = login(client, "rep1@northwind.test")
    mode.set_override("secure")
    r = client.patch("/api/profile", headers=h, json={"phone": "123", "role_id": 1, "salary": 999999})
    assert r.status_code in (200, 422)
    me = client.get("/api/auth/me", headers=h).json()["user"]
    assert me.get("salary") != 999999
    mode.set_override(None)

def test_legacy_api_gone_in_secure(client, secure):
    h = login(client, "rep1@northwind.test")
    assert client.get("/api/v0/customers", headers=h).status_code in (404, 410)

def test_system_info_hidden_in_secure(client, secure):
    h = login(client, "rep1@northwind.test")
    assert client.get("/api/system/info", headers=h).status_code in (403, 404)

def test_graphql_introspection(client):
    from app import mode
    q = {"query": "{ __schema { types { name } } }"}
    mode.set_override("secure")
    r = client.post("/graphql", json=q, headers=login(client, "rep1@northwind.test"))
    assert "errors" in r.json() or r.status_code >= 400
    mode.set_override("vulnerable")
    r = client.post("/graphql", json=q, headers=login(client, "rep1@northwind.test"))
    assert "__schema" in r.text
    mode.set_override(None)

def test_oidc_discovery_and_jwks(client):
    assert client.get("/.well-known/openid-configuration").status_code == 200
    assert client.get("/oidc/jwks.json").json()["keys"]

def test_testcases_library(client):
    h = login(client, "auditor@northwind.test")
    r = client.get("/api/testlib/cases", headers=h)
    assert r.status_code == 200
    assert "flag" not in r.text.lower().replace("flags", "")
