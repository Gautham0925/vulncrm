import os, sys, json, inspect, tempfile

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(root, "backend"))
tmp = tempfile.mkdtemp()
os.environ.update(DATABASE_URL=f"sqlite:///{tmp}/d.db", UPLOAD_DIR=f"{tmp}/up", KEYS_DIR=f"{tmp}/k", IDP_CERT_DIR=f"{tmp}/i", VULNCRM_DISABLE_WEBHOOKS="1")

from fastapi.testclient import TestClient
import app.main as m
from app.db import Base
import app.models
from app.mode import ALL_FLAGS
from app.testcases_seed import CASES
from app.rbac import PERMISSIONS, SYSTEM_ROLES

docs = os.path.join(root, "docs")
os.makedirs(docs, exist_ok=True)

with TestClient(m.app) as c:
    spec = c.get("/api/openapi.json").json()

groups = {}
for path, ops in sorted(spec["paths"].items()):
    for verb, op in ops.items():
        tag = (op.get("tags") or ["other"])[0]
        groups.setdefault(tag, []).append((verb.upper(), path, op.get("summary", "")))

lines = ["# API documentation", "", "Generated from the running application by `tools/gen_docs.py`. Every `/api` route requires authentication (session cookie, bearer JWT, `vck_` API key, or `vco_` OAuth token) unless noted. Writes using a cookie session also require the `X-CSRF-Token` header in the secure configuration.", "",
         "Interactive OpenAPI is served at `/api/docs` and the machine-readable spec at `/api/openapi.json`.", ""]
for tag, rows in sorted(groups.items()):
    lines += [f"## {tag}", "", "| Method | Path |", "|---|---|"] + [f"| {v} | `{p}` |" for v, p, _ in rows] + [""]
lines += ["## GraphQL", "", "`POST /graphql` with `{ \"query\": \"...\" }`. Queries: `me`, `customers`, `customer(id)`, `users`, `organization`. Mutations: `updateCustomer`, `deleteCustomer`, `setUserRole`. Depth, cost, alias and batching limits and introspection are enforced in the secure configuration.", ""]
open(os.path.join(docs, "API_DOCUMENTATION.md"), "w").write("\n".join(lines))

lines = ["# Database schema", "", "Generated from the SQLAlchemy models. Migrations live in `backend/alembic/versions`.", ""]
for t in Base.metadata.sorted_tables:
    lines += [f"## `{t.name}`", "", "| Column | Type | Constraints |", "|---|---|---|"]
    for col in t.columns:
        cons = []
        if col.primary_key: cons.append("PK")
        if not col.nullable and not col.primary_key: cons.append("NOT NULL")
        if col.unique: cons.append("UNIQUE")
        for fk in col.foreign_keys: cons.append(f"FK → {fk.column.table.name}.{fk.column.name}")
        lines.append(f"| `{col.name}` | {col.type} | {', '.join(cons)} |")
    lines.append("")
open(os.path.join(docs, "DATABASE_SCHEMA.md"), "w").write("\n".join(lines))

by_toggle = {}
for r in CASES:
    by_toggle.setdefault(r[6], []).append(r[0])
lines = ["# Vulnerable configuration reference", "", "Each toggle below changes one behavior in the vulnerable training configuration. Every toggle is inactive in the secure configuration and can be switched off individually with `VULN_DISABLE=toggle1,toggle2`.", "",
         "| Toggle | Related test cases |", "|---|---|"]
for f in ALL_FLAGS:
    lines.append(f"| `{f}` | {', '.join(by_toggle.get(f, [])) or '—'} |")
open(os.path.join(docs, "_toggles.md"), "w").write("\n".join(lines))

lines = ["| Role | Scope | Permissions |", "|---|---|---|"]
for key, (name, desc, perms, level) in SYSTEM_ROLES.items():
    lines.append(f"| {name} (`{key}`) | {level} | {', '.join(perms)} |")
open(os.path.join(docs, "_roles.md"), "w").write("\n".join(lines))
print(len(spec["paths"]), "paths;", len(Base.metadata.tables), "tables;", len(ALL_FLAGS), "toggles;", len(CASES), "cases")
