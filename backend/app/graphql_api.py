import json
from typing import Optional

import strawberry
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from graphql import parse
from graphql.language import ast
from sqlalchemy.orm import Session
from strawberry.types import Info

from app.db import get_db
from app.deps import Principal, current_principal, rate_limit, scoped, team_member_ids
from app.mode import vuln
from app.models import Customer, Lead, Membership, Opportunity, Organization, Role, Ticket, User, now

router = APIRouter(tags=["graphql"])
MAX_DEPTH, MAX_COST, MAX_ALIASES = 6, 300, 15


def ctx(info: Info):
    return info.context["db"], info.context["p"]


def sensitive_ok(p: Principal, perm: str) -> bool:
    return vuln("gql_field_authz") or p.can(perm)


@strawberry.type
class UserType:
    id: int
    name: str
    email: str
    role: Optional[str]
    title: Optional[str]
    org_id: int
    _m: strawberry.Private[Membership]

    @strawberry.field
    def salary(self, info: Info) -> Optional[float]:
        _, p = ctx(info)
        return self._m.salary if sensitive_ok(p, "employees.manage") else None

    @strawberry.field
    def password_hash(self, info: Info) -> Optional[str]:
        return self._m.user.password_hash if vuln("gql_field_authz") else None

    @strawberry.field
    def internal_notes(self, info: Info) -> Optional[str]:
        _, p = ctx(info)
        return self._m.internal_notes if sensitive_ok(p, "employees.manage") else None

    @strawberry.field
    def customers(self, info: Info, first: int = 20) -> list["CustomerType"]:
        db, p = ctx(info)
        qs = db.query(Customer).filter(Customer.owner_id == self._m.id, Customer.deleted_at.is_(None))
        if not vuln("gql_field_authz"):
            qs = scoped(db, qs, Customer, p)
        return [to_customer(c) for c in qs.limit(first).all()]


@strawberry.type
class OpportunityType:
    id: int
    name: str
    amount: float
    stage: str
    probability: int
    approval_status: str
    customer_id: Optional[int]
    owner_id: Optional[int]


@strawberry.type
class TicketType:
    id: int
    subject: str
    status: str
    priority: str
    customer_id: Optional[int]


@strawberry.type
class CustomerType:
    id: int
    name: str
    email: Optional[str]
    industry: Optional[str]
    status: str
    tier: str
    org_id: int
    owner_id: Optional[int]
    _c: strawberry.Private[Customer]

    @strawberry.field
    def internal_notes(self, info: Info) -> Optional[str]:
        _, p = ctx(info)
        return self._c.internal_notes if sensitive_ok(p, "customers.reassign") else None

    @strawberry.field
    def credit_limit(self, info: Info) -> Optional[float]:
        _, p = ctx(info)
        return self._c.credit_limit if sensitive_ok(p, "customers.reassign") else None

    @strawberry.field
    def owner(self, info: Info) -> Optional[UserType]:
        db, _ = ctx(info)
        m = db.get(Membership, self._c.owner_id) if self._c.owner_id else None
        return to_user(m) if m else None

    @strawberry.field
    def opportunities(self, info: Info) -> list[OpportunityType]:
        db, _ = ctx(info)
        return [OpportunityType(id=o.id, name=o.name, amount=o.amount, stage=o.stage, probability=o.probability, approval_status=o.approval_status, customer_id=o.customer_id, owner_id=o.owner_id)
                for o in db.query(Opportunity).filter(Opportunity.customer_id == self._c.id).all()]

    @strawberry.field
    def tickets(self, info: Info) -> list[TicketType]:
        db, _ = ctx(info)
        return [TicketType(id=t.id, subject=t.subject, status=t.status, priority=t.priority, customer_id=t.customer_id) for t in db.query(Ticket).filter(Ticket.customer_id == self._c.id).all()]


@strawberry.type
class OrganizationType:
    id: int
    name: str
    slug: str
    plan: str


def to_user(m: Membership) -> UserType:
    return UserType(id=m.id, name=m.user.name, email=m.user.email, role=m.role.key, title=m.title, org_id=m.org_id, _m=m)


def to_customer(c: Customer) -> CustomerType:
    return CustomerType(id=c.id, name=c.name, email=c.email, industry=c.industry, status=c.status, tier=c.tier, org_id=c.org_id, owner_id=c.owner_id, _c=c)


@strawberry.input
class CustomerFilter:
    q: Optional[str] = None
    status: Optional[str] = None
    industry: Optional[str] = None


@strawberry.input
class CustomerInput:
    name: Optional[str] = None
    email: Optional[str] = None
    industry: Optional[str] = None
    status: Optional[str] = None
    tier: Optional[str] = None
    owner_id: Optional[int] = None
    credit_limit: Optional[float] = None
    org_id: Optional[int] = None


@strawberry.type
class Query:
    @strawberry.field
    def me(self, info: Info) -> UserType:
        _, p = ctx(info)
        return to_user(p.membership)

    @strawberry.field
    def customers(self, info: Info, filter: Optional[CustomerFilter] = None, page: int = 1, size: int = 20) -> list[CustomerType]:
        db, p = ctx(info)
        if not p.can("customers.read"):
            raise Exception("Forbidden")
        qs = scoped(db, db.query(Customer).filter(Customer.deleted_at.is_(None)), Customer, p)
        if filter:
            if filter.q:
                qs = qs.filter(Customer.name.ilike(f"%{filter.q}%"))
            if filter.status:
                qs = qs.filter(Customer.status == filter.status)
            if filter.industry:
                qs = qs.filter(Customer.industry == filter.industry)
        size = max(1, min(size, 100))
        return [to_customer(c) for c in qs.order_by(Customer.name).offset((page - 1) * size).limit(size).all()]

    @strawberry.field
    def customer(self, info: Info, id: int) -> Optional[CustomerType]:
        db, p = ctx(info)
        if not p.can("customers.read"):
            raise Exception("Forbidden")
        c = db.get(Customer, id) if vuln("bola") else scoped(db, db.query(Customer).filter(Customer.id == id), Customer, p).first()
        return to_customer(c) if c and not c.deleted_at else None

    @strawberry.field
    def opportunities(self, info: Info, stage: Optional[str] = None, first: int = 25) -> list[OpportunityType]:
        db, p = ctx(info)
        if not p.can("opportunities.read"):
            raise Exception("Forbidden")
        qs = scoped(db, db.query(Opportunity), Opportunity, p)
        if stage:
            qs = qs.filter(Opportunity.stage == stage)
        return [OpportunityType(id=o.id, name=o.name, amount=o.amount, stage=o.stage, probability=o.probability, approval_status=o.approval_status, customer_id=o.customer_id, owner_id=o.owner_id) for o in qs.limit(min(first, 100)).all()]

    @strawberry.field
    def users(self, info: Info, org_id: Optional[int] = None) -> list[UserType]:
        db, p = ctx(info)
        if not p.can("employees.read"):
            raise Exception("Forbidden")
        org = org_id if (org_id and vuln("bola")) else p.org_id
        return [to_user(m) for m in db.query(Membership).filter(Membership.org_id == org).all()]

    @strawberry.field
    def user(self, info: Info, id: int) -> Optional[UserType]:
        db, p = ctx(info)
        if not p.can("employees.read"):
            raise Exception("Forbidden")
        m = db.get(Membership, id) if vuln("bola") else db.query(Membership).filter(Membership.id == id, Membership.org_id == p.org_id).first()
        return to_user(m) if m else None

    @strawberry.field
    def organization(self, info: Info, id: Optional[int] = None) -> Optional[OrganizationType]:
        db, p = ctx(info)
        o = db.get(Organization, id if (id and vuln("bola")) else p.org_id)
        return OrganizationType(id=o.id, name=o.name, slug=o.slug, plan=o.plan) if o else None

    @strawberry.field
    def tickets(self, info: Info, status: Optional[str] = None) -> list[TicketType]:
        db, p = ctx(info)
        if not p.can("tickets.read"):
            raise Exception("Forbidden")
        qs = db.query(Ticket).filter(Ticket.org_id == p.org_id)
        if status:
            qs = qs.filter(Ticket.status == status)
        return [TicketType(id=t.id, subject=t.subject, status=t.status, priority=t.priority, customer_id=t.customer_id) for t in qs.limit(50).all()]


@strawberry.type
class Mutation:
    @strawberry.mutation
    def update_customer(self, info: Info, id: int, input: CustomerInput) -> CustomerType:
        db, p = ctx(info)
        if not vuln("gql_mutation_authz") and not p.can("customers.write"):
            raise Exception("Forbidden")
        c = db.get(Customer, id) if vuln("gql_mutation_authz") else scoped(db, db.query(Customer).filter(Customer.id == id), Customer, p).first()
        if not c:
            raise Exception("Not found")
        allowed = {"name", "email", "industry", "status", "tier"}
        if p.can("customers.reassign") or vuln("gql_mutation_authz"):
            allowed |= {"owner_id", "credit_limit"}
        if vuln("gql_mutation_authz"):
            allowed |= {"org_id"}
        for k, v in vars(input).items():
            if v is not None and k in allowed:
                setattr(c, k, v)
        db.commit()
        return to_customer(c)

    @strawberry.mutation
    def delete_customer(self, info: Info, id: int) -> bool:
        db, p = ctx(info)
        if not vuln("gql_mutation_authz") and not p.can("customers.delete"):
            raise Exception("Forbidden")
        c = db.get(Customer, id) if vuln("gql_mutation_authz") else scoped(db, db.query(Customer).filter(Customer.id == id), Customer, p).first()
        if not c:
            raise Exception("Not found")
        c.deleted_at = now()
        db.commit()
        return True

    @strawberry.mutation
    def set_user_role(self, info: Info, membership_id: int, role_key: str) -> UserType:
        db, p = ctx(info)
        if not vuln("gql_mutation_authz") and not p.can("employees.manage"):
            raise Exception("Forbidden")
        m = db.get(Membership, membership_id) if vuln("gql_mutation_authz") else db.query(Membership).filter(Membership.id == membership_id, Membership.org_id == p.org_id).first()
        role = db.query(Role).filter(Role.key == role_key, Role.org_id.is_(None)).first()
        if not m or not role or (role.key == "super_admin" and not p.super_admin and not vuln("gql_mutation_authz")):
            raise Exception("Invalid request")
        m.role_id = role.id
        db.commit()
        return to_user(m)


schema = strawberry.Schema(query=Query, mutation=Mutation)


def analyze(doc, fragments=None):
    frags = {d.name.value: d for d in doc.definitions if isinstance(d, ast.FragmentDefinitionNode)}
    stats = {"depth": 0, "cost": 0, "aliases": 0, "introspection": False}

    def walk(sel_set, depth, seen):
        if sel_set is None:
            return
        for s in sel_set.selections:
            if isinstance(s, ast.FieldNode):
                stats["cost"] += 1
                if s.alias:
                    stats["aliases"] += 1
                if s.name.value.startswith("__") and s.name.value != "__typename":
                    stats["introspection"] = True
                stats["depth"] = max(stats["depth"], depth)
                walk(s.selection_set, depth + 1, seen)
            elif isinstance(s, ast.InlineFragmentNode):
                walk(s.selection_set, depth, seen)
            elif isinstance(s, ast.FragmentSpreadNode):
                f = frags.get(s.name.value)
                if f and s.name.value not in seen:
                    walk(f.selection_set, depth, seen | {s.name.value})

    for d in doc.definitions:
        if isinstance(d, ast.OperationDefinitionNode):
            walk(d.selection_set, 1, set())
    return stats


def run_one(payload: dict, db: Session, p: Principal | None):
    query = payload.get("query") or ""
    try:
        doc = parse(query)
    except Exception as e:
        return {"errors": [{"message": f"Syntax error: {str(e)[:200]}"}]}
    st = analyze(doc)
    if not vuln("gql_introspection") and st["introspection"]:
        return {"errors": [{"message": "GraphQL introspection is disabled"}]}
    if p is None and not (st["introspection"] and vuln("gql_introspection")):
        return {"errors": [{"message": "Authentication required"}]}
    if not vuln("gql_depth"):
        if st["depth"] > MAX_DEPTH:
            return {"errors": [{"message": f"Query depth {st['depth']} exceeds the maximum of {MAX_DEPTH}"}]}
        if st["cost"] > MAX_COST or st["aliases"] > MAX_ALIASES:
            return {"errors": [{"message": "Query is too complex"}]}
    res = schema.execute_sync(query, variable_values=payload.get("variables"), operation_name=payload.get("operationName"), context_value={"db": db, "p": p})
    out = {"data": res.data}
    if res.errors:
        out["errors"] = [{"message": str(e.message) if vuln("verbose_errors") or str(e.message) in ("Forbidden", "Not found", "Invalid request") else "Request failed", "path": e.path} for e in res.errors]
    return out


def optional_principal_dep(request: Request, db: Session = Depends(get_db)):
    try:
        return current_principal(request, db)
    except HTTPException:
        return None


@router.post("/graphql")
async def graphql_endpoint(request: Request, db: Session = Depends(get_db), p: Principal | None = Depends(optional_principal_dep)):
    if not vuln("rate_limit"):
        rate_limit(request, "graphql", 120, 60)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")
    if isinstance(body, list):
        if not vuln("gql_batching"):
            raise HTTPException(400, "Batched queries are not supported")
        return JSONResponse([run_one(b, db, p) for b in body])
    return JSONResponse(run_one(body, db, p))
