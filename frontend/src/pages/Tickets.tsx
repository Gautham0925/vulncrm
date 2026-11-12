import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { get, patch, post } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useAct, useDebounced, useList } from "../lib/hooks";
import { Badge, Card, ErrorBox, Field, Modal, PageHeader, Pager, SearchBox, Select, Spinner, Table } from "../components/ui";
import { date, dateTime } from "../lib/format";

const STATUSES = ["open", "in_progress", "waiting", "resolved", "closed"];
const PRIORITIES = ["low", "medium", "high", "critical"];

export function TicketList() {
  const { can } = useAuth();
  const nav = useNavigate();
  const [q, setQ] = useState(""); const [status, setStatus] = useState(""); const [priority, setPriority] = useState(""); const [page, setPage] = useState(1); const [create, setCreate] = useState(false);
  const [f, setF] = useState<any>({ priority: "medium" });
  const dq = useDebounced(q);
  const { data, isLoading, error } = useList("tickets", "/api/tickets", { q: dq, status, priority, page, size: 15 });
  const { data: cust } = useQuery({ queryKey: ["customers", "pick"], queryFn: () => get("/api/customers", { size: 100 }), enabled: create });
  const m = useAct(() => post("/api/tickets", f), ["tickets"], (r: any) => { setCreate(false); nav(`/tickets/${r.id}`); });
  return (
    <>
      <PageHeader title="Support tickets" subtitle="Customer issues and escalations" actions={can("tickets.write") && <button className="btn-primary" onClick={() => setCreate(true)}><Plus className="h-4 w-4" /> New ticket</button>} />
      <Card pad={false}>
        <div className="flex flex-wrap items-center gap-3 border-b border-ink-100 p-4">
          <SearchBox value={q} onChange={(v) => { setQ(v); setPage(1); }} placeholder="Search tickets" />
          <Select value={status} onChange={(v) => { setStatus(v); setPage(1); }} options={STATUSES} all="All statuses" />
          <Select value={priority} onChange={(v) => { setPriority(v); setPage(1); }} options={PRIORITIES} all="All priorities" />
        </div>
        {error ? <div className="p-4"><ErrorBox error={error} /></div> : isLoading ? <Spinner /> : (
          <>
            <Table rows={data!.items} onRow={(r) => nav(`/tickets/${r.id}`)} cols={[
              { key: "subject", header: "Ticket", render: (r: any) => <div><p className="font-medium text-ink-900">{r.subject}</p><p className="text-xs text-ink-500">{r.customer_name}</p></div> },
              { key: "priority", header: "Priority", render: (r: any) => <Badge value={r.priority} /> },
              { key: "status", header: "Status", render: (r: any) => <span className="flex gap-1.5"><Badge value={r.status} />{r.escalated && <Badge value="escalated" />}</span> },
              { key: "assignee_name", header: "Assignee" },
              { key: "created_at", header: "Opened", render: (r: any) => date(r.created_at) },
            ]} />
            <Pager meta={data!.meta} onPage={setPage} />
          </>
        )}
      </Card>
      <Modal open={create} onClose={() => setCreate(false)} title="New ticket" wide>
        <div className="grid gap-4 sm:grid-cols-2">
          {m.error && <div className="sm:col-span-2"><ErrorBox error={{ message: m.error }} /></div>}
          <div className="sm:col-span-2"><Field label="Subject"><input className="input" value={f.subject ?? ""} onChange={(e) => setF({ ...f, subject: e.target.value })} aria-label="Subject" /></Field></div>
          <Field label="Customer"><select className="input" value={f.customer_id ?? ""} onChange={(e) => setF({ ...f, customer_id: Number(e.target.value) })} aria-label="Customer"><option value="">Select customer</option>{cust?.items.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
          <Field label="Priority"><select className="input" value={f.priority} onChange={(e) => setF({ ...f, priority: e.target.value })} aria-label="Priority">{PRIORITIES.map((p) => <option key={p}>{p}</option>)}</select></Field>
          <div className="sm:col-span-2"><Field label="Description"><textarea className="input min-h-24" value={f.description ?? ""} onChange={(e) => setF({ ...f, description: e.target.value })} aria-label="Description" /></Field></div>
          <div className="flex justify-end gap-2 sm:col-span-2"><button className="btn-secondary" onClick={() => setCreate(false)}>Cancel</button><button className="btn-primary" disabled={!f.subject || !f.customer_id || m.isPending} onClick={() => m.mutate(undefined)}>Create ticket</button></div>
        </div>
      </Modal>
    </>
  );
}

export function TicketDetail() {
  const { id } = useParams();
  const { can } = useAuth();
  const [body, setBody] = useState(""); const [internal, setInternal] = useState(false);
  const { data: t, isLoading, error } = useQuery({ queryKey: ["ticket", id], queryFn: () => get(`/api/tickets/${id}`) });
  const comment = useAct(() => post(`/api/tickets/${id}/comments`, { body, internal }), ["ticket"], () => setBody(""));
  const status = useAct((s: string) => patch(`/api/tickets/${id}`, { status: s }), ["ticket", "tickets"]);
  const escalate = useAct(() => post(`/api/tickets/${id}/escalate`, {}), ["ticket", "tickets"]);
  if (isLoading) return <Spinner />;
  if (error) return <ErrorBox error={error} />;
  const err = comment.error || status.error || escalate.error;
  return (
    <>
      <PageHeader title={t.subject} subtitle={`${t.customer_name} · Opened ${date(t.created_at)} by ${t.created_by_name ?? "—"}`}
        actions={can("tickets.escalate") && !t.escalated && t.status !== "closed" && <button className="btn-secondary" onClick={() => escalate.mutate(undefined)}>Escalate</button>} />
      {err && <div className="mb-4"><ErrorBox error={{ message: err }} /></div>}
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card title="Description"><p className="whitespace-pre-wrap text-sm text-ink-700">{t.description || "No description"}</p></Card>
          <Card title={`Conversation (${t.comments.length})`} pad={false}>
            <ul className="divide-y divide-ink-100">
              {t.comments.map((c: any) => (
                <li key={c.id} className={c.internal ? "bg-amber-50/60 px-5 py-4" : "px-5 py-4"}>
                  <div className="flex items-center justify-between text-sm"><span className="font-medium text-ink-800">{c.author_name} {c.internal && <Badge tone="amber">Internal</Badge>}</span><span className="text-xs text-ink-400">{dateTime(c.created_at)}</span></div>
                  {c.body_html ? <div className="mt-1.5 text-sm text-ink-700" dangerouslySetInnerHTML={{ __html: c.body_html }} /> : <p className="mt-1.5 whitespace-pre-wrap text-sm text-ink-700">{c.body}</p>}
                </li>
              ))}
              {!t.comments.length && <li className="px-5 py-8 text-center text-sm text-ink-500">No replies yet</li>}
            </ul>
            {can("tickets.write") && (
              <div className="border-t border-ink-100 p-5"><textarea className="input min-h-24" placeholder="Write a reply" value={body} onChange={(e) => setBody(e.target.value)} aria-label="Reply" />
                <div className="mt-3 flex items-center justify-between"><label className="flex items-center gap-2 text-sm text-ink-600"><input type="checkbox" checked={internal} onChange={(e) => setInternal(e.target.checked)} /> Internal note</label><button className="btn-primary" disabled={!body.trim() || comment.isPending} onClick={() => comment.mutate(undefined)}>Send</button></div></div>
            )}
          </Card>
        </div>
        <div className="space-y-6">
          <Card title="Properties">
            <dl className="space-y-3 text-sm"><div className="flex justify-between"><dt className="text-ink-500">Priority</dt><dd><Badge value={t.priority} /></dd></div><div className="flex justify-between"><dt className="text-ink-500">Status</dt><dd><Badge value={t.status} /></dd></div>
              <div className="flex justify-between"><dt className="text-ink-500">Assignee</dt><dd>{t.assignee_name ?? "Unassigned"}</dd></div>{t.escalated && <div className="flex justify-between"><dt className="text-ink-500">Escalated</dt><dd><Badge value="escalated" /></dd></div>}</dl>
          </Card>
          {can("tickets.write") && <Card title="Update status"><div className="grid grid-cols-2 gap-2">{STATUSES.map((s) => <button key={s} className={s === t.status ? "btn-primary" : "btn-secondary"} disabled={status.isPending} onClick={() => status.mutate(s)}>{s.replace("_", " ")}</button>)}</div></Card>}
        </div>
      </div>
    </>
  );
}
