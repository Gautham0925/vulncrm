import mimetypes
import os
import re
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import Principal, audit, client_ip, current_principal, like, paginate, require, team_member_ids, to_dict
from app.mode import vuln
from app.models import Customer, Document, DocumentPermission, DocumentVersion, Membership, now
from app.services import log_activity, notify

router = APIRouter(tags=["documents"])
settings = get_settings()
ALLOWED = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".txt": "text/plain", ".csv": "text/csv",
           ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
           ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}
MAGIC = {".pdf": b"%PDF", ".png": b"\x89PNG", ".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff", ".docx": b"PK", ".xlsx": b"PK", ".pptx": b"PK"}
MAX_BYTES = 10 * 1024 * 1024
INLINE_SAFE = {"image/png", "image/jpeg", "application/pdf", "text/plain"}
STATUSES = ["draft", "in_review", "approved", "signed", "rejected"]


def root() -> str:
    r = os.path.abspath(settings.upload_dir)
    os.makedirs(r, exist_ok=True)
    return r


def safe_display_name(name: str) -> str:
    base = os.path.basename((name or "file").replace("\\", "/"))
    base = re.sub(r"[^\w.\- ]", "_", base)[:120]
    return base or "file"


def resolve_inside(path: str) -> str:
    full = os.path.abspath(path)
    if not (full == root() or full.startswith(root() + os.sep)):
        raise HTTPException(400, "Invalid file path")
    return full


def level_for(db: Session, p: Principal, d: Document) -> str | None:
    if d.owner_id == p.membership.id:
        return "write"
    if d.org_id != p.org_id:
        return None
    perm = db.query(DocumentPermission).filter(DocumentPermission.document_id == d.id, DocumentPermission.membership_id == p.membership.id).first()
    if perm:
        return perm.level
    if p.level == "org" and p.can("documents.read"):
        return "write" if p.can("documents.write") and p.role.key in ("org_admin", "super_admin") else "read"
    if p.level == "team" and d.owner_id in team_member_ids(db, p):
        return "write"
    if d.visibility == "org":
        return "read"
    return None


def load_doc(db: Session, did: int, p: Principal, need: str = "read", flag: str = "file_download") -> Document:
    d = db.get(Document, did)
    if not d or d.deleted_at:
        raise HTTPException(404, "Not found")
    if vuln(flag):
        return d
    lvl = level_for(db, p, d)
    if lvl is None or (need == "write" and lvl != "write"):
        raise HTTPException(404, "Not found")
    return d


def ser(db: Session, d: Document, p: Principal) -> dict:
    v = db.query(DocumentVersion).filter(DocumentVersion.document_id == d.id, DocumentVersion.version == d.current_version).first()
    o = db.get(Membership, d.owner_id) if d.owner_id else None
    return {**to_dict(d), "owner_name": o.user.name if o else None, "size": v.size if v else 0, "content_type": v.content_type if v else None, "original_name": v.original_name if v else None,
            "access": level_for(db, p, d)}


async def save_upload(file: UploadFile, org_id: int) -> tuple[str, str, str, int]:
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File too large (10 MB max)")
    original = file.filename or "upload"
    ext = os.path.splitext(original)[1].lower()
    ctype = file.content_type or mimetypes.guess_type(original)[0] or "application/octet-stream"
    folder = os.path.join(root(), f"org_{org_id}")
    os.makedirs(folder, exist_ok=True)
    if vuln("file_upload"):
        stored = original if vuln("file_name") else f"{uuid.uuid4().hex}{ext}"
    else:
        if ext not in ALLOWED:
            raise HTTPException(415, "This file type is not allowed")
        if ctype.split(";")[0] != ALLOWED[ext]:
            raise HTTPException(415, "File content type does not match its extension")
        magic = MAGIC.get(ext)
        if magic and not data.startswith(magic):
            raise HTTPException(415, "File content does not match its type")
        stored = f"{uuid.uuid4().hex}{ext}"
        ctype = ALLOWED[ext]
    full = resolve_inside(os.path.join(folder, stored))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "wb") as f:
        f.write(data)
    rel = os.path.relpath(full, root())
    return original, rel, ctype, len(data)


@router.get("/api/documents")
def list_documents(q: str = "", kind: str = "", customer_id: int | None = None, page: int = 1, size: int = 25, p: Principal = Depends(require("documents.read")), db: Session = Depends(get_db)):
    qs = db.query(Document).filter(Document.org_id == p.org_id, Document.deleted_at.is_(None))
    if q:
        qs = qs.filter(Document.name.ilike(like(q)))
    if kind:
        qs = qs.filter(Document.kind == kind)
    if customer_id:
        qs = qs.filter(Document.customer_id == customer_id)
    rows = [d for d in qs.order_by(Document.updated_at.desc()).all() if level_for(db, p, d)]
    total = len(rows)
    rows = rows[(page - 1) * size: page * size]
    return {"items": [ser(db, d, p) for d in rows], "meta": {"page": page, "size": size, "total": total}}


@router.post("/api/documents", status_code=201)
async def upload(request: Request, file: UploadFile = File(...), name: str = Form(""), kind: str = Form("general"), visibility: str = Form("private"), customer_id: int | None = Form(None),
                 p: Principal = Depends(require("documents.write")), db: Session = Depends(get_db)):
    if kind not in ("general", "contract", "proposal") or visibility not in ("private", "shared", "org"):
        raise HTTPException(422, "Invalid kind or visibility")
    if customer_id and not vuln("bola"):
        c = db.query(Customer).filter(Customer.id == customer_id, Customer.org_id == p.org_id).first()
        if not c:
            raise HTTPException(422, "Invalid customer")
    original, rel, ctype, size = await save_upload(file, p.org_id)
    d = Document(org_id=p.org_id, name=name or safe_display_name(original), kind=kind, visibility=visibility, owner_id=p.membership.id, customer_id=customer_id)
    db.add(d)
    db.flush()
    db.add(DocumentVersion(document_id=d.id, version=1, original_name=original, stored_name=rel, content_type=ctype, size=size, uploaded_by=p.membership.id))
    if customer_id:
        log_activity(db, p.org_id, "customer", customer_id, "system", "Document uploaded", d.name, p.membership.id)
    audit(db, p, "document.upload", "document", d.id, {"name": d.name, "size": size}, ip=client_ip(request))
    db.commit()
    return ser(db, d, p)


@router.get("/api/documents/{did}")
def get_document(did: int, p: Principal = Depends(require("documents.read")), db: Session = Depends(get_db)):
    d = load_doc(db, did, p)
    versions = db.query(DocumentVersion).filter(DocumentVersion.document_id == d.id).order_by(DocumentVersion.version.desc()).all()
    perms = db.query(DocumentPermission).filter(DocumentPermission.document_id == d.id).all()
    return {**ser(db, d, p), "versions": [to_dict(v, exclude=("stored_name",)) for v in versions],
            "shared_with": [{**to_dict(x), "name": db.get(Membership, x.membership_id).user.name} for x in perms]}


@router.patch("/api/documents/{did}")
def update_document(did: int, body: dict, p: Principal = Depends(require("documents.write")), db: Session = Depends(get_db)):
    d = load_doc(db, did, p, "write", flag="bola")
    for k in ("name", "kind", "visibility"):
        if k in body:
            setattr(d, k, body[k])
    if "status" in body:
        if body["status"] not in STATUSES:
            raise HTTPException(422, "Invalid status")
        d.status = body["status"]
        audit(db, p, "document.status", "document", d.id, {"status": d.status})
    db.commit()
    return ser(db, d, p)


@router.delete("/api/documents/{did}")
def delete_document(did: int, p: Principal = Depends(require("documents.write")), db: Session = Depends(get_db)):
    d = load_doc(db, did, p, "write", flag="bola")
    if d.owner_id != p.membership.id and p.level == "own" and not vuln("bfla"):
        raise HTTPException(403, "Only the owner can delete a document")
    d.deleted_at = now()
    audit(db, p, "document.delete", "document", d.id)
    db.commit()
    return {"ok": True}


def send(db: Session, d: Document, version: int | None, inline: bool):
    q = db.query(DocumentVersion).filter(DocumentVersion.document_id == d.id)
    v = q.filter(DocumentVersion.version == version).first() if version else q.filter(DocumentVersion.version == d.current_version).first()
    if not v:
        raise HTTPException(404, "Version not found")
    full = resolve_inside(os.path.join(root(), v.stored_name))
    if not os.path.exists(full):
        raise HTTPException(404, "File missing")
    name = safe_display_name(v.original_name)
    if inline:
        if vuln("file_upload"):
            return FileResponse(full, media_type=v.content_type, headers={"Content-Disposition": f"inline; filename=\"{v.original_name}\""})
        if v.content_type not in INLINE_SAFE:
            raise HTTPException(415, "Preview is not available for this file type")
        return FileResponse(full, media_type=v.content_type, headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(name)}", "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox; default-src 'none'"})
    return FileResponse(full, media_type="application/octet-stream", headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}", "X-Content-Type-Options": "nosniff"})


@router.get("/api/documents/{did}/download")
def download(did: int, request: Request, version: int | None = None, p: Principal = Depends(require("documents.read")), db: Session = Depends(get_db)):
    d = load_doc(db, did, p)
    audit(db, p, "document.download", "document", d.id, ip=client_ip(request))
    db.commit()
    return send(db, d, version, False)


@router.get("/api/documents/{did}/preview")
def preview(did: int, version: int | None = None, p: Principal = Depends(require("documents.read")), db: Session = Depends(get_db)):
    return send(db, load_doc(db, did, p), version, True)


@router.post("/api/documents/{did}/versions", status_code=201)
async def new_version(did: int, request: Request, file: UploadFile = File(...), p: Principal = Depends(require("documents.read")), db: Session = Depends(get_db)):
    if vuln("file_replace"):
        d = load_doc(db, did, p, "read", flag="file_replace")
    else:
        if not p.can("documents.write"):
            raise HTTPException(403, "Insufficient permissions")
        d = load_doc(db, did, p, "write", flag="never")
    original, rel, ctype, size = await save_upload(file, d.org_id)
    d.current_version += 1
    db.add(DocumentVersion(document_id=d.id, version=d.current_version, original_name=original, stored_name=rel, content_type=ctype, size=size, uploaded_by=p.membership.id))
    audit(db, p, "document.version", "document", d.id, {"version": d.current_version}, ip=client_ip(request))
    db.commit()
    return ser(db, d, p)


@router.post("/api/documents/{did}/share")
def share(did: int, body: dict, request: Request, p: Principal = Depends(require("documents.read")), db: Session = Depends(get_db)):
    d = load_doc(db, did, p, "read", flag="doc_share")
    if not vuln("doc_share"):
        if not (d.owner_id == p.membership.id or p.can("documents.share")):
            raise HTTPException(403, "Only the owner or a manager can share this document")
    target = db.get(Membership, body.get("membership_id"))
    level = body.get("level", "read")
    if not target or level not in ("read", "write") or (target.org_id != d.org_id and not vuln("doc_share")):
        raise HTTPException(422, "Invalid share target")
    perm = db.query(DocumentPermission).filter(DocumentPermission.document_id == d.id, DocumentPermission.membership_id == target.id).first()
    if perm:
        perm.level = level
    else:
        db.add(DocumentPermission(document_id=d.id, membership_id=target.id, level=level, granted_by=p.membership.id))
    if d.visibility == "private":
        d.visibility = "shared"
    notify(db, target.org_id, target.id, "A document was shared with you", d.name, f"/documents/{d.id}")
    audit(db, p, "document.share", "document", d.id, {"to": target.id, "level": level}, ip=client_ip(request))
    db.commit()
    return {"ok": True}


@router.delete("/api/documents/{did}/share/{mid}")
def unshare(did: int, mid: int, p: Principal = Depends(require("documents.read")), db: Session = Depends(get_db)):
    d = load_doc(db, did, p, "read", flag="doc_share")
    if not vuln("doc_share") and not (d.owner_id == p.membership.id or p.can("documents.share")):
        raise HTTPException(403, "Insufficient permissions")
    db.query(DocumentPermission).filter(DocumentPermission.document_id == d.id, DocumentPermission.membership_id == mid).delete()
    audit(db, p, "document.unshare", "document", d.id, {"from": mid})
    db.commit()
    return {"ok": True}


@router.put("/api/documents/{did}/owner")
def transfer(did: int, body: dict, p: Principal = Depends(require("documents.read")), db: Session = Depends(get_db)):
    d = load_doc(db, did, p, "read", flag="ownership")
    if not vuln("ownership") and d.owner_id != p.membership.id and not p.can("documents.share"):
        raise HTTPException(403, "Only the owner can transfer ownership")
    target = db.get(Membership, body.get("owner_id"))
    if not target or (target.org_id != d.org_id and not vuln("ownership")):
        raise HTTPException(422, "Invalid owner")
    old = d.owner_id
    d.owner_id = target.id
    audit(db, p, "document.owner_changed", "document", d.id, {"from": old, "to": target.id})
    db.commit()
    return ser(db, d, p)


@router.get("/api/files/{path:path}")
def raw_file(path: str):
    if not vuln("file_download"):
        raise HTTPException(404, "Not found")
    full = resolve_inside(os.path.join(root(), path))
    if not os.path.isfile(full):
        raise HTTPException(404, "Not found")
    return FileResponse(full, media_type=mimetypes.guess_type(full)[0] or "application/octet-stream")
