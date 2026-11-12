from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import Principal, audit, client_ip, like, paginate, require, team_member_ids, to_dict
from app.mode import vuln
from app.models import Customer, Document, Membership, Ticket, TicketComment, now
from app.services import log_activity, notify

router = APIRouter(prefix="/api/tickets", tags=["tickets"])
STATUSES = ["open", "in_progress", "waiting", "resolved", "closed"]
PRIORITIES = ["low", "medium", "high", "urgent"]
NEXT = {"open": {"in_progress", "waiting", "resolved"}, "in_progress": {"waiting", "resolved", "open"}, "waiting": {"in_progress", "resolved"}, "resolved": {"closed", "open"}, "closed": {"open"}}


def ticket_scope(db: Session, qs, p: Principal):
    qs = qs.filter(Ticket.org_id == p.org_id)
    if p.level == "org":
        return qs
    cust_ids = [c.id for c in db.query(Customer.id).filter(Customer.org_id == p.org_id, Customer.owner_id.in_(team_member_ids(db, p) if p.level == "team" else [p.membership.id])).all()]
    return qs.filter(or_(Ticket.customer_id.in_(cust_ids), Ticket.assignee_id == p.membership.id, Ticket.created_by == p.membership.id))


def get_ticket(db: Session, tid: int, p: Principal) -> Ticket:
    if vuln("bola"):
        t = db.get(Ticket, tid)
    else:
        t = ticket_scope(db, db.query(Ticket).filter(Ticket.id == tid), p).first()
    if not t:
        raise HTTPException(404, "Not found")
    return t


def mname(db, mid):
    m = db.get(Membership, mid) if mid else None
    return m.user.name if m else None


def ser(db, t):
    c = db.get(Customer, t.customer_id) if t.customer_id else None
    return {**to_dict(t), "assignee_name": mname(db, t.assignee_id), "customer_name": c.name if c else None, "created_by_name": mname(db, t.created_by)}


@router.get("")
def list_tickets(q: str = "", status: str = "", priority: str = "", assignee_id: int | None = None, customer_id: int | None = None, escalated: bool | None = None, page: int = 1, size: int = 25,
                 p: Principal = Depends(require("tickets.read")), db: Session = Depends(get_db)):
    qs = ticket_scope(db, db.query(Ticket), p)
    if q:
        qs = qs.filter(or_(Ticket.subject.ilike(like(q)), Ticket.description.ilike(like(q))))
    if status:
        qs = qs.filter(Ticket.status == status)
    if priority:
        qs = qs.filter(Ticket.priority == priority)
    if assignee_id:
        qs = qs.filter(Ticket.assignee_id == assignee_id)
    if customer_id:
        qs = qs.filter(Ticket.customer_id == customer_id)
    if escalated is not None:
        qs = qs.filter(Ticket.escalated == escalated)
    rows, meta = paginate(qs.order_by(Ticket.updated_at.desc()), page, size)
    return {"items": [ser(db, t) for t in rows], "meta": meta}


@router.post("", status_code=201)
def create_ticket(body: dict, request: Request, p: Principal = Depends(require("tickets.write")), db: Session = Depends(get_db)):
    if not body.get("subject"):
        raise HTTPException(422, "Subject is required")
    pr = body.get("priority", "medium")
    if pr not in PRIORITIES:
        raise HTTPException(422, "Invalid priority")
    cid = body.get("customer_id")
    if cid and not vuln("bola") and not db.query(Customer).filter(Customer.id == cid, Customer.org_id == p.org_id).first():
        raise HTTPException(422, "Invalid customer")
    t = Ticket(org_id=p.org_id, customer_id=cid, subject=body["subject"], description=body.get("description"), priority=pr, assignee_id=body.get("assignee_id") or p.membership.id, created_by=p.membership.id)
    db.add(t)
    db.flush()
    log_activity(db, p.org_id, "ticket", t.id, "system", "Ticket created", None, p.membership.id)
    audit(db, p, "ticket.create", "ticket", t.id, ip=client_ip(request))
    db.commit()
    return ser(db, t)


@router.get("/{tid}")
def get(tid: int, p: Principal = Depends(require("tickets.read")), db: Session = Depends(get_db)):
    t = get_ticket(db, tid, p)
    comments = db.query(TicketComment).filter(TicketComment.ticket_id == t.id).order_by(TicketComment.created_at).all()
    see_internal = p.can("tickets.write") or vuln("data_exposure")
    items = []
    for c in comments:
        if c.internal and not see_internal:
            continue
        d = {**to_dict(c), "author_name": mname(db, c.author_id)}
        if vuln("xss_stored"):
            d["body_html"] = c.body
        items.append(d)
    from app.models import Activity
    hist = db.query(Activity).filter(Activity.entity_type == "ticket", Activity.entity_id == t.id).order_by(Activity.created_at.desc()).all()
    return {**ser(db, t), "comments": items, "history": [{**to_dict(a), "actor_name": mname(db, a.actor_id)} for a in hist]}


@router.patch("/{tid}")
def update(tid: int, body: dict, request: Request, p: Principal = Depends(require("tickets.write")), db: Session = Depends(get_db)):
    t = get_ticket(db, tid, p)
    for k in ("subject", "description"):
        if k in body:
            setattr(t, k, body[k])
    if "priority" in body:
        if body["priority"] not in PRIORITIES:
            raise HTTPException(422, "Invalid priority")
        t.priority = body["priority"]
    if "assignee_id" in body:
        a = db.get(Membership, body["assignee_id"])
        if not a or (a.org_id != t.org_id and not vuln("reassign")):
            raise HTTPException(422, "Invalid assignee")
        t.assignee_id = a.id
        notify(db, t.org_id, a.id, "Ticket assigned to you", t.subject, f"/tickets/{t.id}")
    if "status" in body:
        s = body["status"]
        if s not in STATUSES:
            raise HTTPException(422, "Invalid status")
        if s != t.status and s not in NEXT[t.status] and not vuln("workflow_state"):
            raise HTTPException(409, f"Cannot move ticket from {t.status} to {s}")
        t.status = s
        t.resolved_at = now() if s in ("resolved", "closed") else None
        log_activity(db, t.org_id, "ticket", t.id, "system", f"Status: {s}", None, p.membership.id)
    audit(db, p, "ticket.update", "ticket", t.id, {"fields": list(body)}, ip=client_ip(request))
    db.commit()
    return ser(db, t)


@router.post("/{tid}/comments", status_code=201)
def comment(tid: int, body: dict, p: Principal = Depends(require("tickets.read")), db: Session = Depends(get_db)):
    t = get_ticket(db, tid, p)
    internal = bool(body.get("internal"))
    if internal and not p.can("tickets.write"):
        raise HTTPException(403, "Only support staff can add internal comments")
    if not p.can("tickets.write") and not internal and not vuln("bfla"):
        raise HTTPException(403, "Insufficient permissions")
    if not body.get("body"):
        raise HTTPException(422, "Comment is required")
    doc_id = body.get("document_id")
    if doc_id and not vuln("bola"):
        if not db.query(Document).filter(Document.id == doc_id, Document.org_id == t.org_id).first():
            raise HTTPException(422, "Invalid attachment")
    c = TicketComment(org_id=t.org_id, ticket_id=t.id, author_id=p.membership.id, body=body["body"], internal=internal, document_id=doc_id)
    db.add(c)
    t.updated_at = now()
    db.commit()
    d = {**to_dict(c), "author_name": mname(db, c.author_id)}
    if vuln("xss_stored"):
        d["body_html"] = c.body
    return d


@router.post("/{tid}/escalate")
def escalate(tid: int, body: dict, request: Request, p: Principal = Depends(require("tickets.write")), db: Session = Depends(get_db)):
    if not p.can("tickets.escalate") and not vuln("bfla"):
        raise HTTPException(403, "Insufficient permissions")
    t = get_ticket(db, tid, p)
    t.escalated = True
    t.priority = "urgent" if t.priority in ("high", "urgent") else "high"
    to = db.get(Membership, body.get("to")) if body.get("to") else None
    if to:
        t.escalated_to, t.assignee_id = to.id, to.id
        notify(db, t.org_id, to.id, "Ticket escalated to you", t.subject, f"/tickets/{t.id}")
    log_activity(db, t.org_id, "ticket", t.id, "system", "Escalated", body.get("reason"), p.membership.id)
    audit(db, p, "ticket.escalate", "ticket", t.id, ip=client_ip(request))
    db.commit()
    return ser(db, t)
