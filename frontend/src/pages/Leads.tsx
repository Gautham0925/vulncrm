import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { get, patch, post, put, del } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useAct, useDebounced, useList } from "../lib/hooks";
import { Badge, Card, Confirm, ErrorBox, Field, Modal, PageHeader, Pager, SearchBox, Select, Spinner, Table } from "../components/ui";
import { date, dateTime, money } from "../lib/format";

const STATUSES = ["new", "contacted", "qualified", "disqualified"];
const SOURCES = ["web", "referral", "event", "partner", "outbound", "other"];

function LeadForm({ open, onClose, initial }: { open: boolean; onClose: () => void; initial?: any }) {
  const [f, setF] = useState<any>(initial ?? { source: "web" });
  const m = useAct(() => (initial?.id ? patch(`/api/leads/${initial.id}`, f) : post("/api/leads", f)), ["leads", "lead"], onClose);
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  return (
    <Modal open={open} onClose={onClose} title={initial ? "Edit lead" : "New lead"} wide>
      <div className="grid gap-4 sm:grid-cols-2">
        {m.error && <div className="sm:col-span-2"><ErrorBox error={{ message: m.error }} /></div>}
        <Field label="Name"><input className="input" value={f.name ?? ""} onChange={set("name")} aria-label="Name" /></Field>
        <Field label="Company"><input className="input" value={f.company ?? ""} onChange={set("company")} aria-label="Company" /></Field>
        <Field label="Email"><input className="input" value={f.email ?? ""} onChange={set("email")} aria-label="Email" /></Field>
        <Field label="Phone"><input className="input" value={f.phone ?? ""} onChange={set("phone")} aria-label="Phone" /></Field>
        <Field label="Source"><select className="input" value={f.source ?? "web"} onChange={set("source")}>{SOURCES.map((s) => <option key={s}>{s}</option>)}</select></Field>
        <Field label="Estimated value"><input className="input" type="number" value={f.estimated_value ?? ""} onChange={(e) => setF({ ...f, estimated_value: e.target.value === "" ? null : Number(e.target.value) })} aria-label="Estimated value" /></Field>
        <div className="sm:col-span-2"><Field label="Notes"><textarea className="input min-h-20" value={f.notes ?? ""} onChange={set("notes")} aria-label="Notes" /></Field></div>
        <div className="flex justify-end gap-2 sm:col-span-2"><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={!f.name || m.isPending} onClick={() => m.mutate(undefined)}>Save lead</button></div>
      </div>
    </Modal>
  );
}

export function LeadList() {
  const { can } = useAuth();
  const nav = useNavigate();
  const [q, setQ] = useState(""); const [status, setStatus] = useState(""); const [source, setSource] = useState(""); const [page, setPage] = useState(1); const [create, setCreate] = useState(false);
  const dq = useDebounced(q);
  const { data, isLoading, error } = useList("leads", "/api/leads", { q: dq, status, source, page, size: 15 });
  return (
    <>
      <PageHeader title="Leads" subtitle="Qualify inbound interest and convert it to customers" actions={can("leads.write") && <button className="btn-primary" onClick={() => setCreate(true)}><Plus className="h-4 w-4" /> New lead</button>} />
      <Card pad={false}>
        <div className="flex flex-wrap items-center gap-3 border-b border-ink-100 p-4">
          <SearchBox value={q} onChange={(v) => { setQ(v); setPage(1); }} placeholder="Search leads" />
          <Select value={status} onChange={(v) => { setStatus(v); setPage(1); }} options={[...STATUSES, "converted"]} all="All statuses" />
          <Select value={source} onChange={(v) => { setSource(v); setPage(1); }} options={SOURCES} all="All sources" />
        </div>
        {error ? <div className="p-4"><ErrorBox error={error} /></div> : isLoading ? <Spinner /> : (
          <>
            <Table rows={data!.items} onRow={(r) => nav(`/leads/${r.id}`)} cols={[
              { key: "name", header: "Lead", render: (r: any) => <div><p className="font-medium text-ink-900">{r.name}</p><p className="text-xs text-ink-500">{r.company}</p></div> },
              { key: "source", header: "Source", render: (r: any) => <Badge tone="gray">{r.source}</Badge> },
              { key: "status", header: "Status", render: (r: any) => <Badge value={r.status} /> },
              { key: "score", header: "Score" },
              { key: "estimated_value", header: "Est. value", render: (r: any) => money(r.estimated_value) },
              { key: "owner_name", header: "Owner" },
              { key: "created_at", header: "Created", render: (r: any) => date(r.created_at) },
            ]} />
            <Pager meta={data!.meta} onPage={setPage} />
          </>
        )}
      </Card>
      <LeadForm open={create} onClose={() => setCreate(false)} />
    </>
  );
}

export function LeadDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { can } = useAuth();
  const [edit, setEdit] = useState(false); const [assign, setAssign] = useState(false); const [confirm, setConfirm] = useState(false);
  const { data: l, isLoading, error } = useQuery({ queryKey: ["lead", id], queryFn: () => get(`/api/leads/${id}`) });
  const { data: hist } = useQuery({ queryKey: ["lead", id, "history"], queryFn: () => get(`/api/leads/${id}/history`) });
  const { data: emp } = useQuery({ queryKey: ["employees", "owners"], queryFn: () => get("/api/employees", { size: 100 }), enabled: assign });
  const setStatus = useAct((status: string) => post(`/api/leads/${id}/status`, { status }), ["lead", "leads"]);
  const convert = useAct(() => post(`/api/leads/${id}/convert`, {}), ["lead", "leads", "customers"], (r: any) => nav(`/customers/${r.customer_id ?? r.customer?.id ?? ""}`));
  const owner = useAct((owner_id: number) => put(`/api/leads/${id}/assign`, { owner_id }), ["lead", "leads"], () => setAssign(false));
  const remove = useAct(() => del(`/api/leads/${id}`), ["leads"], () => nav("/leads"));
  if (isLoading) return <Spinner />;
  if (error) return <ErrorBox error={error} />;
  const converted = l.status === "converted";
  return (
    <>
      <PageHeader title={l.name} subtitle={`${l.company ?? "—"} · Owner ${l.owner_name ?? "unassigned"}`}
        actions={<>
          {can("leads.assign") && <button className="btn-secondary" onClick={() => setAssign(true)}>Assign</button>}
          {can("leads.write") && !converted && <button className="btn-secondary" onClick={() => setEdit(true)}>Edit</button>}
          {can("leads.convert") && !converted && <button className="btn-primary" onClick={() => convert.mutate(undefined)} disabled={convert.isPending}>Convert to customer</button>}
        </>} />
      {(convert.error || setStatus.error) && <div className="mb-4"><ErrorBox error={{ message: convert.error || setStatus.error }} /></div>}
      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Lead details" className="lg:col-span-2">
          <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
            {[["Email", l.email], ["Phone", l.phone], ["Source", l.source], ["Score", l.score], ["Estimated value", money(l.estimated_value)], ["Created", date(l.created_at)]].map(([k, v]) => <div key={k as string}><dt className="label">{k}</dt><dd className="text-sm">{v || "—"}</dd></div>)}
          </dl>
          {l.notes && <div className="mt-5 border-t border-ink-100 pt-4"><p className="label">Notes</p><p className="whitespace-pre-wrap text-sm text-ink-700">{l.notes}</p></div>}
          {converted && <div className="mt-5 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">Converted on {date(l.converted_at)}.</div>}
        </Card>
        <Card title="Qualification">
          <div className="mb-3"><Badge value={l.status} /></div>
          {!converted && can("leads.write") && (
            <div className="space-y-2">{STATUSES.map((s) => <button key={s} className={s === l.status ? "btn-primary w-full" : "btn-secondary w-full"} disabled={setStatus.isPending} onClick={() => setStatus.mutate(s)}>Mark as {s}</button>)}</div>
          )}
        </Card>
      </div>
      <Card title="History" className="mt-6" pad={false}>
        <ul className="divide-y divide-ink-100">{hist?.items.map((a: any) => <li key={a.id} className="flex justify-between px-5 py-3 text-sm"><span>{a.subject} <span className="text-ink-400">· {a.actor_name}</span></span><span className="text-xs text-ink-400">{dateTime(a.created_at)}</span></li>)}
          {!hist?.items.length && <li className="px-5 py-6 text-sm text-ink-500">No history yet</li>}</ul>
      </Card>
      {can("leads.write") && !converted && <div className="mt-6 text-right"><button className="btn-ghost text-red-600" onClick={() => setConfirm(true)}>Delete lead</button></div>}
      {edit && <LeadForm open onClose={() => setEdit(false)} initial={l} />}
      <Confirm open={confirm} danger title="Delete lead" body="This lead will be removed permanently." onCancel={() => setConfirm(false)} onConfirm={() => remove.mutate(undefined)} />
      <Modal open={assign} onClose={() => setAssign(false)} title="Assign lead">
        {owner.error && <ErrorBox error={{ message: owner.error }} />}
        <Field label="Owner"><select className="input" defaultValue={l.owner_id} onChange={(e) => owner.mutate(Number(e.target.value))} aria-label="Owner">{emp?.items.map((e: any) => <option key={e.id} value={e.id}>{e.name} ({e.role_name})</option>)}</select></Field>
      </Modal>
    </>
  );
}
