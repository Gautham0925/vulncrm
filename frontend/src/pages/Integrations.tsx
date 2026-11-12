import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Copy, KeyRound, Plus, Trash2 } from "lucide-react";
import { del, get, post } from "../lib/api";
import { useAct } from "../lib/hooks";
import { Badge, Card, ErrorBox, Field, Modal, PageHeader, Pager, Spinner, Table, Tabs } from "../components/ui";
import { dateTime, date } from "../lib/format";

function Secret({ value, onClose, label }: { value: string; onClose: () => void; label: string }) {
  return (
    <Modal open onClose={onClose} title={label}>
      <p className="mb-3 text-sm text-ink-600">Copy this value now. For security it will not be shown again.</p>
      <div className="flex items-center gap-2 rounded-lg bg-ink-900 p-3"><code className="flex-1 break-all text-xs text-emerald-300" data-testid="secret-value">{value}</code><button className="btn-ghost !p-1.5 text-white" aria-label="Copy" onClick={() => navigator.clipboard?.writeText(value)}><Copy className="h-4 w-4" /></button></div>
      <div className="mt-4 flex justify-end"><button className="btn-primary" onClick={onClose}>Done</button></div>
    </Modal>
  );
}

export default function Integrations() {
  const [tab, setTab] = useState("clients");
  return (
    <>
      <PageHeader title="API & integrations" subtitle="API clients, keys, webhooks and connectors" />
      <Tabs value={tab} onChange={setTab} tabs={[{ key: "clients", label: "API clients" }, { key: "webhooks", label: "Webhooks" }, { key: "connectors", label: "Connectors" }, { key: "requests", label: "Request history" }]} />
      {tab === "clients" && <Clients />}{tab === "webhooks" && <Webhooks />}{tab === "connectors" && <Connectors />}{tab === "requests" && <Requests />}
    </>
  );
}

function Clients() {
  const { data, isLoading, error } = useQuery({ queryKey: ["clients"], queryFn: () => get("/api/integrations/clients") });
  const [create, setCreate] = useState(false); const [f, setF] = useState<any>({ scopes: [] }); const [sel, setSel] = useState<any>(null); const [secret, setSecret] = useState("");
  const add = useAct(() => post("/api/integrations/clients", f), ["clients"], () => { setCreate(false); setF({ scopes: [] }); });
  const keys = useQuery({ queryKey: ["clients", sel?.id, "keys"], queryFn: () => get(`/api/integrations/clients/${sel.id}/keys`), enabled: !!sel });
  const mk = useAct(() => post(`/api/integrations/clients/${sel.id}/keys`, { expires_days: 90 }), ["clients"], (r: any) => { setSecret(r.key ?? r.secret ?? r.api_key ?? ""); keys.refetch(); });
  const rv = useAct((id: number) => del(`/api/integrations/keys/${id}`), ["clients"], () => keys.refetch());
  const rmc = useAct((id: number) => del(`/api/integrations/clients/${id}`), ["clients"], () => setSel(null));
  if (isLoading) return <Spinner />;
  if (error) return <ErrorBox error={error} />;
  const scopes: string[] = data.available_scopes ?? [];
  return (
    <div className="grid gap-6 lg:grid-cols-5">
      <Card title="Clients" className="lg:col-span-2" pad={false} actions={<button className="btn-secondary" onClick={() => setCreate(true)}><Plus className="h-4 w-4" /> New</button>}>
        <ul className="divide-y divide-ink-100">{data.items.map((c: any) => <li key={c.id}><button className={`w-full px-5 py-3 text-left hover:bg-ink-50 ${sel?.id === c.id ? "bg-brand-50" : ""}`} onClick={() => setSel(c)}><p className="text-sm font-medium">{c.name}</p><p className="text-xs text-ink-500">{(c.scopes ?? []).join(", ") || "No scopes"}</p></button></li>)}{!data.items.length && <li className="px-5 py-6 text-sm text-ink-500">No API clients yet</li>}</ul>
      </Card>
      <Card title={sel ? `${sel.name} keys` : "API keys"} className="lg:col-span-3" pad={false} actions={sel && <div className="flex gap-2"><button className="btn-ghost text-red-600" onClick={() => rmc.mutate(sel.id)}>Delete client</button><button className="btn-primary" onClick={() => mk.mutate(undefined)}><KeyRound className="h-4 w-4" /> Generate key</button></div>}>
        {!sel ? <p className="p-6 text-sm text-ink-500">Select a client to manage its keys.</p> : (
          <>{(mk.error || rv.error) && <div className="p-4"><ErrorBox error={{ message: mk.error || rv.error }} /></div>}
            <Table rows={keys.data?.items ?? []} cols={[{ key: "prefix", header: "Key", render: (r: any) => <code className="text-xs">{r.prefix ?? r.key_prefix}…</code> }, { key: "scopes", header: "Scopes", render: (r: any) => (r.scopes ?? []).join(", ") }, { key: "expires_at", header: "Expires", render: (r: any) => date(r.expires_at) }, { key: "last_used_at", header: "Last used", render: (r: any) => dateTime(r.last_used_at) },
              { key: "x", header: "", render: (r: any) => <button className="btn-ghost !p-1.5" aria-label="Revoke key" onClick={() => rv.mutate(r.id)}><Trash2 className="h-4 w-4" /></button> }]} empty={<p className="p-6 text-sm text-ink-500">No keys yet</p>} /></>
        )}
      </Card>
      <Modal open={create} onClose={() => setCreate(false)} title="New API client">
        <div className="space-y-3">{add.error && <ErrorBox error={{ message: add.error }} />}
          <Field label="Name"><input className="input" value={f.name ?? ""} onChange={(e) => setF({ ...f, name: e.target.value })} aria-label="Client name" /></Field>
          <Field label="Description"><input className="input" value={f.description ?? ""} onChange={(e) => setF({ ...f, description: e.target.value })} aria-label="Description" /></Field>
          <div><p className="label">Scopes</p><div className="grid grid-cols-2 gap-1.5">{scopes.map((s) => <label key={s} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.scopes.includes(s)} onChange={(e) => setF({ ...f, scopes: e.target.checked ? [...f.scopes, s] : f.scopes.filter((x: string) => x !== s) })} />{s}</label>)}</div></div>
          <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setCreate(false)}>Cancel</button><button className="btn-primary" disabled={!f.name} onClick={() => add.mutate(undefined)}>Create client</button></div></div>
      </Modal>
      {secret && <Secret value={secret} label="New API key" onClose={() => setSecret("")} />}
    </div>
  );
}

function Webhooks() {
  const { data, isLoading, error } = useQuery({ queryKey: ["webhooks"], queryFn: () => get("/api/integrations/webhooks") });
  const [url, setUrl] = useState(""); const [open, setOpen] = useState(false); const [result, setResult] = useState<any>(null);
  const add = useAct(() => post("/api/integrations/webhooks", { url }), ["webhooks"], () => { setOpen(false); setUrl(""); });
  const rm = useAct((id: number) => del(`/api/integrations/webhooks/${id}`), ["webhooks"]);
  const test = useAct((id: number) => post(`/api/integrations/webhooks/${id}/test`), [], setResult);
  if (isLoading) return <Spinner />;
  if (error) return <ErrorBox error={error} />;
  return (
    <>
      <Card title="Webhook endpoints" pad={false} actions={<button className="btn-secondary" onClick={() => setOpen(true)}><Plus className="h-4 w-4" /> Add endpoint</button>}>
        {test.error && <div className="p-4"><ErrorBox error={{ message: test.error }} /></div>}
        <Table rows={data.items} cols={[{ key: "url", header: "URL", render: (r: any) => <code className="text-xs">{r.url}</code> }, { key: "events", header: "Events", render: (r: any) => (r.events ?? []).join(", ") }, { key: "active", header: "Status", render: (r: any) => <Badge value={r.active === false ? "inactive" : "active"} /> },
          { key: "x", header: "", render: (r: any) => <div className="flex gap-1"><button className="btn-secondary !py-1 text-xs" onClick={() => test.mutate(r.id)}>Send test</button><button className="btn-ghost !p-1.5" aria-label="Delete webhook" onClick={() => rm.mutate(r.id)}><Trash2 className="h-4 w-4" /></button></div> }]} empty={<p className="p-6 text-sm text-ink-500">No webhooks configured</p>} />
      </Card>
      <Modal open={open} onClose={() => setOpen(false)} title="Add webhook endpoint">
        <div className="space-y-3">{add.error && <ErrorBox error={{ message: add.error }} />}<Field label="Endpoint URL"><input className="input" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/hooks" aria-label="Endpoint URL" /></Field>
          <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button><button className="btn-primary" disabled={!url} onClick={() => add.mutate(undefined)}>Add endpoint</button></div></div>
      </Modal>
      <Modal open={!!result} onClose={() => setResult(null)} title="Delivery result"><pre className="max-h-80 overflow-auto rounded-lg bg-ink-50 p-3 text-xs" data-testid="webhook-result">{JSON.stringify(result, null, 2)}</pre></Modal>
    </>
  );
}

function Connectors() {
  const { data, isLoading, error } = useQuery({ queryKey: ["configs"], queryFn: () => get("/api/integrations/configs") });
  const [action, setAction] = useState("lookup"); const [body, setBody] = useState('{"email": "info@acme.example"}'); const [out, setOut] = useState("");
  const [imp, setImp] = useState(""); const [impOut, setImpOut] = useState<any>(null);
  const run = useAct(() => post(`/api/integrations/connector/${action}`, JSON.parse(body)), [], (r) => setOut(JSON.stringify(r, null, 2)));
  const imp_ = useAct(() => post("/api/integrations/import-url", { url: imp }), [], setImpOut);
  if (isLoading) return <Spinner />;
  if (error) return <ErrorBox error={error} />;
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card title="Configured integrations" pad={false}><Table rows={data.items} cols={[{ key: "name", header: "Name" }, { key: "kind", header: "Type", render: (r: any) => <Badge tone="blue">{r.kind}</Badge> }, { key: "enabled", header: "Status", render: (r: any) => <Badge value={r.enabled ? "active" : "inactive"} /> }]} empty={<p className="p-6 text-sm text-ink-500">No integrations configured</p>} /></Card>
      <Card title="Import data from a URL">
        <p className="mb-3 text-sm text-ink-500">Fetch a JSON or CSV feed from a partner system.</p>
        {imp_.error && <div className="mb-3"><ErrorBox error={{ message: imp_.error }} /></div>}
        <div className="flex gap-2"><input className="input" value={imp} onChange={(e) => setImp(e.target.value)} placeholder="https://partner.example/feed.json" aria-label="Import URL" /><button className="btn-primary" disabled={!imp} onClick={() => imp_.mutate(undefined)}>Fetch</button></div>
        {impOut && <pre className="mt-3 max-h-60 overflow-auto rounded-lg bg-ink-50 p-3 text-xs" data-testid="import-result">{JSON.stringify(impOut, null, 2)}</pre>}
      </Card>
      <Card title="Data sync connector" className="lg:col-span-2">
        <div className="mb-3 flex gap-2">{["lookup", "config", "settings"].map((a) => <button key={a} className={a === action ? "btn-primary" : "btn-secondary"} onClick={() => setAction(a)}>{a}</button>)}</div>
        <textarea className="input min-h-24 font-mono text-xs" value={body} onChange={(e) => setBody(e.target.value)} aria-label="Connector request JSON" />
        {run.error && <div className="mt-3"><ErrorBox error={{ message: run.error }} /></div>}
        <button className="btn-primary mt-3" onClick={() => { try { JSON.parse(body); run.mutate(undefined); } catch { run.setError("Request body must be valid JSON"); } }}>Send request</button>
        {out && <pre className="mt-3 max-h-72 overflow-auto rounded-lg bg-ink-50 p-3 text-xs" data-testid="connector-result">{out}</pre>}
      </Card>
    </div>
  );
}

function Requests() {
  const [page, setPage] = useState(1);
  const { data, isLoading, error } = useQuery({ queryKey: ["requests", page], queryFn: () => get("/api/integrations/requests", { page, size: 20 }) });
  if (isLoading) return <Spinner />;
  if (error) return <ErrorBox error={error} />;
  return <Card pad={false} title="Recent API requests"><Table rows={data.items} cols={[{ key: "method", header: "Method", render: (r: any) => <Badge tone="gray">{r.method}</Badge> }, { key: "path", header: "Path", render: (r: any) => <code className="text-xs">{r.path}</code> }, { key: "status", header: "Status" }, { key: "client", header: "Client", render: (r: any) => r.client_name ?? r.api_client_id ?? "—" }, { key: "created_at", header: "Time", render: (r: any) => dateTime(r.created_at) }]} /><Pager meta={data.meta} onPage={setPage} /></Card>;
}
