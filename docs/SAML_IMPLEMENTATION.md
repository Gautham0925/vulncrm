# SAML 2.0 implementation

VULNCRM is a SAML **service provider**. Configure an identity provider in **Single sign-on** (`/sso`) or through `PUT /api/sso/saml`.

## Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /saml/{org}/metadata` | SP metadata |
| `GET /saml/{org}/login` | Builds an AuthnRequest (HTTP-Redirect) and records the request ID |
| `POST /saml/{org}/acs` | Assertion consumer service (add `?format=json` for JSON) |
| `GET /saml/{org}/logout`, `POST /saml/{org}/slo` | Single logout |

## Validation in the ACS

The secure configuration performs all of the following, each with its own toggle in the vulnerable configuration:

| Check | Toggle |
|---|---|
| XML signature present and valid against the **configured** certificate | `saml_signature`, `saml_cert` |
| Only the signed element is read (no signature wrapping; exactly one assertion) | `saml_wrapping` |
| `Issuer` equals the configured IdP entity ID | `saml_issuer` |
| `Audience` equals the SP entity ID | `saml_audience` |
| `Recipient` and `Destination` equal the ACS URL | `saml_recipient` |
| `NotBefore` / `NotOnOrAfter` with small clock skew | — |
| Assertion ID single use (cached and persisted) | `saml_replay` |
| `InResponseTo` matches an outstanding request | `saml_correlation` |
| Acceptable `AuthnContext` | `saml_correlation` |
| Logout requests signed by the IdP | `saml_slo` |

XML is parsed with entity resolution and network access disabled.

## Provisioning

With JIT provisioning on, an unknown NameID creates a user and a membership with the organization's default role. Administrator roles can never be a default. An asserted `role` attribute is honored only in the vulnerable configuration.

## Synthetic IdP

`idp/main.py` signs assertions with `signxml` using a key pair stored in `IDP_CERT_DIR`. Endpoints: `/saml/metadata`, `/saml/sso`, `/saml/slo`. When `IDP_LAB_TOOLS=1`, `POST /lab/saml/issue` produces signed responses with chosen issuer, audience, destination, signing scope and attributes for validation testing.

## Tests

`backend/tests/test_sso.py` covers valid login, wrong audience, wrong issuer, replay, and unsigned messages in both configurations; Playwright test 11 drives a full browser login.
