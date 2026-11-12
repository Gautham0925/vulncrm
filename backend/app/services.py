import ipaddress
import socket
import threading
from urllib.parse import urlparse

import httpx

from app.db import SessionLocal
from app.mode import vuln
from app.models import Activity, Notification, Webhook, now

BLOCKED_HOSTS = {"metadata.google.internal", "metadata", "instance-data"}


def log_activity(db, org_id, etype, eid, kind, subject=None, body=None, actor_id=None):
    a = Activity(org_id=org_id, entity_type=etype, entity_id=eid, kind=kind, subject=subject, body=body, actor_id=actor_id)
    db.add(a)
    return a


def notify(db, org_id, membership_id, title, body=None, link=None):
    db.add(Notification(org_id=org_id, membership_id=membership_id, title=title, body=body, link=link))


def egress_check(url: str, allow_private: bool = False) -> tuple[bool, str]:
    u = urlparse(url)
    if u.scheme not in ("http", "https"):
        return False, "Only http and https URLs are supported"
    host = u.hostname or ""
    if host.lower() in BLOCKED_HOSTS:
        return False, "Destination is not allowed"
    try:
        infos = socket.getaddrinfo(host, u.port or (443 if u.scheme == "https" else 80))
    except socket.gaierror:
        return False, "Host could not be resolved"
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_link_local or str(ip).startswith("169.254.") or ip.is_multicast or ip.is_unspecified:
            return False, "Destination is not allowed"
        if not allow_private and not vuln("ssrf") and (ip.is_private or ip.is_loopback or ip.is_reserved):
            return False, "Destination is not allowed"
    return True, ""


def safe_fetch(url: str, method: str = "GET", json=None, headers=None, timeout: float = 3.0, max_bytes: int = 20000, allow_private: bool = False):
    ok, why = egress_check(url, allow_private)
    if not ok:
        return {"ok": False, "error": why}
    try:
        r = httpx.request(method, url, json=json, headers=headers, timeout=timeout, follow_redirects=False)
        return {"ok": True, "status": r.status_code, "body": r.text[:max_bytes], "content_type": r.headers.get("content-type")}
    except httpx.HTTPError as e:
        return {"ok": False, "error": f"Request failed: {type(e).__name__}"}


def dispatch_webhooks(org_id: int, event: str, payload: dict):
    def run():
        db = SessionLocal()
        try:
            hooks = db.query(Webhook).filter(Webhook.org_id == org_id, Webhook.active.is_(True)).all()
            for h in hooks:
                if h.events and event not in h.events and "*" not in h.events:
                    continue
                res = safe_fetch(h.url, "POST", json={"event": event, "data": payload, "sent_at": now().isoformat()}, headers={"X-VulnCRM-Event": event}, timeout=1.5, max_bytes=200)
                h.last_status = str(res.get("status") or res.get("error"))
            db.commit()
        finally:
            db.close()
    if get_threading_enabled():
        threading.Thread(target=run, daemon=True).start()


def get_threading_enabled() -> bool:
    import os
    return os.environ.get("VULNCRM_DISABLE_WEBHOOKS") != "1"
