from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import Principal, audit, client_ip, get_or_404, like, paginate, require, scoped, to_dict
from app.mode import vuln
from app.models import Activity, Customer, CustomerContact, Document, Membership, Opportunity, Ticket, now
from app.services import dispatch_webhooks, log_activity, notify

router = APIRouter(prefix="/api/customers", tags=["customers"])
SENSITIVE = ("internal_notes", "tax_id", "credit_limit")
SORTABLE = {"name", "created_at", "status", "tier", "industry", "company", "id"}


def ser(c: Customer, p: Principal) -> dict:
    d = to_dict(c)
    if not vuln("data_exposure") and not p.can("customers.reassign"):
        for k in SENSITIVE:
            d.pop(k, None)
    return d


def owner_label(db: Session, mid):
    if not mid:
        return None
    m = db.get(Membership, mid)
    return m.user.name if m else None


@router.get("")
def list_customers(request: Request, q: str = "", status: str = "", industry: str = "", owner_id: int | None = None, sort: str = "name", order: str = "asc",
                   page: int = 1, size: int = 25, p: Principal = Depends(require("customers.read")), db: Session = Depends(get_db)):
    if vuln("sqli") and q:
        stmt = (f"SELECT id, name, email, company, status, industry, tier, owner_id FROM customers "
                f"WHERE org_id = {p.org_id} AND deleted_at IS NULL AND (name LIKE '%{q}%' OR email LIKE '%{q}%' OR company LIKE '%{q}%') ORDER BY {sort} {'DESC' if order == 'desc' else 'ASC'}")
        rows = db.execute(text(stmt)).mappings().all()
        items = [dict(r) for r in rows][(page - 1) * size: page * size]
        return {"items": items, "meta": {"page": page, "size": size, "total": len(rows)}}
    qs = scoped(db, db.query(Customer).filter(Customer.deleted_at.is_(None)), Customer, p)
    if q:
        qs = qs.filter(or_(Customer.name.ilike(like(q)), Customer.email.ilike(like(q)), Customer.company.ilike(like(q))))
    if status:
        qs = qs.filter(Customer.status == status)
    if industry:
        qs = qs.filter(Customer.industry == industry)
    if owner_id:
        qs = qs.filter(Customer.owner_id == owner_id)
    col = getattr(Customer, sort if sort in SORTABLE else "name")
    qs = qs.order_by(col.desc() if order == "desc" else col.asc())
    rows, meta = paginate(qs, page, size)
    items = [{**ser(c, p), "owner_name": owner_label(db, c.owner_id)} for c in rows]
    return {"items": items, "meta": meta}


@router.post("", status_code=201)
def create_customer(body: dict, request: Request, p: Principal = Depends(require("customers.write")), db: Session = Depends(get_db)):
    if not body.get("name"):
        raise HTTPException(422, "Name is required")
    allowed = ["name", "email", "phone", "industry", "company", "website", "address", "status", "tier", "notes", "internal_notes", "credit_limit", "tax_id"]
    data = {k: body[k] for k in allowed if k in body}
    if vuln("mass_assignment"):
        data.update({k: body[k] for k in ("org_id", "owner_id") if k in body})
    c = Customer(**data)
    c.org_id = c.org_id or p.org_id
    c.owner_id = c.owner_id or p.membership.id
    if not p.can("customers.reassign") and not vuln("mass_assignment"):
        c.owner_id = p.membership.id
    db.add(c)
    db.flush()
    log_activity(db, c.org_id, "customer", c.id, "system", "Customer created", None, p.membership.id)
    audit(db, p, "customer.create", "customer", c.id, ip=client_ip(request))
    db.commit()
    dispatch_webhooks(p.org_id, "customer.created", {"id": c.id, "name": c.name})
    return ser(c, p)


@router.get("/{cid}")
def get_customer(cid: int, p: Principal = Depends(require("customers.read")), db: Session = Depends(get_db)):
    c = get_or_404(db, Customer, cid, p)
    d = ser(c, p)
    d["owner_name"] = owner_label(db, c.owner_id)
    d["contacts"] = [to_dict(x) for x in db.query(CustomerContact).filter(CustomerContact.customer_id == c.id).all()]
    d["opportunities"] = [to_dict(o, include_only=("id", "name", "amount", "stage", "expected_close")) for o in db.query(Opportunity).filter(Opportunity.customer_id == c.id).all()]
    d["ticket_count"] = db.query(Ticket).filter(Ticket.customer_id == c.id).count()
    return d


@router.patch("/{cid}")
def update_customer(cid: int, body: dict, request: Request, p: Principal = Depends(require("customers.write")), db: Session = Depends(get_db)):
    c = get_or_404(db, Customer, cid, p)
    allowed = {"name", "email", "phone", "industry", "company", "website", "address", "status", "tier", "notes"}
    if p.can("customers.reassign"):
        allowed |= {"internal_notes", "credit_limit", "tax_id", "owner_id"}
    if vuln("mass_assignment"):
        allowed |= {"internal_notes", "credit_limit", "tax_id", "owner_id", "org_id"}
    changed = {}
    for k, v in body.items():
        if k in allowed and hasattr(c, k):
            setattr(c, k, v)
            changed[k] = v
    audit(db, p, "customer.update", "customer", c.id, {"fields": list(changed)}, ip=client_ip(request))
    db.commit()
    return ser(c, p)


@router.delete("/{cid}")
def delete_customer(cid: int, request: Request, p: Principal = Depends(require("customers.write")), db: Session = Depends(get_db)):
    if not p.can("customers.delete") and not vuln("bfla"):
        raise HTTPException(403, "Insufficient permissions")
    c = get_or_404(db, Customer, cid, p)
    c.deleted_at = now()
    audit(db, p, "customer.delete", "customer", c.id, ip=client_ip(request))
    db.commit()
    return {"ok": True}


@router.put("/{cid}/owner")
def reassign(cid: int, body: dict, request: Request, p: Principal = Depends(require("customers.write")), db: Session = Depends(get_db)):
    if not p.can("customers.reassign") and not vuln("reassign"):
        raise HTTPException(403, "Only managers can reassign customers")
    c = get_or_404(db, Customer, cid, p)
    target = db.get(Membership, body.get("owner_id"))
    if not target or (target.org_id != c.org_id and not vuln("reassign")):
        raise HTTPException(422, "Invalid owner")
    old = c.owner_id
    c.owner_id = target.id
    log_activity(db, c.org_id, "customer", c.id, "system", "Owner changed", f"{owner_label(db, old)} → {owner_label(db, target.id)}", p.membership.id)
    notify(db, c.org_id, target.id, "Customer assigned to you", c.name, f"/customers/{c.id}")
    audit(db, p, "customer.reassign", "customer", c.id, {"from": old, "to": target.id}, ip=client_ip(request))
    db.commit()
    return ser(c, p)


@router.get("/{cid}/activities")
def activities(cid: int, p: Principal = Depends(require("customers.read")), db: Session = Depends(get_db)):
    c = get_or_404(db, Customer, cid, p)
    rows = db.query(Activity).filter(Activity.entity_type == "customer", Activity.entity_id == c.id).order_by(Activity.created_at.desc()).limit(200).all()
    items = []
    for a in rows:
        d = to_dict(a)
        d["actor_name"] = owner_label(db, a.actor_id)
        if vuln("xss_stored") and a.body:
            d["body_html"] = a.body
        items.append(d)
    return {"items": items}


@router.post("/{cid}/activities", status_code=201)
def add_activity(cid: int, body: dict, p: Principal = Depends(require("customers.write")), db: Session = Depends(get_db)):
    c = get_or_404(db, Customer, cid, p)
    kind = body.get("kind", "note")
    if kind not in ("note", "call", "email", "meeting"):
        raise HTTPException(422, "Invalid activity type")
    a = log_activity(db, c.org_id, "customer", c.id, kind, (body.get("subject") or "")[:200], body.get("body"), p.membership.id)
    db.commit()
    d = to_dict(a)
    if vuln("xss_stored") and a.body:
        d["body_html"] = a.body
    return d


@router.post("/{cid}/contacts", status_code=201)
def add_contact(cid: int, body: dict, p: Principal = Depends(require("customers.write")), db: Session = Depends(get_db)):
    c = get_or_404(db, Customer, cid, p)
    ct = CustomerContact(org_id=c.org_id, customer_id=c.id, name=body.get("name", ""), email=body.get("email"), phone=body.get("phone"), title=body.get("title"), primary=bool(body.get("primary")))
    if not ct.name:
        raise HTTPException(422, "Name is required")
    db.add(ct)
    db.commit()
    return to_dict(ct)


@router.delete("/{cid}/contacts/{contact_id}")
def delete_contact(cid: int, contact_id: int, p: Principal = Depends(require("customers.write")), db: Session = Depends(get_db)):
    c = get_or_404(db, Customer, cid, p)
    ct = db.query(CustomerContact).filter(CustomerContact.id == contact_id, CustomerContact.customer_id == c.id).first()
    if not ct:
        raise HTTPException(404, "Not found")
    db.delete(ct)
    db.commit()
    return {"ok": True}
