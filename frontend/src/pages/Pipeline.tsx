import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Plus } from "lucide-react";
import { get, patch, post } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useAct } from "../lib/hooks";
import { Badge, Card, ErrorBox, Field, Modal, PageHeader, Spinner, Table, Tabs } from "../components/ui";
import { date, dateTime, money, title } from "../lib/format";

const NEXT: Record<string, string> = { prospecting: "qualification", qualification: "proposal", proposal: "negotiation", negotiation: "closed_won" };

function DealForm({ open, onClose, initial }: { open: boolean; onClose: () => void; initial?: any }) {
  const [f, setF] = useState<any>(initial ?? { discount_pct: 0 });
  const { data: cust } = useQuery({ queryKey: ["customers", "pick"], queryFn: () => get("/api/customers", { size: 100 }), enabled: open });
  const m = useAct(() => (initial?.id ? patch(`/api/opportunities/${initial.id}`, f) : post("/api/opportunities", f)), ["pipeline", "opportunity", "opportunities"], onClose);
  return (
    <Modal open={open} onClose={onClose} title={initial ? "Edit deal" : "New deal"} wide>
      <div className="grid gap-4 sm:grid-cols-2">
        {m.error && <div className="sm:col-span-2"><ErrorBox error={{ message: m.error }} /></div>}
        <div className="sm:col-span-2"><Field label="Deal name"><input className="input" value={f.name ?? ""} onChange={(e) => setF({ ...f, name: e.target.value })} aria-label="Deal name" /></Field></div>
        <Field label="Customer"><select className="input" value={f.customer_id ?? ""} onChange={(e) => setF({ ...f, customer_id: Number(e.target.value) })} aria-label="Customer"><option value="">Select customer</option>{cust?.items.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
        <Field label="Expected close"><input className="input" type="date" value={(f.expected_close ?? "").slice(0, 10)} onChange={(e) => setF({ ...f, expected_close: e.target.value })} aria-label="Expected close" /></Field>
        <Field label="Amount (USD)"><input className="input" type="number" value={f.amount ?? ""} onChange={(e) => setF({ ...f, amount: Number(e.target.value) })} aria-label="Amount" /></Field>
        <Field label="Discount %"><input className="input" type="number" value={f.discount_pct ?? 0} onChange={(e) => setF({ ...f, discount_pct: Number(e.target.value) })} aria-label="Discount" /></Field>
        <div className="flex justify-end gap-2 sm:col-span-2"><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={!f.name || !f.customer_id || m.isPending} onClick={() => m.mutate(undefined)}>Save deal</button></div>
      </div>
    </Modal>
  );
}

export function Pipeline() {
  const nav = useNavigate();
  const { can } = useAuth();
  const [tab, setTab] = useState("board");
  const [create, setCreate] = useState(false);
  const { data, isLoading, error } = useQuery({ queryKey: ["pipeline"], queryFn: () => get("/api/opportunities/pipeline") });
  const { data: fc } = useQuery({ queryKey: ["forecast"], queryFn: () => get("/api/opportunities/forecast"), enabled: tab === "forecast" });
  const move = useAct((v: { id: number; stage: string }) => post(`/api/opportunities/${v.id}/stage`, { stage: v.stage }), ["pipeline", "forecast"]);
  if (isLoading) return <Spinner />;
  if (error) return <ErrorBox error={error} />;
  return (
    <>
      <PageHeader title="Sales pipeline" subtitle="Track deals from first conversation to close" actions={can("opportunities.write") && <button className="btn-primary" onClick={() => setCreate(true)}><Plus className="h-4 w-4" /> New deal</button>} />
      <Tabs value={tab} onChange={setTab} tabs={[{ key: "board", label: "Board" }, { key: "forecast", label: "Forecast" }]} />
      {move.error && <div className="mb-4"><ErrorBox error={{ message: move.error }} /></div>}
      {tab === "board" && (
        <div className="flex gap-4 overflow-x-auto pb-3">
          {data.stages.map((s: any) => (
            <div key={s.stage} className="w-72 shrink-0 rounded-xl bg-ink-100/70 p-3" data-testid={`stage-${s.stage}`}>
              <div className="mb-3 flex items-baseline justify-between gap-2 px-1"><h3 className="text-sm font-semibold">{title(s.stage)}</h3><span className="whitespace-nowrap text-xs text-ink-500">{s.count} · {money(s.value, true)}</span></div>
              <div className="space-y-2.5">
                {s.items.map((o: any) => (
                  <div key={o.id} className="card cursor-pointer p-3 hover:border-brand-500" onClick={() => nav(`/pipeline/deal/${o.id}`)}>
                    <p className="text-sm font-semibold text-ink-900">{o.name}</p><p className="text-xs text-ink-500">{o.customer_name}</p>
                    <div className="mt-2 flex items-center justify-between"><span className="text-sm font-medium">{money(o.amount)}</span>{o.approval_status === "pending" && <Badge tone="amber">Approval</Badge>}</div>
                    {can("opportunities.write") && NEXT[s.stage] && <button className="btn-secondary mt-2.5 w-full !py-1 text-xs" onClick={(e) => { e.stopPropagation(); move.mutate({ id: o.id, stage: NEXT[s.stage] }); }}>Move to {title(NEXT[s.stage])}</button>}
                  </div>
                ))}
                {!s.items.length && <p className="px-1 py-4 text-center text-xs text-ink-400">No deals</p>}
              </div>
            </div>
          ))}
        </div>
      )}
      {tab === "forecast" && (!fc ? <Spinner /> : (
        <Card title="Weighted forecast by expected close month">
          <div className="h-72"><ResponsiveContainer><BarChart data={fc.items}><CartesianGrid stroke="#eceff6" vertical={false} /><XAxis dataKey="month" tickLine={false} axisLine={false} fontSize={12} /><YAxis tickLine={false} axisLine={false} fontSize={12} tickFormatter={(v) => money(v, true)} width={60} /><Tooltip formatter={(v: any) => money(v)} /><Legend /><Bar dataKey="pipeline" name="Pipeline" fill="#b6c8f9" radius={[4, 4, 0, 0]} /><Bar dataKey="weighted" name="Weighted" fill="#2449cc" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div>
        </Card>
      ))}
      <DealForm open={create} onClose={() => setCreate(false)} />
    </>
  );
}

export function DealDetail() {
  const { id } = useParams();
  const { can } = useAuth();
  const [edit, setEdit] = useState(false);
  const [note, setNote] = useState("");
  const { data: o, isLoading, error } = useQuery({ queryKey: ["opportunity", id], queryFn: () => get(`/api/opportunities/${id}`) });
  const { data: hist } = useQuery({ queryKey: ["opportunity", id, "history"], queryFn: () => get(`/api/opportunities/${id}/history`) });
  const inv = ["opportunity", "pipeline"];
  const move = useAct((stage: string) => post(`/api/opportunities/${id}/stage`, { stage }), inv);
  const request = useAct(() => post(`/api/opportunities/${id}/request-approval`), inv);
  const decide = useAct((decision: string) => post(`/api/opportunities/${id}/approval`, { decision, note }), inv, () => setNote(""));
  if (isLoading) return <Spinner />;
  if (error) return <ErrorBox error={error} />;
  const closed = o.stage === "closed_won" || o.stage === "closed_lost";
  const err = move.error || request.error || decide.error;
  return (
    <>
      <PageHeader title={o.name} subtitle={`${o.customer_name} · Owner ${o.owner_name ?? "—"}`} actions={can("opportunities.write") && !closed && <button className="btn-secondary" onClick={() => setEdit(true)}>Edit</button>} />
      {err && <div className="mb-4"><ErrorBox error={{ message: err }} /></div>}
      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Deal" className="lg:col-span-2">
          <div className="mb-4 flex gap-2"><Badge value={o.stage} /><Badge value={o.approval_status} /></div>
          <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
            {[["Amount", money(o.amount)], ["Discount", `${o.discount_pct}%`], ["Probability", `${o.probability}%`], ["Expected close", date(o.expected_close)], ["Closed", date(o.closed_at)], ["Created", date(o.created_at)]].map(([k, v]) => <div key={k}><dt className="label">{k}</dt><dd className="text-sm">{v}</dd></div>)}
          </dl>
          {o.requires_approval && <p className="mt-5 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">This deal exceeds the approval threshold. A manager must approve it before it can be closed.</p>}
        </Card>
        <Card title="Actions">
          <div className="space-y-2">
            {can("opportunities.write") && !closed && NEXT[o.stage] && <button className="btn-primary w-full" disabled={move.isPending} onClick={() => move.mutate(NEXT[o.stage])}>Move to {title(NEXT[o.stage])}</button>}
            {can("opportunities.write") && !closed && <button className="btn-secondary w-full" onClick={() => move.mutate("closed_lost")}>Mark as lost</button>}
            {can("opportunities.write") && o.requires_approval && o.approval_status !== "pending" && o.approval_status !== "approved" && <button className="btn-secondary w-full" onClick={() => request.mutate(undefined)}>Request approval</button>}
            {can("opportunities.approve") && o.approval_status === "pending" && (
              <div className="space-y-2 border-t border-ink-100 pt-3"><textarea className="input" placeholder="Decision note" value={note} onChange={(e) => setNote(e.target.value)} aria-label="Decision note" />
                <div className="grid grid-cols-2 gap-2"><button className="btn-primary" onClick={() => decide.mutate("approved")}>Approve</button><button className="btn-danger" onClick={() => decide.mutate("rejected")}>Reject</button></div></div>
            )}
          </div>
        </Card>
      </div>
      <Card title="History" className="mt-6" pad={false}>
        <ul className="divide-y divide-ink-100">{hist?.items.map((a: any) => <li key={a.id} className="px-5 py-3 text-sm"><div className="flex justify-between"><span className="font-medium">{a.subject}</span><span className="text-xs text-ink-400">{dateTime(a.created_at)}</span></div><p className="text-xs text-ink-500">{a.actor_name}{a.body ? ` · ${a.body}` : ""}</p></li>)}</ul>
      </Card>
      {edit && <DealForm open onClose={() => setEdit(false)} initial={o} />}
    </>
  );
}
