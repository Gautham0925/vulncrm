import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import Principal, audit, client_ip, like, paginate, require, to_dict
from app.models import SecurityTestCase, SecurityTestCaseVersion

api = APIRouter(prefix="/api/testlib", tags=["security-test-library"])
FIELDS = ["code", "category", "title", "description", "module", "preconditions", "required_role", "objective", "procedure", "expected_secure", "indicators", "severity", "evidence",
          "remediation", "references", "auth_required", "api_type", "technology", "execution", "vuln_toggle"]
SEVERITIES = ["info", "low", "medium", "high", "critical"]


def snapshot(t: SecurityTestCase) -> dict:
    return {k: getattr(t, k) for k in FIELDS}


def apply(t: SecurityTestCase, data: dict):
    for k in FIELDS:
        if k in data:
            setattr(t, k, data[k])
    if t.severity not in SEVERITIES:
        raise HTTPException(422, "Severity must be one of " + ", ".join(SEVERITIES))


@api.get("/facets")
def facets(p: Principal = Depends(require("testlib.read")), db: Session = Depends(get_db)):
    rows = db.query(SecurityTestCase).all()
    pick = lambda attr: sorted({getattr(r, attr) for r in rows if getattr(r, attr) not in (None, "")})
    return {"categories": pick("category"), "modules": pick("module"), "severities": SEVERITIES, "api_types": pick("api_type"), "technologies": pick("technology"), "executions": pick("execution"), "total": len(rows)}


@api.get("/cases")
def list_cases(q: str = "", category: str = "", module: str = "", severity: str = "", auth_required: bool | None = None, api_type: str = "", technology: str = "", execution: str = "",
               page: int = 1, size: int = 25, p: Principal = Depends(require("testlib.read")), db: Session = Depends(get_db)):
    qs = db.query(SecurityTestCase)
    if q:
        qs = qs.filter(or_(SecurityTestCase.title.ilike(like(q)), SecurityTestCase.code.ilike(like(q)), SecurityTestCase.description.ilike(like(q))))
    for col, val in (("category", category), ("module", module), ("severity", severity), ("api_type", api_type), ("technology", technology), ("execution", execution)):
        if val:
            qs = qs.filter(getattr(SecurityTestCase, col) == val)
    if auth_required is not None:
        qs = qs.filter(SecurityTestCase.auth_required == auth_required)
    rows, meta = paginate(qs.order_by(SecurityTestCase.code), page, size)
    return {"items": [to_dict(t, exclude=("procedure", "indicators", "expected_secure", "evidence", "remediation", "preconditions", "objective", "description")) for t in rows], "meta": meta}


@api.get("/cases/{tid}")
def get_case(tid: int, p: Principal = Depends(require("testlib.read")), db: Session = Depends(get_db)):
    t = db.get(SecurityTestCase, tid)
    if not t:
        raise HTTPException(404, "Not found")
    return to_dict(t)


@api.post("/cases", status_code=201)
def create_case(body: dict, request: Request, p: Principal = Depends(require("testlib.manage")), db: Session = Depends(get_db)):
    if not body.get("code") or not body.get("title") or not body.get("category"):
        raise HTTPException(422, "Code, title and category are required")
    if db.query(SecurityTestCase).filter(SecurityTestCase.code == body["code"]).first():
        raise HTTPException(409, "A test case with that ID exists")
    t = SecurityTestCase()
    apply(t, body)
    db.add(t)
    db.flush()
    db.add(SecurityTestCaseVersion(test_case_id=t.id, version=1, snapshot=snapshot(t)))
    audit(db, p, "testcase.create", "test_case", t.code, ip=client_ip(request))
    db.commit()
    return to_dict(t)


@api.patch("/cases/{tid}")
def update_case(tid: int, body: dict, request: Request, p: Principal = Depends(require("testlib.manage")), db: Session = Depends(get_db)):
    t = db.get(SecurityTestCase, tid)
    if not t:
        raise HTTPException(404, "Not found")
    body.pop("code", None)
    apply(t, body)
    t.version += 1
    db.add(SecurityTestCaseVersion(test_case_id=t.id, version=t.version, snapshot=snapshot(t)))
    audit(db, p, "testcase.update", "test_case", t.code, {"version": t.version}, ip=client_ip(request))
    db.commit()
    return to_dict(t)


@api.delete("/cases/{tid}")
def delete_case(tid: int, p: Principal = Depends(require("testlib.manage")), db: Session = Depends(get_db)):
    t = db.get(SecurityTestCase, tid)
    if not t:
        raise HTTPException(404, "Not found")
    db.query(SecurityTestCaseVersion).filter(SecurityTestCaseVersion.test_case_id == t.id).delete()
    db.delete(t)
    audit(db, p, "testcase.delete", "test_case", t.code)
    db.commit()
    return {"ok": True}


@api.get("/cases/{tid}/versions")
def versions(tid: int, p: Principal = Depends(require("testlib.read")), db: Session = Depends(get_db)):
    rows = db.query(SecurityTestCaseVersion).filter(SecurityTestCaseVersion.test_case_id == tid).order_by(SecurityTestCaseVersion.version.desc()).all()
    return {"items": [{"version": v.version, "created_at": v.created_at.isoformat(), "snapshot": v.snapshot} for v in rows]}


@api.post("/cases/{tid}/restore/{version}")
def restore(tid: int, version: int, p: Principal = Depends(require("testlib.manage")), db: Session = Depends(get_db)):
    t = db.get(SecurityTestCase, tid)
    v = db.query(SecurityTestCaseVersion).filter(SecurityTestCaseVersion.test_case_id == tid, SecurityTestCaseVersion.version == version).first()
    if not t or not v:
        raise HTTPException(404, "Not found")
    apply(t, {k: x for k, x in v.snapshot.items() if k != "code"})
    t.version += 1
    db.add(SecurityTestCaseVersion(test_case_id=t.id, version=t.version, snapshot=snapshot(t)))
    audit(db, p, "testcase.restore", "test_case", t.code, {"from_version": version})
    db.commit()
    return to_dict(t)


@api.get("/export")
def export(p: Principal = Depends(require("testlib.read")), db: Session = Depends(get_db)):
    rows = db.query(SecurityTestCase).order_by(SecurityTestCase.code).all()
    return Response(json.dumps({"format": "vulncrm-testcases/1", "cases": [snapshot(t) for t in rows]}, indent=2), media_type="application/json", headers={"Content-Disposition": "attachment; filename=vulncrm-test-cases.json"})


@api.post("/import")
def import_cases(body: dict, request: Request, p: Principal = Depends(require("testlib.manage")), db: Session = Depends(get_db)):
    cases = body.get("cases")
    if not isinstance(cases, list):
        raise HTTPException(422, "Expected an object with a 'cases' list")
    created = updated = 0
    for c in cases:
        if not isinstance(c, dict) or not c.get("code") or not c.get("title") or not c.get("category"):
            raise HTTPException(422, "Every case needs code, title and category")
        t = db.query(SecurityTestCase).filter(SecurityTestCase.code == c["code"]).first()
        if t:
            apply(t, {k: v for k, v in c.items() if k != "code"})
            t.version += 1
            updated += 1
        else:
            t = SecurityTestCase()
            apply(t, c)
            db.add(t)
            created += 1
        db.flush()
        db.add(SecurityTestCaseVersion(test_case_id=t.id, version=t.version, snapshot=snapshot(t)))
    audit(db, p, "testcase.import", "test_case", None, {"created": created, "updated": updated}, ip=client_ip(request))
    db.commit()
    return {"created": created, "updated": updated}
