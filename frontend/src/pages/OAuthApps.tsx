import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { del, get, post } from "../lib/api";
import { useAct } from "../lib/hooks";
import { Badge, Card, ErrorBox, Field, Modal, PageHeader, Spinner, Table, Tabs } from "../components/ui";
import { dateTime } from "../lib/format";

export default function OAuthApps() {
  const [tab, setTab] = useState("apps"); const [open, setOpen] = useState(false); const [secret, setSecret] = useState<any>(null);
  const [f, setF] = useState<any>({ redirect_uris: "", scopes: ["openid", "profile"], grant_types: ["authorization_code", "refresh_token"], public: false });
  const { data, isLoading, error } = useQuery({ queryKey: ["oauth-clients"], queryFn: () => get("/api/oauth/clients") });
  const { data: toks } = useQuery({ queryKey: ["oauth-tokens"], queryFn: () => get("/api/oauth/tokens"), enabled: tab === "tokens" });
  const add = useAct(() => post("/api/oauth/clients", { ...f, redirect_uris: f.redirect_uris.split(/\s+/).filter(Boolean) }), ["oauth-clients"], (r: any) => { setOpen(false); setSecret(r); });
  const rm = useAct((id: number) => del(`/api/oauth/clients/${id}`), ["oauth-clients"]);
  const rot = useAct((id: number) => post(`/api/oauth/clients/${id}/rotate-secret`), ["oauth-clients"], setSecret);
  const revoke = useAct((id: number) => del(`/api/oauth/tokens/${id}`), ["oauth-tokens"]);
  if (isLoading) return <Spinner />;
  if (error) return <ErrorBox error={error} />;
  const scopes = Object.keys(data.available_scopes ?? {});
  return (
    <>
      <PageHeader title="OAuth applications" subtitle="Register applications that sign in users or call the API" actions={<button className="btn-primary" onClick={() => setOpen(true)}><Plus className="h-4 w-4" /> Register application</button>} />
      <Tabs value={tab} onChange={setTab} tabs={[{ key: "apps", label: "Applications", count: data.items.length }, { key: "tokens", label: "Issued tokens" }]} />
      {(rm.error || rot.error || revoke.error) && <div className="mb-4"><ErrorBox error={{ message: rm.error || rot.error || revoke.error }} /></div>}
      {tab === "apps" && (
        <Card pad={false}><Table rows={data.items} cols={[
          { key: "name", header: "Application", render: (r: any) => <div><p className="font-medium text-ink-900">{r.name}</p><code className="text-xs text-ink-500">{r.client_id}</code></div> },
          { key: "grants", header: "Grants", render: (r: any) => (r.grant_types ?? []).map((g: string) => <Badge key={g} tone="gray">{g}</Badge>) },
          { key: "scopes", header: "Scopes", render: (r: any) => (r.scopes ?? []).join(" ") }, { key: "public", header: "Type", render: (r: any) => <Badge tone={r.public ? "purple" : "blue"}>{r.public ? "Public" : "Confidential"}</Badge> },
          { key: "x", header: "", render: (r: any) => <div className="flex gap-1">{!r.public && <button className="btn-secondary !py-1 text-xs" onClick={() => rot.mutate(r.id)}>Rotate secret</button>}<button className="btn-ghost !p-1.5" aria-label="Delete application" onClick={() => rm.mutate(r.id)}><Trash2 className="h-4 w-4" /></button></div> },
        ]} empty={<p className="p-6 text-sm text-ink-500">No applications registered</p>} /></Card>
      )}
      {tab === "tokens" && <Card pad={false}><Table rows={toks?.items ?? []} cols={[{ key: "client", header: "Application", render: (r: any) => r.client_name ?? r.client_id }, { key: "user", header: "User", render: (r: any) => r.user_name ?? "Service" }, { key: "scope", header: "Scope" }, { key: "expires_at", header: "Expires", render: (r: any) => dateTime(r.expires_at) }, { key: "x", header: "", render: (r: any) => <button className="btn-ghost text-red-600" onClick={() => revoke.mutate(r.id)}>Revoke</button> }]} empty={<p className="p-6 text-sm text-ink-500">No active tokens</p>} /></Card>}
      <Modal open={open} onClose={() => setOpen(false)} title="Register application" wide>
        <div className="space-y-3">{add.error && <ErrorBox error={{ message: add.error }} />}
          <Field label="Name"><input className="input" value={f.name ?? ""} onChange={(e) => setF({ ...f, name: e.target.value })} aria-label="Application name" /></Field>
          <Field label="Redirect URIs" hint="One per line"><textarea className="input min-h-20" value={f.redirect_uris} onChange={(e) => setF({ ...f, redirect_uris: e.target.value })} aria-label="Redirect URIs" /></Field>
          <div><p className="label">Grant types</p><div className="flex flex-wrap gap-4">{["authorization_code", "refresh_token", "client_credentials"].map((g) => <label key={g} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.grant_types.includes(g)} onChange={(e) => setF({ ...f, grant_types: e.target.checked ? [...f.grant_types, g] : f.grant_types.filter((x: string) => x !== g) })} />{g}</label>)}</div></div>
          <div><p className="label">Scopes</p><div className="grid grid-cols-2 gap-1.5 sm:grid-cols-3">{scopes.map((s) => <label key={s} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.scopes.includes(s)} onChange={(e) => setF({ ...f, scopes: e.target.checked ? [...f.scopes, s] : f.scopes.filter((x: string) => x !== s) })} />{s}</label>)}</div></div>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.public} onChange={(e) => setF({ ...f, public: e.target.checked })} /> Public client (no secret, PKCE required)</label>
          <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button><button className="btn-primary" disabled={!f.name} onClick={() => add.mutate(undefined)}>Register</button></div></div>
      </Modal>
      <Modal open={!!secret} onClose={() => setSecret(null)} title="Application credentials">
        <p className="mb-3 text-sm text-ink-600">Store the client secret securely. It is shown only once.</p>
        <dl className="space-y-2 text-sm"><div><dt className="label">Client ID</dt><dd><code>{secret?.client_id}</code></dd></div>{secret?.client_secret && <div><dt className="label">Client secret</dt><dd><code data-testid="client-secret">{secret.client_secret}</code></dd></div>}</dl>
        <div className="mt-4 flex justify-end"><button className="btn-primary" onClick={() => setSecret(null)}>Done</button></div>
      </Modal>
    </>
  );
}
