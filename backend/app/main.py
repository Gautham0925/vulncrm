import logging
import os
import traceback
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from app import seed
from app.config import get_settings
from app.db import SessionLocal
from app.graphql_api import router as graphql_router
from app.mode import mode, vuln
from app.models import ApiRequestLog
from app.routers import apimgmt, auth, customers, documents, misc, oauth, oidc_rp, people, reports, sales, saml, testlib, tickets

settings = get_settings()
log = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_error = None
    if settings.seed_on_start:
        try:
            seed.run()
        except Exception as exc:
            app.state.db_error = f"{type(exc).__name__}: {str(exc)[:400]}"
            log.error("Startup database error: %s", app.state.db_error)
    yield


app = FastAPI(title="VULNCRM API", version="1.0.0", description="Enterprise CRM API. Training environments may run an intentionally vulnerable configuration.", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)

for mod in (auth, customers, people, documents, tickets, reports, apimgmt, misc, oauth, oidc_rp, saml, testlib):
    for name in ("router", "api"):
        r = getattr(mod, name, None)
        if r is not None:
            app.include_router(r)
app.include_router(sales.leads_router)
app.include_router(sales.opps_router)
app.include_router(graphql_router)


@app.middleware("http")
async def platform_middleware(request: Request, call_next):
    if vuln("method_override") and request.headers.get("x-http-method-override"):
        request.scope["method"] = request.headers["x-http-method-override"].upper()
    origin = request.headers.get("origin")
    if request.method == "OPTIONS" and origin:
        from fastapi import Response
        resp = Response(status_code=204)
    else:
        resp = await call_next(request)
    if origin:
        if vuln("misconfig_cors"):
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Credentials"] = "true"
            resp.headers["Access-Control-Allow-Headers"] = request.headers.get("access-control-request-headers", "*")
            resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
        elif origin in [o.strip() for o in settings.cors_origins.split(",") if o.strip()]:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Credentials"] = "true"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-CSRF-Token, Authorization"
            resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
            resp.headers["Vary"] = "Origin"
    if not vuln("misconfig_headers"):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        preview = request.url.path.startswith("/api/documents/") and request.url.path.endswith("/preview")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN" if preview else "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if request.url.path.startswith("/api") and "content-security-policy" not in resp.headers:
            resp.headers["Content-Security-Policy"] = "frame-ancestors 'self'" if preview else "default-src 'none'; frame-ancestors 'none'"
        if settings.public_base_url.startswith("https"):
            resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    else:
        resp.headers["X-Powered-By"] = "VULNCRM/1.0 (FastAPI; Python)"
        resp.headers["Server"] = "uvicorn"
    resp.headers["X-VulnCRM-Mode"] = mode()
    principal = getattr(request.state, "principal", None)
    if principal is not None and principal.kind in ("api_key", "oauth") and request.url.path.startswith("/api"):
        db = SessionLocal()
        try:
            db.add(ApiRequestLog(org_id=principal.org_id, actor=principal.actor_label, method=request.method, path=request.url.path[:300], status=resp.status_code, ip=request.client.host if request.client else None))
            db.commit()
        finally:
            db.close()
    return resp


@app.exception_handler(HTTPException)
async def http_exc(request: Request, exc: HTTPException):
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
async def validation_exc(request: Request, exc: RequestValidationError):
    if vuln("verbose_errors"):
        return JSONResponse({"detail": exc.errors()[:5] and [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()[:5]]}, status_code=422)
    return JSONResponse({"detail": "Invalid request"}, status_code=422)


@app.exception_handler(Exception)
async def server_error(request: Request, exc: Exception):
    cid = uuid.uuid4().hex[:12]
    log.error("Unhandled error %s: %s", cid, "".join(traceback.format_exception(exc))[-1500:])
    if vuln("verbose_errors"):
        body = {"detail": f"{type(exc).__name__}: {exc}", "trace": traceback.format_exc().splitlines()[-12:], "path": request.url.path}
        if isinstance(exc, SQLAlchemyError):
            body["sql"] = str(getattr(exc, "statement", ""))[:600]
        return JSONResponse(body, status_code=500)
    return JSONResponse({"detail": "An unexpected error occurred", "correlation_id": cid}, status_code=500)


@app.get("/api/startup-status", include_in_schema=False)
def startup_status(request: Request):
    err = getattr(request.app.state, "db_error", None)
    return {"database": "error" if err else "ok", "detail": err if mode() == "vulnerable" else None}


static_root = os.path.abspath(settings.static_dir)
if os.path.isdir(static_root):
    if os.path.isdir(os.path.join(static_root, "assets")):
        app.mount("/assets", StaticFiles(directory=os.path.join(static_root, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith(("api/", "saml/", "oauth/", "oidc/", "graphql", "__internal")):
            raise HTTPException(404, "Not found")
        candidate = os.path.abspath(os.path.join(static_root, full_path))
        if full_path and candidate.startswith(static_root + os.sep) and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(static_root, "index.html"))
