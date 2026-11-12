import os, tempfile, pytest
_d = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_d}/t.db"
os.environ["UPLOAD_DIR"] = f"{_d}/up"
os.environ["KEYS_DIR"] = f"{_d}/keys"
os.environ["VULNCRM_DISABLE_WEBHOOKS"] = "1"
os.environ["RATE_LIMIT_MULTIPLIER"] = "50"
os.environ["IDP_CERT_DIR"] = f"{_d}/idp"
from fastapi.testclient import TestClient
from app import mode
import app.main as m

PW = "Crm#Pass2026"

@pytest.fixture(scope="session")
def client():
    with TestClient(m.app) as c:
        yield c

@pytest.fixture(params=["vulnerable", "secure"])
def cfg(request):
    mode.set_override(request.param)
    yield request.param
    mode.set_override(None)

@pytest.fixture
def vulnerable():
    mode.set_override("vulnerable"); yield; mode.set_override(None)

@pytest.fixture
def secure():
    mode.set_override("secure"); yield; mode.set_override(None)

def login(client, email, password=PW):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}
