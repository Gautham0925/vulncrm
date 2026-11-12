import csv
import io
import secrets
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import Principal, audit, client_ip, paginate, require, to_dict
from app.mode import vuln
from app.models import ApiClient, ApiKey, ApiRequestLog, AuditLog, IntegrationConfig, Webhook, now
from app.rbac import OAUTH_SCOPES
from app.security import sha256
from app.services import safe_fetch

router = APIRouter(prefix="/api", tags=["integrations"])
settings = get_settings()
KEY_SCOPES = [s for s in OAUTH_SCOPES if ":" in s]


def client_of(db, cid, p, flag="bola"):
    c = db.get(ApiClient, cid) if vuln(flag) else db.query(ApiClient).filter(ApiClient.id == cid, ApiClient.org_id == p.org_id).first()
    if not c:
        raise HTTPException(404, "Not found")
    return c


def ser_key(k: ApiKey, reveal=False):
    d = to_dict(k, exclude=("key_hash", "plaintext"))
    if vuln("api_key_weak") and k.plaintext:
        d["key"] = k.plaintext
    return d


@router.get("/integrations/clients")
def list_clients(p: Principal = Depends(require("integrations.manage")), db: Session = Depends(get_db)):
    rows = db.query(ApiClient).filter(ApiClient.org_id == p.org_id).order_by(ApiClient.name).all()
    return {"items": [{**to_dict(c), "key_count": db.query(ApiKey).filter(ApiKey.client_id == c.id, ApiKey.revoked.is_(False)).count()} for c in rows], "available_scopes": KEY_SCOPES}


@router.post("/integrations/clients", status_code=201)
def create_client(body: dict, request: Request, p: Principal = Depends(require("integrations.manage")), db: Session = Depends(get_db)):
    if not body.get("name"):
        raise HTTPException(422, "Name is required")
    scopes = [s for s in body.get("scopes", []) if s in KEY_SCOPES]
    c = ApiClient(org_id=p.org_id, name=body["name"], description=body.get("description"), scopes=scopes, owner_id=p.membership.id)
    db.add(c)
    db.flush()
    audit(db, p, "api_client.create", "api_client", c.id, {"scopes": scopes}, ip=client_ip(request))
    db.commit()
    return to_dict(c)


@router.patch("/integrations/clients/{cid}")
def update_client(cid: int, body: dict, p: Principal = Depends(require("integrations.manage")), db: Session = Depends(get_db)):
    c = client_of(db, cid, p)
    for k in ("name", "description", "active"):
        if k in body:
            setattr(c, k, body[k])
    if "scopes" in body:
        c.scopes = [s for s in body["scopes"] if s in KEY_SCOPES]
    audit(db, p, "api_client.update", "api_client", c.id)
    db.commit()
    return to_dict(c)


@router.delete("/integrations/clients/{cid}")
def delete_client(cid: int, p: Principal = Depends(require("integrations.manage")), db: Session = Depends(get_db)):
    c = client_of(db, cid, p)
    db.query(ApiKey).filter(ApiKey.client_id == c.id).update({"revoked": True})
    c.active = False
    audit(db, p, "api_client.disable", "api_client", c.id)
    db.commit()
    return {"ok": True}


@router.get("/integrations/clients/{cid}/keys")
def list_keys(cid: int, p: Principal = Depends(require("integrations.manage")), db: Session = Depends(get_db)):
    c = client_of(db, cid, p)
    return {"items": [ser_key(k) for k in db.query(ApiKey).filter(ApiKey.client_id == c.id).order_by(ApiKey.created_at.desc()).all()]}


@router.post("/integrations/clients/{cid}/keys", status_code=201)
def create_key(cid: int, body: dict, request: Request, p: Principal = Depends(require("integrations.manage")), db: Session = Depends(get_db)):
    c = client_of(db, cid, p)
    prefix = "vck_" + secrets.token_hex(4)
    secret = f"{secrets.randbelow(10**8):08d}" if vuln("api_key_weak") else secrets.token_urlsafe(32)
    raw = prefix + secret
    days = body.get("expires_days", 90)
    scopes = [s for s in body.get("scopes", c.scopes) if s in KEY_SCOPES and (s in (c.scopes or []) or vuln("api_key_weak"))]
    k = ApiKey(org_id=c.org_id, client_id=c.id, prefix=prefix, key_hash=sha256(raw), plaintext=raw if vuln("api_key_weak") else None, scopes=scopes,
               expires_at=None if vuln("api_key_weak") or not days else now() + timedelta(days=int(days)))
    db.add(k)
    db.flush()
    audit(db, p, "api_key.create", "api_key", k.id, {"client": c.id, "scopes": scopes}, ip=client_ip(request))
    db.commit()
    return {**ser_key(k), "key": raw, "notice": "Copy this key now. It will not be shown again." if not vuln("api_key_weak") else None}


@router.delete("/integrations/keys/{kid}")
def revoke_key(kid: int, p: Principal = Depends(require("integrations.manage")), db: Session = Depends(get_db)):
    k = db.get(ApiKey, kid) if vuln("bola") else db.query(ApiKey).filter(ApiKey.id == kid, ApiKey.org_id == p.org_id).first()
    if not k:
        raise HTTPException(404, "Not found")
    k.revoked = True
    audit(db, p, "api_key.revoke", "api_key", k.id)
    db.commit()
    return {"ok": True}


@router.get("/integrations/requests")
def request_history(page: int = 1, size: int = 50, p: Principal = Depends(require("integrations.manage")), db: Session = Depends(get_db)):
    rows, meta = paginate(db.query(ApiRequestLog).filter(ApiRequestLog.org_id == p.org_id).order_by(ApiRequestLog.created_at.desc()), page, size)
    return {"items": [to_dict(r) for r in rows], "meta": meta}


@router.get("/integrations/webhooks")
def list_webhooks(p: Principal = Depends(require("integrations.manage")), db: Session = Depends(get_db)):
    rows = db.query(Webhook).filter(Webhook.org_id == p.org_id).all()
    return {"items": [to_dict(w, exclude=() if vuln("data_exposure") else ("secret",)) for w in rows]}


@router.post("/integrations/webhooks", status_code=201)
def create_webhook(body: dict, request: Request, p: Principal = Depends(require("integrations.manage")), db: Session = Depends(get_db)):
    url = body.get("url", "")
    if not url.startswith(("http://", "https://")):
        raise HTTPException(422, "A valid http(s) URL is required")
    w = Webhook(org_id=p.org_id, url=url, events=body.get("events", ["*"]), secret=secrets.token_hex(12))
    db.add(w)
    db.flush()
    audit(db, p, "webhook.create", "webhook", w.id, {"url": url}, ip=client_ip(request))
    db.commit()
    return to_dict(w)


@router.delete("/integrations/webhooks/{wid}")
def delete_webhook(wid: int, p: Principal = Depends(require("integrations.manage")), db: Session = Depends(get_db)):
    w = db.get(Webhook, wid) if vuln("bola") else db.query(Webhook).filter(Webhook.id == wid, Webhook.org_id == p.org_id).first()
    if not w:
        raise HTTPException(404, "Not found")
    db.delete(w)
    audit(db, p, "webhook.delete", "webhook", wid)
    db.commit()
    return {"ok": True}


@router.post("/integrations/webhooks/{wid}/test")
def test_webhook(wid: int, p: Principal = Depends(require("integrations.manage")), db: Session = Depends(get_db)):
    w = db.get(Webhook, wid) if vuln("bola") else db.query(Webhook).filter(Webhook.id == wid, Webhook.org_id == p.org_id).first()
    if not w:
        raise HTTPException(404, "Not found")
    res = safe_fetch(w.url, "POST", json={"event": "webhook.test", "data": {}}, timeout=3)
    w.last_status = str(res.get("status") or res.get("error"))
    db.commit()
    if vuln("ssrf"):
        return res
    return {"ok": res.get("ok", False), "status": res.get("status"), "error": res.get("error")}


@router.post("/integrations/import-url")
def import_url(body: dict, p: Principal = Depends(require("integrations.manage")), db: Session = Depends(get_db)):
    res = safe_fetch(body.get("url", ""), "GET", timeout=3)
    if not res.get("ok"):
        raise HTTPException(422, res.get("error", "Import failed"))
    return {"status": res["status"], "content_type": res.get("content_type"), "preview": res["body"][:2000] if vuln("ssrf") else f"{len(res['body'])} bytes fetched"}


@router.get("/integrations/configs")
def list_configs(p: Principal = Depends(require("integrations.manage")), db: Session = Depends(get_db)):
    return {"items": [to_dict(c) for c in db.query(IntegrationConfig).filter(IntegrationConfig.org_id == p.org_id).all()]}


@router.post("/integrations/configs", status_code=201)
def create_config(body: dict, p: Principal = Depends(require("integrations.manage")), db: Session = Depends(get_db)):
    if not body.get("name") or not body.get("kind"):
        raise HTTPException(422, "Name and kind are required")
    c = IntegrationConfig(org_id=p.org_id, kind=body["kind"], name=body["name"], config=body.get("config", {}), enabled=bool(body.get("enabled", True)))
    db.add(c)
    db.flush()
    audit(db, p, "integration.create", "integration", c.id, {"kind": c.kind})
    db.commit()
    return to_dict(c)


@router.patch("/integrations/configs/{iid}")
def update_config(iid: int, body: dict, p: Principal = Depends(require("integrations.manage")), db: Session = Depends(get_db)):
    c = db.query(IntegrationConfig).filter(IntegrationConfig.id == iid, IntegrationConfig.org_id == p.org_id).first()
    if not c:
        raise HTTPException(404, "Not found")
    for k in ("name", "config", "enabled"):
        if k in body:
            setattr(c, k, body[k])
    audit(db, p, "integration.update", "integration", c.id)
    db.commit()
    return to_dict(c)


@router.delete("/integrations/configs/{iid}")
def delete_config(iid: int, p: Principal = Depends(require("integrations.manage")), db: Session = Depends(get_db)):
    c = db.query(IntegrationConfig).filter(IntegrationConfig.id == iid, IntegrationConfig.org_id == p.org_id).first()
    if not c:
        raise HTTPException(404, "Not found")
    db.delete(c)
    audit(db, p, "integration.delete", "integration", iid)
    db.commit()
    return {"ok": True}


@router.post("/integrations/connector/{action}")
def connector(action: str, body: dict, p: Principal = Depends(require("integrations.manage"))):
    if action not in ("config", "lookup", "settings"):
        raise HTTPException(404, "Unknown connector action")
    try:
        r = httpx.post(f"{settings.node_service_url}/connector/{action}", json=body, headers={"X-Org-Id": str(p.org_id), "X-Mode": "vulnerable" if vuln("proto_pollution") else "secure"}, timeout=3)
        return Response(r.content, status_code=r.status_code, media_type="application/json")
    except httpx.HTTPError:
        raise HTTPException(503, "Connector service is not available")


@router.get("/audit")
def audit_logs(action: str = "", actor: str = "", resource_type: str = "", date_from: str = "", date_to: str = "", page: int = 1, size: int = 50, p: Principal = Depends(require("audit.read")), db: Session = Depends(get_db)):
    qs = db.query(AuditLog).filter(AuditLog.org_id == p.org_id)
    if action:
        qs = qs.filter(AuditLog.action.like(f"{action}%"))
    if actor:
        qs = qs.filter(AuditLog.actor_label.ilike(f"%{actor}%"))
    if resource_type:
        qs = qs.filter(AuditLog.resource_type == resource_type)
    if date_from:
        qs = qs.filter(AuditLog.created_at >= datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc))
    if date_to:
        qs = qs.filter(AuditLog.created_at <= datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc) + timedelta(days=1))
    rows, meta = paginate(qs.order_by(AuditLog.created_at.desc()), page, size)
    return {"items": [to_dict(r) for r in rows], "meta": meta}


@router.get("/audit/export")
def audit_export(action: str = "", p: Principal = Depends(require("audit.read")), db: Session = Depends(get_db)):
    qs = db.query(AuditLog).filter(AuditLog.org_id == p.org_id)
    if action:
        qs = qs.filter(AuditLog.action.like(f"{action}%"))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["time", "actor", "action", "resource", "resource_id", "ip"])
    for r in qs.order_by(AuditLog.created_at.desc()).limit(5000).all():
        w.writerow([r.created_at.isoformat(), r.actor_label, r.action, r.resource_type, r.resource_id, r.ip])
    return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=audit-log.csv"})
