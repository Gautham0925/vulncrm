import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { get, patch, post, put } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useAct, useList } from "../lib/hooks";
import { Badge, Card, ErrorBox, Field, Modal, PageHeader, Pager, SearchBox, Select, Spinner, Table } from "../components/ui";
import { date, dateTime, title } from "../lib/format";

export function Sso() {
  const { data, isLoading, error } = useQuery({ queryKey: ["saml"], queryFn: () => get("/api/sso/saml") });
  const { data: sess } = useQuery({ queryKey: ["sso-sessions"], queryFn: () => get("/api/sso/sessions") });
  const [f, setF] = useState<any>(null);
  useEffect(() => { if (data) setF(data); }, [data]);
  const save = useAct(() => put("/api/sso/saml", { enabled: f.enabled, idp_entity_id: f.idp_entity_id, sso_url: f.sso_url, slo_url: f.slo_url, x509_cert: f.x509_cert, jit_provisioning: f.jit_provisioning, default_role_key: f.default_role_key, require_signed_assertions: f.require_signed_assertions }), ["saml"]);
  if (isLoading || !f) return <Spinner />;
  if (error) return <ErrorBox error={error} />;
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  return (
    <>
      <PageHeader title="Single sign-on" subtitle="SAML 2.0 identity provider configuration" actions={<button className="btn-primary" disabled={save.isPending} onClick={() => save.mutate(undefined)}>{save.isPending ? "Saving…" : "Save configuration"}</button>} />
      {save.error && <div className="mb-4"><ErrorBox error={{ message: save.error }} /></div>}
      {save.isSuccess && <p role="status" className="mb-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">Configuration saved.</p>}
      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Identity provider" className="lg:col-span-2">
          <div className="space-y-4">
            <label className="flex items-center gap-2 text-sm font-medium"><input type="checkbox" checked={!!f.enabled} onChange={set("enabled")} /> Enable SAML sign-in</label>
            <Field label="IdP entity ID"><input className="input" value={f.idp_entity_id ?? ""} onChange={set("idp_entity_id")} aria-label="IdP entity ID" /></Field>
            <Field label="SSO URL"><input className="input" value={f.sso_url ?? ""} onChange={set("sso_url")} aria-label="SSO URL" /></Field>
            <Field label="Single logout URL"><input className="input" value={f.slo_url ?? ""} onChange={set("slo_url")} aria-label="Single logout URL" /></Field>
            <Field label="Signing certificate (PEM)"><textarea className="input min-h-32 font-mono text-xs" value={f.x509_cert ?? ""} onChange={set("x509_cert")} aria-label="Signing certificate" /></Field>
            <div className="grid gap-3 sm:grid-cols-2"><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!f.jit_provisioning} onChange={set("jit_provisioning")} /> Provision users on first sign-in</label><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!f.require_signed_assertions} onChange={set("require_signed_assertions")} /> Require signed assertions</label></div>
            <Field label="Default role"><select className="input" value={f.default_role_key ?? "sales_rep"} onChange={set("default_role_key")} aria-label="Default role">{["sales_rep", "support_agent", "auditor", "sales_manager"].map((r) => <option key={r} value={r}>{title(r)}</option>)}</select></Field>
          </div>
        </Card>
        <div className="space-y-6">
          <Card title="Service provider details"><dl className="space-y-3 text-sm">{[["Entity ID", f.sp_entity_id], ["ACS URL", f.acs_url], ["Metadata", f.metadata_url], ["Login URL", f.login_url]].map(([k, v]) => <div key={k}><dt className="label">{k}</dt><dd className="break-all text-ink-700">{v}</dd></div>)}</dl></Card>
          <Card title="Active SSO sessions" pad={false}><ul className="divide-y divide-ink-100">{sess?.items.slice(0, 6).map((s: any) => <li key={s.id} className="px-5 py-3 text-sm"><p>{s.name_id ?? s.user_name}</p><p className="text-xs text-ink-400">{dateTime(s.created_at)} · <Badge value={s.status} /></p></li>)}{!sess?.items.length && <li className="px-5 py-5 text-sm text-ink-500">No SSO sessions</li>}</ul></Card>
        </div>
      </div>
    </>
  );
}

export function Audit() {
  const [action, setAction] = useState(""); const [actor, setActor] = useState(""); const [page, setPage] = useState(1);
  const { data, isLoading, error } = useList("audit", "/api/audit", { action, actor, page, size: 25 });
  return (
    <>
      <PageHeader title="Audit logs" subtitle="Security-relevant events in your organization" actions={<a className="btn-secondary" href="/api/audit/export">Export CSV</a>} />
      <Card pad={false}>
        <div className="flex flex-wrap items-center gap-3 border-b border-ink-100 p-4"><SearchBox value={actor} onChange={(v) => { setActor(v); setPage(1); }} placeholder="Filter by actor" /><Select value={action} onChange={(v) => { setAction(v); setPage(1); }} options={["auth", "customer", "opportunity", "employee", "document", "report", "integration", "sso", "role"]} all="All categories" /></div>
        {error ? <div className="p-4"><ErrorBox error={error} /></div> : isLoading ? <Spinner /> : (
          <>
            <Table rows={data!.items} cols={[{ key: "created_at", header: "Time", render: (r: any) => dateTime(r.created_at) }, { key: "actor_label", header: "Actor" }, { key: "action", header: "Action", render: (r: any) => <code className="text-xs">{r.action}</code> }, { key: "resource_type", header: "Resource", render: (r: any) => `${r.resource_type ?? ""} ${r.resource_id ?? ""}` }, { key: "ip", header: "IP" }, { key: "detail", header: "Details", render: (r: any) => <span className="line-clamp-1 max-w-xs text-xs text-ink-500">{JSON.stringify(r.detail)}</span> }]} />
            <Pager meta={data!.meta} onPage={setPage} />
          </>
        )}
      </Card>
    </>
  );
}

export function OrgSettings() {
  const { can } = useAuth();
  const { data, isLoading, error } = useQuery({ queryKey: ["org"], queryFn: () => get("/api/org") });
  const [f, setF] = useState<any>(null);
  useEffect(() => { if (data) setF({ name: data.name, industry: data.industry ?? "", timezone: data.timezone ?? "", settings: data.settings }); }, [data]);
  const save = useAct(() => patch("/api/org", f), ["org"]);
  if (isLoading || !f) return <Spinner />;
  if (error) return <ErrorBox error={error} />;
  const s = f.settings;
  const setS = (k: string, v: any) => setF({ ...f, settings: { ...s, [k]: v } });
  return (
    <>
      <PageHeader title="Organization settings" subtitle={`${data.name} · ${title(data.plan)} plan`} actions={can("org.manage") && <button className="btn-primary" disabled={save.isPending} onClick={() => save.mutate(undefined)}>Save changes</button>} />
      {save.error && <div className="mb-4"><ErrorBox error={{ message: save.error }} /></div>}
      {save.isSuccess && <p role="status" className="mb-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">Settings saved.</p>}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="General"><div className="space-y-4">
          <Field label="Organization name"><input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} aria-label="Organization name" /></Field>
          <Field label="Industry"><input className="input" value={f.industry} onChange={(e) => setF({ ...f, industry: e.target.value })} aria-label="Industry" /></Field>
          <Field label="Time zone"><input className="input" value={f.timezone} onChange={(e) => setF({ ...f, timezone: e.target.value })} aria-label="Time zone" /></Field>
        </div></Card>
        <Card title="Security policy"><div className="space-y-4">
          <label className="flex items-center gap-2 text-sm font-medium"><input type="checkbox" checked={!!s.mfa_required} onChange={(e) => setS("mfa_required", e.target.checked)} /> Require multi-factor authentication</label>
          <Field label="Session timeout (minutes)"><input className="input" type="number" value={s.session_timeout_minutes} onChange={(e) => setS("session_timeout_minutes", Number(e.target.value))} aria-label="Session timeout" /></Field>
          <Field label="Minimum password length"><input className="input" type="number" value={s.min_password_length} onChange={(e) => setS("min_password_length", Number(e.target.value))} aria-label="Minimum password length" /></Field>
          <Field label="Allowed email domains" hint="Comma separated"><input className="input" value={(s.allowed_email_domains ?? []).join(", ")} onChange={(e) => setS("allowed_email_domains", e.target.value.split(",").map((x: string) => x.trim()).filter(Boolean))} aria-label="Allowed email domains" /></Field>
        </div></Card>
      </div>
    </>
  );
}

export function Platform() {
  const { data, isLoading, error } = useQuery({ queryKey: ["platform-orgs"], queryFn: () => get("/api/platform/orgs") });
  const [open, setOpen] = useState(false); const [f, setF] = useState<any>({ plan: "enterprise" });
  const add = useAct(() => post("/api/platform/orgs", f), ["platform-orgs"], () => setOpen(false));
  if (isLoading) return <Spinner />;
  if (error) return <ErrorBox error={error} />;
  return (
    <>
      <PageHeader title="Platform" subtitle="Organizations on this deployment" actions={<button className="btn-primary" onClick={() => setOpen(true)}><Plus className="h-4 w-4" /> New organization</button>} />
      <Card pad={false}><Table rows={data.items} cols={[{ key: "name", header: "Organization", render: (r: any) => <span className="font-medium text-ink-900">{r.name}</span> }, { key: "slug", header: "Identifier" }, { key: "plan", header: "Plan", render: (r: any) => <Badge tone="blue">{title(r.plan)}</Badge> }, { key: "members", header: "Members", render: (r: any) => r.member_count ?? r.members }, { key: "created_at", header: "Created", render: (r: any) => date(r.created_at) }]} /></Card>
      <Modal open={open} onClose={() => setOpen(false)} title="New organization">
        <div className="space-y-3">{add.error && <ErrorBox error={{ message: add.error }} />}
          {[["name", "Organization name"], ["industry", "Industry"], ["admin_name", "Administrator name"], ["admin_email", "Administrator email"]].map(([k, l]) => <Field key={k} label={l}><input className="input" value={f[k] ?? ""} onChange={(e) => setF({ ...f, [k]: e.target.value })} aria-label={l} /></Field>)}
          <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button><button className="btn-primary" disabled={!f.name || !f.admin_email} onClick={() => add.mutate(undefined)}>Create</button></div></div>
      </Modal>
    </>
  );
}
