import hashlib
import hmac
import os
from fastapi import Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

COOKIE = "lab_gate"
OPEN_PATHS = {"/api/health", "/__gate"}

PAGE = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VULNCRM training lab</title>
<style>body{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;display:grid;place-items:center;height:100vh;margin:0}
form{background:#1e293b;padding:32px;border-radius:12px;width:320px}h1{font-size:18px;margin:0 0 8px}p{font-size:13px;color:#94a3b8;margin:0 0 16px}
input,button{width:100%;padding:10px;border-radius:8px;border:1px solid #334155;box-sizing:border-box;font-size:14px}
input{background:#0f172a;color:#e2e8f0;margin-bottom:12px}button{background:#2563eb;color:#fff;border:0;cursor:pointer}.e{color:#f87171;font-size:13px}</style></head>
<body><form method="post" action="/__gate"><h1>VULNCRM training lab</h1><p>Private training environment. Enter the lab access password you were given.</p>
<input type="password" name="password" placeholder="Lab password" autofocus required>__ERR__<button type="submit">Enter</button></form></body></html>"""


def _password():
    return os.environ.get("LAB_GATE_PASSWORD", "")


def _token():
    return hmac.new(_password().encode(), b"vulncrm-lab-gate", hashlib.sha256).hexdigest()


def enabled():
    return bool(_password())


async def gate_middleware(request: Request, call_next):
    if not enabled():
        return await call_next(request)
    path = request.url.path
    if request.client and request.client.host in ("127.0.0.1", "::1") and "x-forwarded-for" not in request.headers:
        return await call_next(request)
    if path == "/__gate":
        if request.method == "POST":
            form = (await request.body()).decode()
            from urllib.parse import parse_qs
            supplied = parse_qs(form).get("password", [""])[0]
            if hmac.compare_digest(supplied.encode(), _password().encode()):
                resp = RedirectResponse("/", status_code=303)
                resp.set_cookie(COOKIE, _token(), httponly=True, samesite="lax", secure=request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https", max_age=60 * 60 * 24 * 7)
                return resp
            return HTMLResponse(PAGE.replace("__ERR__", '<div class="e">Wrong password</div>'), status_code=401)
        return HTMLResponse(PAGE.replace("__ERR__", ""))
    if path in OPEN_PATHS:
        return await call_next(request)
    supplied = request.cookies.get(COOKIE, "") or request.headers.get("x-lab-key", "")
    if supplied and (hmac.compare_digest(supplied, _token()) or hmac.compare_digest(supplied, _password())):
        return await call_next(request)
    if "text/html" in request.headers.get("accept", ""):
        return RedirectResponse("/__gate", status_code=303)
    return JSONResponse({"detail": "Lab access password required"}, status_code=401)
