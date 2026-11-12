from app import deps
from app.config import get_settings


def test_login_is_throttled_at_default_limits_in_secure(client, secure):
    s = get_settings()
    old = s.rate_limit_multiplier
    s.rate_limit_multiplier = 1
    deps._buckets.clear()
    try:
        codes = [client.post("/api/auth/login", json={"email": f"nobody{i}@example.test", "password": "x"}).status_code for i in range(14)]
        assert 429 in codes
        assert codes.index(429) <= 11
    finally:
        s.rate_limit_multiplier = old
        deps._buckets.clear()


def test_forwarded_header_does_not_bypass_throttle_in_secure(client, secure):
    s = get_settings()
    old = s.rate_limit_multiplier
    s.rate_limit_multiplier = 1
    deps._buckets.clear()
    try:
        codes = [client.post("/api/auth/login", json={"email": f"x{i}@example.test", "password": "x"}, headers={"X-Forwarded-For": f"10.0.0.{i}"}).status_code for i in range(14)]
        assert 429 in codes
    finally:
        s.rate_limit_multiplier = old
        deps._buckets.clear()


def test_forwarded_header_bypasses_throttle_in_vulnerable(client, vulnerable):
    deps._buckets.clear()
    codes = [client.post("/api/auth/login", json={"email": f"y{i}@example.test", "password": "x"}, headers={"X-Forwarded-For": f"10.1.0.{i}"}).status_code for i in range(14)]
    assert 429 not in codes
    deps._buckets.clear()
