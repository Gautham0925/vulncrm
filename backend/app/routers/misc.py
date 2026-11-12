import html
import platform
import sys

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import Principal, current_principal, like, require, scoped, to_dict
from app.mode import mode, vuln
from app.models import Customer, Lead, Opportunity, SimulatedEmail, Ticket, User

router = APIRouter(tags=["misc"])
settings = get_settings()


@router.get("/api/meta")
def meta():
    m = mode()
    return {"product": "VULNCRM", "tagline": "Manage Relationships. Secure Every Interaction.", "mode": m, "training_environment": settings.training_allowed,
            "banner": "Training configuration: intentionally vulnerable. Do not expose to untrusted networks." if m == "vulnerable" else None,
            "sso": {"saml": True, "oidc": True}}


@router.get("/api/health")
def health():
    return {"status": "ok"}


@router.get("/api/dev/mailbox")
def mailbox(to: str = "", db: Session = Depends(get_db)):
    if not settings.training_allowed:
        raise HTTPException(404, "Not found")
    qs = db.query(SimulatedEmail)
    if to:
        qs = qs.filter(SimulatedEmail.to_email == to.lower())
    return {"items": [{"id": m.id, "to": m.to_email, "subject": m.subject, "body": m.body, "created_at": m.created_at.isoformat()} for m in qs.order_by(SimulatedEmail.id.desc()).limit(30).all()]}


@router.get("/api/system/info")
def system_info(request: Request):
    if not vuln("misconfig_headers"):
        raise HTTPException(404, "Not found")
    return {"python": sys.version, "platform": platform.platform(), "environment": settings.environment, "database": settings.sqlalchemy_url.split("@")[-1],
            "debug": True, "upload_dir": settings.upload_dir, "node_service": settings.node_service_url, "headers": dict(request.headers)}


@router.get("/__internal/service-config")
def internal_config(request: Request):
    host = request.client.host if request.client else ""
    if not vuln("ssrf") or host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(404, "Not found")
    return {"service": "internal-billing", "note": "Synthetic internal service, reachable only from loopback", "connection": {"host": "billing.internal", "user": "svc_billing", "password": "synthetic-not-a-real-secret"}}


@router.get("/api/search")
def search(q: str = "", p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    if len(q) < 2:
        return {"customers": [], "leads": [], "opportunities": [], "tickets": []}
    out = {"customers": [], "leads": [], "opportunities": [], "tickets": []}
    if p.can("customers.read"):
        out["customers"] = [{"id": c.id, "name": c.name, "sub": c.company} for c in scoped(db, db.query(Customer).filter(Customer.deleted_at.is_(None), Customer.name.ilike(like(q))), Customer, p).limit(5)]
    if p.can("leads.read"):
        out["leads"] = [{"id": l.id, "name": l.name, "sub": l.company} for l in scoped(db, db.query(Lead).filter(Lead.name.ilike(like(q))), Lead, p).limit(5)]
    if p.can("opportunities.read"):
        out["opportunities"] = [{"id": o.id, "name": o.name, "sub": o.stage} for o in scoped(db, db.query(Opportunity).filter(Opportunity.name.ilike(like(q))), Opportunity, p).limit(5)]
    if p.can("tickets.read"):
        out["tickets"] = [{"id": t.id, "name": t.subject, "sub": t.status} for t in db.query(Ticket).filter(Ticket.org_id == p.org_id, Ticket.subject.ilike(like(q))).limit(5)]
    return out


@router.get("/api/v0/customers")
def legacy_customers(request: Request, db: Session = Depends(get_db)):
    if not vuln("legacy_api"):
        raise HTTPException(410, "This API version has been retired. Use /api/customers")
    key = request.headers.get("x-api-key", "")
    if not key.startswith("vck_"):
        raise HTTPException(401, "API key required")
    return {"items": [to_dict(c) for c in db.query(Customer).filter(Customer.deleted_at.is_(None)).limit(200).all()], "version": "v0"}


@router.get("/api/v0/users")
def legacy_users(request: Request, db: Session = Depends(get_db)):
    if not vuln("legacy_api"):
        raise HTTPException(410, "This API version has been retired")
    if not request.headers.get("x-api-key", "").startswith("vck_"):
        raise HTTPException(401, "API key required")
    return {"items": [{"id": u.id, "email": u.email, "name": u.name, "mfa_enabled": u.mfa_enabled, "active": u.active} for u in db.query(User).limit(200).all()], "version": "v0"}


@router.get("/api/notifications/read-all")
def read_all_get(p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    if not vuln("method_override"):
        raise HTTPException(405, "Method not allowed")
    from app.models import Notification
    db.query(Notification).filter(Notification.membership_id == p.membership.id).update({"read": True})
    db.commit()
    return {"ok": True}
