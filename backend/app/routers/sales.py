from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import Principal, audit, client_ip, get_or_404, like, paginate, require, scoped, to_dict
from app.mode import vuln
from app.models import Activity, Customer, CustomerContact, Lead, Membership, Opportunity, now
from app.services import dispatch_webhooks, log_activity, notify

leads_router = APIRouter(prefix="/api/leads", tags=["leads"])
opps_router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])

STAGES = ["prospecting", "qualification", "proposal", "negotiation", "closed_won"]
PROB = {"prospecting": 10, "qualification": 25, "proposal": 50, "negotiation": 75, "closed_won": 100, "closed_lost": 0}
LEAD_STATUSES = ["new", "contacted", "qualified", "disqualified", "converted"]


def mname(db, mid):
    m = db.get(Membership, mid) if mid else None
    return m.user.name if m else None


@leads_router.get("")
def list_leads(q: str = "", status: str = "", source: str = "", owner_id: int | None = None, page: int = 1, size: int = 25, p: Principal = Depends(require("leads.read")), db: Session = Depends(get_db)):
    qs = scoped(db, db.query(Lead), Lead, p)
    if q:
        qs = qs.filter(or_(Lead.name.ilike(like(q)), Lead.email.ilike(like(q)), Lead.company.ilike(like(q))))
    if status:
        qs = qs.filter(Lead.status == status)
    if source:
        qs = qs.filter(Lead.source == source)
    if owner_id:
        qs = qs.filter(Lead.owner_id == owner_id)
    rows, meta = paginate(qs.order_by(Lead.created_at.desc()), page, size)
    return {"items": [{**to_dict(l), "owner_name": mname(db, l.owner_id)} for l in rows], "meta": meta}


@leads_router.post("", status_code=201)
def create_lead(body: dict, request: Request, p: Principal = Depends(require("leads.write")), db: Session = Depends(get_db)):
    if not body.get("name"):
        raise HTTPException(422, "Name is required")
    allowed = ["name", "email", "phone", "company", "source", "notes", "estimated_value", "score"]
    data = {k: body[k] for k in allowed if k in body}
    if vuln("mass_assignment"):
        data.update({k: body[k] for k in ("org_id", "owner_id", "status", "qualification") if k in body})
    l = Lead(**data)
    l.org_id = l.org_id or p.org_id
    l.owner_id = l.owner_id or p.membership.id
    l.created_by = p.membership.id
    db.add(l)
    db.flush()
    log_activity(db, l.org_id, "lead", l.id, "system", "Lead created", f"Source: {l.source}", p.membership.id)
    audit(db, p, "lead.create", "lead", l.id, ip=client_ip(request))
    db.commit()
    dispatch_webhooks(p.org_id, "lead.created", {"id": l.id, "name": l.name})
    return to_dict(l)


@leads_router.get("/{lid}")
def get_lead(lid: int, p: Principal = Depends(require("leads.read")), db: Session = Depends(get_db)):
    l = get_or_404(db, Lead, lid, p)
    d = to_dict(l)
    d["owner_name"] = mname(db, l.owner_id)
    return d


@leads_router.patch("/{lid}")
def update_lead(lid: int, body: dict, request: Request, p: Principal = Depends(require("leads.write")), db: Session = Depends(get_db)):
    l = get_or_404(db, Lead, lid, p)
    allowed = {"name", "email", "phone", "company", "source", "notes", "estimated_value", "score"}
    if vuln("mass_assignment"):
        allowed |= {"owner_id", "status", "qualification", "org_id", "converted_customer_id"}
    for k, v in body.items():
        if k in allowed:
            setattr(l, k, v)
    audit(db, p, "lead.update", "lead", l.id, {"fields": list(body)}, ip=client_ip(request))
    db.commit()
    return to_dict(l)


@leads_router.delete("/{lid}")
def delete_lead(lid: int, p: Principal = Depends(require("leads.write")), db: Session = Depends(get_db)):
    if p.level == "own" and not vuln("bfla"):
        raise HTTPException(403, "Insufficient permissions")
    l = get_or_404(db, Lead, lid, p)
    db.delete(l)
    audit(db, p, "lead.delete", "lead", lid)
    db.commit()
    return {"ok": True}


@leads_router.put("/{lid}/assign")
def assign_lead(lid: int, body: dict, request: Request, p: Principal = Depends(require("leads.write")), db: Session = Depends(get_db)):
    if not p.can("leads.assign") and not vuln("reassign"):
        raise HTTPException(403, "Only managers can assign leads")
    l = get_or_404(db, Lead, lid, p, flag="reassign")
    target = db.get(Membership, body.get("owner_id"))
    if not target or (target.org_id != l.org_id and not vuln("reassign")):
        raise HTTPException(422, "Invalid owner")
    old = l.owner_id
    l.owner_id = target.id
    log_activity(db, l.org_id, "lead", l.id, "system", "Lead assigned", f"{mname(db, old)} → {mname(db, target.id)}", p.membership.id)
    notify(db, l.org_id, target.id, "New lead assigned", l.name, f"/leads/{l.id}")
    audit(db, p, "lead.assign", "lead", l.id, {"from": old, "to": target.id}, ip=client_ip(request))
    db.commit()
    return to_dict(l)


@leads_router.post("/{lid}/status")
def set_status(lid: int, body: dict, p: Principal = Depends(require("leads.write")), db: Session = Depends(get_db)):
    l = get_or_404(db, Lead, lid, p)
    new = body.get("status")
    if new not in LEAD_STATUSES or new == "converted":
        raise HTTPException(422, "Invalid status")
    if l.status == "converted":
        raise HTTPException(409, "Lead already converted")
    if new == "qualified":
        l.qualification = body.get("qualification", "sales_qualified")
    l.status = new
    log_activity(db, l.org_id, "lead", l.id, "system", f"Status: {new}", body.get("note"), p.membership.id)
    audit(db, p, "lead.status", "lead", l.id, {"status": new})
    db.commit()
    return to_dict(l)


@leads_router.post("/{lid}/convert")
def convert_lead(lid: int, body: dict, request: Request, p: Principal = Depends(require("leads.convert")), db: Session = Depends(get_db)):
    l = get_or_404(db, Lead, lid, p, flag="lead_convert")
    if not vuln("lead_convert"):
        if l.status != "qualified":
            raise HTTPException(409, "Only qualified leads can be converted")
    if l.status == "converted" and not vuln("lead_convert"):
        raise HTTPException(409, "Lead already converted")
    c = Customer(org_id=l.org_id, name=l.company or l.name, email=l.email, phone=l.phone, company=l.company, status="active", owner_id=l.owner_id or p.membership.id, notes=l.notes)
    db.add(c)
    db.flush()
    db.add(CustomerContact(org_id=l.org_id, customer_id=c.id, name=l.name, email=l.email, phone=l.phone, primary=True))
    opp = None
    if body.get("create_opportunity", True):
        opp = Opportunity(org_id=l.org_id, customer_id=c.id, lead_id=l.id, name=body.get("opportunity_name") or f"{c.name} – new business", amount=float(body.get("amount") or l.estimated_value or 0), owner_id=c.owner_id, stage="prospecting", probability=10)
        db.add(opp)
    l.status, l.converted_customer_id, l.converted_at = "converted", c.id, now()
    db.flush()
    log_activity(db, l.org_id, "lead", l.id, "system", "Lead converted", f"Customer #{c.id}", p.membership.id)
    log_activity(db, l.org_id, "customer", c.id, "system", "Created from lead conversion", f"Lead #{l.id}", p.membership.id)
    audit(db, p, "lead.convert", "lead", l.id, {"customer_id": c.id}, ip=client_ip(request))
    db.commit()
    dispatch_webhooks(l.org_id, "lead.converted", {"lead_id": l.id, "customer_id": c.id})
    return {"customer_id": c.id, "opportunity_id": opp.id if opp else None, "lead": to_dict(l)}


@leads_router.get("/{lid}/history")
def lead_history(lid: int, p: Principal = Depends(require("leads.read")), db: Session = Depends(get_db)):
    l = get_or_404(db, Lead, lid, p)
    rows = db.query(Activity).filter(Activity.entity_type == "lead", Activity.entity_id == l.id).order_by(Activity.created_at.desc()).all()
    return {"items": [{**to_dict(a), "actor_name": mname(db, a.actor_id)} for a in rows]}


def needs_approval(o: Opportunity) -> bool:
    return (o.amount or 0) * (1 - (o.discount_pct or 0) / 100) > 50000 or (o.discount_pct or 0) > 15


def ser_opp(db, o):
    d = to_dict(o)
    d["owner_name"] = mname(db, o.owner_id)
    d["customer_name"] = db.get(Customer, o.customer_id).name if o.customer_id and db.get(Customer, o.customer_id) else None
    d["requires_approval"] = needs_approval(o)
    return d


@opps_router.get("")
def list_opps(q: str = "", stage: str = "", owner_id: int | None = None, customer_id: int | None = None, page: int = 1, size: int = 25, p: Principal = Depends(require("opportunities.read")), db: Session = Depends(get_db)):
    qs = scoped(db, db.query(Opportunity), Opportunity, p)
    if q:
        qs = qs.filter(Opportunity.name.ilike(like(q)))
    if stage:
        qs = qs.filter(Opportunity.stage == stage)
    if owner_id:
        qs = qs.filter(Opportunity.owner_id == owner_id)
    if customer_id:
        qs = qs.filter(Opportunity.customer_id == customer_id)
    rows, meta = paginate(qs.order_by(Opportunity.updated_at.desc()), page, size)
    return {"items": [ser_opp(db, o) for o in rows], "meta": meta}


@opps_router.get("/pipeline")
def pipeline(p: Principal = Depends(require("opportunities.read")), db: Session = Depends(get_db)):
    rows = scoped(db, db.query(Opportunity), Opportunity, p).all()
    cols = {s: [] for s in STAGES + ["closed_lost"]}
    for o in rows:
        cols.setdefault(o.stage, []).append(ser_opp(db, o))
    return {"stages": [{"stage": s, "count": len(v), "value": sum(x["amount"] for x in v), "items": v} for s, v in cols.items()]}


@opps_router.get("/forecast")
def forecast(p: Principal = Depends(require("opportunities.read")), db: Session = Depends(get_db)):
    rows = scoped(db, db.query(Opportunity).filter(Opportunity.stage.notin_(["closed_won", "closed_lost"])), Opportunity, p).all()
    by_month = defaultdict(lambda: {"pipeline": 0.0, "weighted": 0.0, "count": 0})
    for o in rows:
        k = (o.expected_close or now()).strftime("%Y-%m")
        by_month[k]["pipeline"] += o.amount
        by_month[k]["weighted"] += o.amount * (o.probability or 0) / 100
        by_month[k]["count"] += 1
    return {"items": [{"month": k, **{a: round(b, 2) if isinstance(b, float) else b for a, b in v.items()}} for k, v in sorted(by_month.items())]}


@opps_router.post("", status_code=201)
def create_opp(body: dict, request: Request, p: Principal = Depends(require("opportunities.write")), db: Session = Depends(get_db)):
    if not body.get("name"):
        raise HTTPException(422, "Name is required")
    amount = float(body.get("amount") or 0)
    discount = float(body.get("discount_pct") or 0)
    if not vuln("deal_value") and (amount < 0 or not 0 <= discount <= 60):
        raise HTTPException(422, "Amount must be positive and discount between 0 and 60")
    cid = body.get("customer_id")
    if cid:
        cust = get_or_404(db, Customer, cid, p, flag="bola")
        if not vuln("mass_assignment") and cust.org_id != p.org_id:
            raise HTTPException(422, "Invalid customer")
    o = Opportunity(name=body["name"], amount=amount, discount_pct=discount, customer_id=cid, notes=body.get("notes"), expected_close=_dt(body.get("expected_close")))
    if vuln("mass_assignment"):
        for k in ("org_id", "owner_id", "stage", "probability", "approval_status", "approved_by"):
            if k in body:
                setattr(o, k, body[k])
    o.org_id = o.org_id or p.org_id
    o.owner_id = o.owner_id or p.membership.id
    o.probability = o.probability if vuln("mass_assignment") and "probability" in body else PROB.get(o.stage, 10)
    db.add(o)
    db.flush()
    log_activity(db, o.org_id, "opportunity", o.id, "system", "Opportunity created", None, p.membership.id)
    audit(db, p, "opportunity.create", "opportunity", o.id, ip=client_ip(request))
    db.commit()
    return ser_opp(db, o)


def _dt(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        raise HTTPException(422, "Invalid date")


@opps_router.get("/{oid}")
def get_opp(oid: int, p: Principal = Depends(require("opportunities.read")), db: Session = Depends(get_db)):
    return ser_opp(db, get_or_404(db, Opportunity, oid, p))


@opps_router.patch("/{oid}")
def update_opp(oid: int, body: dict, request: Request, p: Principal = Depends(require("opportunities.write")), db: Session = Depends(get_db)):
    o = get_or_404(db, Opportunity, oid, p)
    allowed = {"name", "notes", "expected_close", "amount", "discount_pct", "customer_id"}
    if vuln("mass_assignment") or vuln("workflow_state"):
        allowed |= {"stage", "probability", "approval_status", "approved_by", "owner_id", "closed_at", "org_id"}
    money_before = (o.amount, o.discount_pct)
    for k, v in body.items():
        if k not in allowed:
            continue
        if k == "expected_close":
            v = _dt(v)
        if k in ("amount", "discount_pct") and not vuln("deal_value"):
            v = float(v)
            if (k == "amount" and v < 0) or (k == "discount_pct" and not 0 <= v <= 60):
                raise HTTPException(422, "Invalid value")
        setattr(o, k, v)
    if (o.amount, o.discount_pct) != money_before and not vuln("deal_value"):
        if o.approval_status == "approved" and needs_approval(o):
            o.approval_status, o.approved_by = "pending", None
            log_activity(db, o.org_id, "opportunity", o.id, "system", "Approval reset", "Deal value changed after approval", p.membership.id)
    audit(db, p, "opportunity.update", "opportunity", o.id, {"fields": list(body)}, ip=client_ip(request))
    db.commit()
    return ser_opp(db, o)


@opps_router.post("/{oid}/stage")
def move_stage(oid: int, body: dict, request: Request, p: Principal = Depends(require("opportunities.write")), db: Session = Depends(get_db)):
    o = get_or_404(db, Opportunity, oid, p)
    new = body.get("stage")
    if new not in PROB:
        raise HTTPException(422, "Invalid stage")
    if o.stage in ("closed_won", "closed_lost") and not vuln("workflow_state"):
        raise HTTPException(409, "Closed opportunities cannot be moved")
    if not vuln("workflow_state"):
        if new != "closed_lost":
            if new not in STAGES or STAGES.index(new) != STAGES.index(o.stage) + 1:
                raise HTTPException(409, "Opportunities must move one stage at a time")
    if new == "closed_won" and needs_approval(o) and not vuln("approval_bypass"):
        if o.approval_status != "approved":
            raise HTTPException(409, "Manager approval is required before this deal can be closed")
    old = o.stage
    o.stage, o.probability = new, PROB[new]
    if new in ("closed_won", "closed_lost"):
        o.closed_at = now()
    log_activity(db, o.org_id, "opportunity", o.id, "stage_change", f"{old} → {new}", body.get("note"), p.membership.id)
    audit(db, p, "opportunity.stage", "opportunity", o.id, {"from": old, "to": new}, ip=client_ip(request))
    db.commit()
    dispatch_webhooks(o.org_id, "opportunity.stage_changed", {"id": o.id, "stage": new})
    return ser_opp(db, o)


@opps_router.post("/{oid}/request-approval")
def request_approval(oid: int, p: Principal = Depends(require("opportunities.write")), db: Session = Depends(get_db)):
    o = get_or_404(db, Opportunity, oid, p)
    if not needs_approval(o):
        raise HTTPException(409, "This deal does not require approval")
    o.approval_status = "pending"
    mgrs = db.query(Membership).filter(Membership.org_id == o.org_id, Membership.status == "active").all()
    for m in mgrs:
        if "opportunities.approve" in (m.role.permissions or []) and m.id != p.membership.id:
            notify(db, o.org_id, m.id, "Deal approval requested", o.name, f"/opportunities/{o.id}")
    log_activity(db, o.org_id, "opportunity", o.id, "system", "Approval requested", None, p.membership.id)
    audit(db, p, "opportunity.approval_requested", "opportunity", o.id)
    db.commit()
    return ser_opp(db, o)


@opps_router.post("/{oid}/approval")
def decide(oid: int, body: dict, p: Principal = Depends(require("opportunities.approve")), db: Session = Depends(get_db)):
    o = get_or_404(db, Opportunity, oid, p)
    decision = body.get("decision")
    if decision not in ("approved", "rejected"):
        raise HTTPException(422, "Decision must be approved or rejected")
    if o.approval_status != "pending":
        raise HTTPException(409, "No pending approval request")
    if o.owner_id == p.membership.id and not vuln("approval_bypass"):
        raise HTTPException(403, "You cannot approve your own deal")
    o.approval_status, o.approved_by = decision, p.membership.id
    log_activity(db, o.org_id, "opportunity", o.id, "system", f"Approval {decision}", body.get("note"), p.membership.id)
    notify(db, o.org_id, o.owner_id, f"Deal {decision}", o.name, f"/opportunities/{o.id}")
    audit(db, p, "opportunity.approval", "opportunity", o.id, {"decision": decision})
    db.commit()
    return ser_opp(db, o)


@opps_router.get("/{oid}/history")
def opp_history(oid: int, p: Principal = Depends(require("opportunities.read")), db: Session = Depends(get_db)):
    o = get_or_404(db, Opportunity, oid, p)
    rows = db.query(Activity).filter(Activity.entity_type == "opportunity", Activity.entity_id == o.id).order_by(Activity.created_at.desc()).all()
    return {"items": [{**to_dict(a), "actor_name": mname(db, a.actor_id)} for a in rows]}


@opps_router.delete("/{oid}")
def delete_opp(oid: int, p: Principal = Depends(require("opportunities.write")), db: Session = Depends(get_db)):
    if p.level == "own" and not vuln("bfla"):
        raise HTTPException(403, "Insufficient permissions")
    o = get_or_404(db, Opportunity, oid, p)
    db.delete(o)
    audit(db, p, "opportunity.delete", "opportunity", oid)
    db.commit()
    return {"ok": True}
