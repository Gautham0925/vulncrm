import csv
import html
import io
from collections import defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import Principal, audit, client_ip, current_principal, require, scoped
from app.mode import vuln
from app.models import Activity, Customer, Lead, Membership, Notification, Opportunity, Organization, Ticket, now

router = APIRouter(prefix="/api", tags=["reports"])
KINDS = {"sales": "Sales report", "customers": "Customer report", "lead-conversion": "Lead conversion report", "employee-performance": "Employee performance report",
         "opportunities": "Opportunity report", "organizations": "Organization report"}


def target_org(request: Request, p: Principal) -> int:
    if vuln("bola") and request.query_params.get("org_id"):
        return int(request.query_params["org_id"])
    return p.org_id


def window(range_: str):
    days = {"7d": 7, "30d": 30, "90d": 90, "365d": 365}.get(range_, 30)
    return now() - timedelta(days=days)


def name_of(db, mid):
    m = db.get(Membership, mid) if mid else None
    return m.user.name if m else "Unassigned"


@router.get("/dashboard")
def dashboard(range: str = "30d", p: Principal = Depends(require("reports.read")), db: Session = Depends(get_db)):
    since = window(range)
    cust = scoped(db, db.query(Customer).filter(Customer.deleted_at.is_(None)), Customer, p)
    leads = scoped(db, db.query(Lead), Lead, p)
    opps = scoped(db, db.query(Opportunity), Opportunity, p)
    open_opps = opps.filter(Opportunity.stage.notin_(["closed_won", "closed_lost"]))
    won = opps.filter(Opportunity.stage == "closed_won")
    won_period = won.filter(Opportunity.closed_at >= since).all()
    monthly = defaultdict(float)
    for o in won.all():
        if o.closed_at:
            monthly[o.closed_at.strftime("%Y-%m")] += o.amount * (1 - (o.discount_pct or 0) / 100)
    months = sorted(monthly)[-6:]
    perf = defaultdict(lambda: {"won": 0.0, "deals": 0, "open": 0})
    for o in opps.all():
        if o.stage == "closed_won":
            perf[o.owner_id]["won"] += o.amount
            perf[o.owner_id]["deals"] += 1
        elif o.stage != "closed_lost":
            perf[o.owner_id]["open"] += 1
    team = [{"name": name_of(db, k), **v} for k, v in sorted(perf.items(), key=lambda kv: -kv[1]["won"])][:8]
    stage_counts = defaultdict(lambda: {"count": 0, "value": 0.0})
    for o in open_opps.all():
        stage_counts[o.stage]["count"] += 1
        stage_counts[o.stage]["value"] += o.amount
    pending = opps.filter(Opportunity.approval_status == "pending").count() if p.can("opportunities.approve") else 0
    recent = db.query(Activity).filter(Activity.org_id == p.org_id).order_by(Activity.created_at.desc()).limit(8).all()
    return {
        "range": range,
        "kpis": {"customers": cust.count(), "active_accounts": cust.filter(Customer.status == "active").count(), "leads": leads.count(), "open_opportunities": open_opps.count(),
                 "closed_deals": won.count(), "monthly_revenue": round(monthly.get(now().strftime("%Y-%m"), 0.0), 2), "period_revenue": round(sum(o.amount for o in won_period), 2),
                 "pipeline_value": round(sum(o.amount for o in open_opps.all()), 2), "pending_approvals": pending,
                 "open_tickets": db.query(Ticket).filter(Ticket.org_id == p.org_id, Ticket.status.notin_(["resolved", "closed"])).count()},
        "revenue_by_month": [{"month": m, "revenue": round(monthly[m], 2)} for m in months],
        "pipeline_by_stage": [{"stage": k, **v} for k, v in stage_counts.items()],
        "team_performance": team,
        "recent_activities": [{"id": a.id, "kind": a.kind, "subject": a.subject, "entity_type": a.entity_type, "entity_id": a.entity_id, "actor": name_of(db, a.actor_id), "created_at": a.created_at.isoformat()} for a in recent],
        "unread_notifications": db.query(Notification).filter(Notification.org_id == p.org_id, Notification.membership_id == p.membership.id, Notification.read.is_(False)).count(),
    }


def build_report(kind: str, db: Session, p: Principal, org_id: int, range_: str):
    since = window(range_)
    scope_p = p if org_id == p.org_id else None

    def sc(q, model):
        return scoped(db, q, model, p) if scope_p else q.filter(model.org_id == org_id)

    if kind == "sales":
        rows = sc(db.query(Opportunity).filter(Opportunity.stage == "closed_won", Opportunity.closed_at >= since), Opportunity).all()
        data = [[o.id, o.name, name_of(db, o.owner_id), o.amount, o.discount_pct, round(o.amount * (1 - o.discount_pct / 100), 2), o.closed_at.strftime("%Y-%m-%d") if o.closed_at else ""] for o in rows]
        return ["ID", "Deal", "Owner", "Amount", "Discount %", "Net revenue", "Closed"], data, {"total_net": round(sum(r[5] for r in data), 2), "deals": len(data)}
    if kind == "customers":
        rows = sc(db.query(Customer).filter(Customer.deleted_at.is_(None)), Customer).all()
        data = [[c.id, c.name, c.industry or "", c.tier, c.status, name_of(db, c.owner_id), c.created_at.strftime("%Y-%m-%d")] for c in rows]
        return ["ID", "Customer", "Industry", "Tier", "Status", "Owner", "Created"], data, {"customers": len(data)}
    if kind == "lead-conversion":
        rows = sc(db.query(Lead), Lead).all()
        by = defaultdict(lambda: [0, 0])
        for l in rows:
            by[l.source][0] += 1
            by[l.source][1] += 1 if l.status == "converted" else 0
        data = [[s, t, c, f"{(c / t * 100):.0f}%" if t else "0%"] for s, (t, c) in sorted(by.items())]
        total, conv = len(rows), sum(1 for l in rows if l.status == "converted")
        return ["Source", "Leads", "Converted", "Rate"], data, {"leads": total, "converted": conv, "rate": f"{(conv / total * 100):.0f}%" if total else "0%"}
    if kind == "opportunities":
        rows = sc(db.query(Opportunity), Opportunity).all()
        data = [[o.id, o.name, o.stage, o.amount, o.probability, o.approval_status, name_of(db, o.owner_id)] for o in rows]
        return ["ID", "Opportunity", "Stage", "Amount", "Probability", "Approval", "Owner"], data, {"count": len(data), "value": round(sum(r[3] for r in data), 2)}
    if kind == "employee-performance":
        if not p.can("employees.read") and not vuln("bfla"):
            raise HTTPException(403, "Insufficient permissions")
        ms = db.query(Membership).filter(Membership.org_id == org_id, Membership.status == "active").all()
        if p.level == "own" and not vuln("bfla"):
            ms = [m for m in ms if m.id == p.membership.id]
        data = []
        for m in ms:
            os_ = db.query(Opportunity).filter(Opportunity.owner_id == m.id).all()
            won = [o for o in os_ if o.stage == "closed_won"]
            data.append([m.user.name, m.role.name, len(os_), len(won), round(sum(o.amount for o in won), 2), db.query(Lead).filter(Lead.owner_id == m.id).count()])
        return ["Employee", "Role", "Deals", "Won", "Won value", "Leads"], data, {"employees": len(data)}
    if kind == "organizations":
        if not p.can("employees.read") and not vuln("bfla"):
            raise HTTPException(403, "Insufficient permissions")
        orgs = db.query(Organization).order_by(Organization.id).all() if p.super_admin else [db.get(Organization, org_id)]
        data = [[o.name, db.query(Membership).filter(Membership.org_id == o.id).count(), db.query(Customer).filter(Customer.org_id == o.id, Customer.deleted_at.is_(None)).count(),
                 db.query(Opportunity).filter(Opportunity.org_id == o.id).count(), round(sum(x.amount for x in db.query(Opportunity).filter(Opportunity.org_id == o.id, Opportunity.stage == "closed_won")), 2)] for o in orgs]
        return ["Organization", "Members", "Customers", "Opportunities", "Won revenue"], data, {"organizations": len(data)}
    raise HTTPException(404, "Unknown report")


@router.get("/reports")
def report_index(p: Principal = Depends(require("reports.read"))):
    return {"items": [{"kind": k, "name": v} for k, v in KINDS.items()]}


@router.get("/reports/{kind}")
def report(kind: str, request: Request, range: str = "90d", p: Principal = Depends(require("reports.read")), db: Session = Depends(get_db)):
    cols, rows, summary = build_report(kind, db, p, target_org(request, p), range)
    return {"kind": kind, "name": KINDS.get(kind), "columns": cols, "rows": rows, "summary": summary}


def csv_cell(v):
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v


@router.get("/reports/{kind}/export")
def export(kind: str, request: Request, format: str = "csv", range: str = "90d", p: Principal = Depends(require("reports.export")), db: Session = Depends(get_db)):
    cols, rows, summary = build_report(kind, db, p, target_org(request, p), range)
    audit(db, p, "report.export", "report", kind, {"format": format}, ip=client_ip(request))
    db.commit()
    if format == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(cols)
        for r in rows:
            w.writerow([csv_cell(x) for x in r])
        return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={kind}-report.csv"})
    if format == "pdf":
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import landscape, letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        out = io.BytesIO()
        doc = SimpleDocTemplate(out, pagesize=landscape(letter), title=KINDS.get(kind, kind))
        st = getSampleStyleSheet()
        t = Table([cols] + [[str(c) for c in r] for r in rows[:200]], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F46E5")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0"))]))
        doc.build([Paragraph(KINDS.get(kind, kind), st["Title"]), Paragraph(", ".join(f"{k}: {v}" for k, v in summary.items()), st["Normal"]), Spacer(1, 12), t])
        return Response(out.getvalue(), media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={kind}-report.pdf"})
    raise HTTPException(422, "Format must be csv or pdf")


@router.get("/reports/{kind}/print", response_class=HTMLResponse)
def print_view(kind: str, request: Request, title: str = "", range: str = "90d", p: Principal = Depends(require("reports.read")), db: Session = Depends(get_db)):
    cols, rows, summary = build_report(kind, db, p, target_org(request, p), range)
    heading = title or KINDS.get(kind, kind)
    heading_html = heading if vuln("xss_reflected") else html.escape(heading)
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in cols)
    body = "".join("<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in r) + "</tr>" for r in rows)
    page = f"<!doctype html><html><head><meta charset='utf-8'><title>Report</title><style>body{{font:14px system-ui;margin:32px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #e2e8f0;padding:6px 10px;text-align:left}}th{{background:#4F46E5;color:#fff}}</style></head><body><h1>{heading_html}</h1><table><tr>{head}</tr>{body}</table></body></html>"
    headers = {} if vuln("xss_reflected") else {"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'", "X-Content-Type-Options": "nosniff"}
    return HTMLResponse(page, headers=headers)
