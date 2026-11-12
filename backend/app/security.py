import base64
import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import get_settings

settings = get_settings()
API_AUDIENCE = "vulncrm-api"


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode()[:72], bcrypt.gensalt(settings.bcrypt_rounds)).decode()


def check_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode()[:72], hashed.encode())
    except ValueError:
        return False


def sha256(v: str) -> str:
    return hashlib.sha256(v.encode()).hexdigest()


def rand(n: int = 32) -> str:
    return secrets.token_urlsafe(n)


class Keys:
    def __init__(self):
        self.private = None
        self.public_pem = b""
        self.kid = ""
        self.retired: list[tuple[str, bytes]] = []

    def load(self):
        d = settings.keys_dir
        os.makedirs(d, exist_ok=True)
        priv_path = os.path.join(d, "private.pem")
        env_pem = os.environ.get("JWT_PRIVATE_KEY_PEM")
        if env_pem:
            pem = env_pem.encode()
        elif os.path.exists(priv_path):
            pem = open(priv_path, "rb").read()
        else:
            k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            pem = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
            with open(priv_path, "wb") as f:
                f.write(pem)
            os.chmod(priv_path, 0o600)
        self.private = serialization.load_pem_private_key(pem, None)
        self.public_pem = self.private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        self.kid = hashlib.sha256(self.public_pem).hexdigest()[:16]
        self.private_pem = pem

    def jwks(self):
        pub = self.private.public_key().public_numbers()

        def b64(i: int):
            return base64.urlsafe_b64encode(i.to_bytes((i.bit_length() + 7) // 8, "big")).rstrip(b"=").decode()

        keys = [{"kty": "RSA", "use": "sig", "alg": "RS256", "kid": self.kid, "n": b64(pub.n), "e": b64(pub.e)}]
        return {"keys": keys}


keys = Keys()


def ensure_keys():
    if keys.private is None:
        keys.load()


def issue_jwt(claims: dict, ttl: int, audience: str = API_AUDIENCE, issuer: str | None = None) -> str:
    ensure_keys()
    now = datetime.now(timezone.utc)
    payload = {"iss": issuer or settings.jwt_issuer, "aud": audience, "iat": now, "exp": now + timedelta(seconds=ttl), "jti": uuid.uuid4().hex, **claims}
    return jwt.encode(payload, keys.private, algorithm="RS256", headers={"kid": keys.kid})


def verify_jwt(token: str, audience: str = API_AUDIENCE) -> dict:
    ensure_keys()
    return jwt.decode(token, keys.public_pem, algorithms=["RS256"], audience=audience, issuer=settings.jwt_issuer, options={"require": ["exp", "iss", "aud", "sub"]})
