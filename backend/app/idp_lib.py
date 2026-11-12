import base64
import datetime as dt
import os
import uuid
import zlib

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from lxml import etree
from signxml import XMLSigner, methods

NS = {"samlp": "urn:oasis:names:tc:SAML:2.0:protocol", "saml": "urn:oasis:names:tc:SAML:2.0:assertion", "ds": "http://www.w3.org/2000/09/xmldsig#"}
PASSWORD_CTX = "urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport"
IDP_ENTITY_ID = "https://idp.vulncrm.local/saml"


def make_keypair(common_name: str = "VULNCRM Synthetic IdP"):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name), x509.NameAttribute(NameOID.ORGANIZATION_NAME, "VULNCRM Training")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=3650)).sign(key, hashes.SHA256()))
    key_pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    return key_pem, cert.public_bytes(serialization.Encoding.PEM)


def load_or_create(directory: str, prefix: str = "idp"):
    os.makedirs(directory, exist_ok=True)
    kp, cp = os.path.join(directory, f"{prefix}-key.pem"), os.path.join(directory, f"{prefix}-cert.pem")
    if not (os.path.exists(kp) and os.path.exists(cp)):
        k, c = make_keypair()
        open(kp, "wb").write(k)
        open(cp, "wb").write(c)
    return open(kp, "rb").read(), open(cp, "rb").read()


def iso(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id() -> str:
    return "_" + uuid.uuid4().hex


def build_response(key_pem: bytes, cert_pem: bytes, *, destination: str, audience: str, recipient: str | None = None, in_response_to: str | None = None, name_id: str,
                   attributes: dict | None = None, issuer: str = IDP_ENTITY_ID, session_index: str | None = None, sign: str = "assertion", authn_context: str = PASSWORD_CTX,
                   not_before: dt.datetime | None = None, not_on_or_after: dt.datetime | None = None, assertion_id: str | None = None, response_id: str | None = None,
                   status: str = "urn:oasis:names:tc:SAML:2.0:status:Success") -> str:
    now = dt.datetime.now(dt.timezone.utc)
    nb = not_before or now - dt.timedelta(minutes=1)
    na = not_on_or_after or now + dt.timedelta(minutes=5)
    rid, aid = response_id or new_id(), assertion_id or new_id()
    irt = f' InResponseTo="{in_response_to}"' if in_response_to else ""
    attrs = "".join(f'<saml:Attribute Name="{k}"><saml:AttributeValue>{v}</saml:AttributeValue></saml:Attribute>' for k, v in (attributes or {}).items())
    attr_stmt = f"<saml:AttributeStatement>{attrs}</saml:AttributeStatement>" if attrs else ""
    xml = (f'<samlp:Response xmlns:samlp="{NS["samlp"]}" xmlns:saml="{NS["saml"]}" ID="{rid}" Version="2.0" IssueInstant="{iso(now)}" Destination="{destination}"{irt}>'
           f'<saml:Issuer>{issuer}</saml:Issuer><samlp:Status><samlp:StatusCode Value="{status}"/></samlp:Status>'
           f'<saml:Assertion ID="{aid}" Version="2.0" IssueInstant="{iso(now)}"><saml:Issuer>{issuer}</saml:Issuer>'
           f'<saml:Subject><saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">{name_id}</saml:NameID>'
           f'<saml:SubjectConfirmation Method="urn:oasis:names:tc:SAML:2.0:cm:bearer"><saml:SubjectConfirmationData NotOnOrAfter="{iso(na)}" Recipient="{recipient or destination}"{irt}/></saml:SubjectConfirmation></saml:Subject>'
           f'<saml:Conditions NotBefore="{iso(nb)}" NotOnOrAfter="{iso(na)}"><saml:AudienceRestriction><saml:Audience>{audience}</saml:Audience></saml:AudienceRestriction></saml:Conditions>'
           f'<saml:AuthnStatement AuthnInstant="{iso(now)}" SessionIndex="{session_index or new_id()}"><saml:AuthnContext><saml:AuthnContextClassRef>{authn_context}</saml:AuthnContextClassRef></saml:AuthnContext></saml:AuthnStatement>'
           f'{attr_stmt}</saml:Assertion></samlp:Response>')
    root = etree.fromstring(xml.encode())
    if sign in ("assertion", "both"):
        a = root.find("saml:Assertion", NS)
        signed = XMLSigner(method=methods.enveloped, signature_algorithm="rsa-sha256", digest_algorithm="sha256", c14n_algorithm="http://www.w3.org/2001/10/xml-exc-c14n#").sign(a, key=key_pem, cert=cert_pem, reference_uri=aid)
        root.replace(a, signed)
        sig = signed.find("ds:Signature", NS)
        issuer_el = signed.find("saml:Issuer", NS)
        if sig is not None and issuer_el is not None and sig.getprevious() is not issuer_el:
            signed.remove(sig)
            issuer_el.addnext(sig)
    if sign in ("response", "both"):
        signed_root = XMLSigner(method=methods.enveloped, signature_algorithm="rsa-sha256", digest_algorithm="sha256", c14n_algorithm="http://www.w3.org/2001/10/xml-exc-c14n#").sign(root, key=key_pem, cert=cert_pem, reference_uri=rid)
        root = signed_root
    return etree.tostring(root).decode()


def b64(xml: str) -> str:
    return base64.b64encode(xml.encode()).decode()


def inflate_request(saml_request: str) -> str:
    raw = base64.b64decode(saml_request)
    try:
        return zlib.decompress(raw, -15).decode()
    except zlib.error:
        return raw.decode()


def deflate_request(xml: str) -> str:
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return base64.b64encode(c.compress(xml.encode()) + c.flush()).decode()
