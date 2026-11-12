import os, re
from urllib.parse import urlparse, parse_qs
from app import mode
from app.idp_lib import IDP_ENTITY_ID, b64, build_response, inflate_request, load_or_create
from lxml import etree

SP = "https://vulncrm.local/saml/northwind"
ACS = "/saml/northwind/acs"


def keys():
    return load_or_create(os.environ["IDP_CERT_DIR"])


def begin(client):
    r = client.get("/saml/northwind/login", follow_redirects=False)
    assert r.status_code == 302
    q = parse_qs(urlparse(r.headers["location"]).query)
    root = etree.fromstring(inflate_request(q["SAMLRequest"][0]).encode())
    return root.get("ID"), root.get("AssertionConsumerServiceURL"), root.find("{urn:oasis:names:tc:SAML:2.0:assertion}Issuer").text


def response(client, **over):
    rid, acs, entity = begin(client)
    k, c = keys()
    args = dict(destination=acs, audience=entity, in_response_to=rid, name_id="rep1@northwind.test", attributes={"email": "rep1@northwind.test", "name": "Rep One"})
    args.update(over)
    return b64(build_response(k, c, **args))


def post(client, xml_b64):
    return client.post(ACS + "?format=json", data={"SAMLResponse": xml_b64})


def test_valid_login(client, cfg):
    assert post(client, response(client)).status_code == 200


def test_wrong_audience_rejected_in_secure(client, secure):
    assert post(client, response(client, audience="https://other.example/sp")).status_code == 401


def test_replay_rejected_in_secure(client, secure):
    rid, acs, entity = begin(client)
    k, c = keys()
    x = b64(build_response(k, c, destination=acs, audience=entity, in_response_to=rid, name_id="rep1@northwind.test", attributes={"email": "rep1@northwind.test"}))
    assert post(client, x).status_code == 200
    assert post(client, x).status_code == 401


def test_unsigned_rejected_in_secure(client, secure):
    assert post(client, response(client, sign="none")).status_code == 401


def test_unsigned_accepted_only_in_vulnerable(client, vulnerable):
    assert post(client, response(client, sign="none")).status_code == 200


def test_wrong_issuer_rejected_in_secure(client, secure):
    assert post(client, response(client, issuer="https://evil.example/idp")).status_code == 401
