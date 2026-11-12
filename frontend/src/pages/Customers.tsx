import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, Trash2 } from "lucide-react";
import { del, get, patch, post, put } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useAct, useDebounced, useList } from "../lib/hooks";
import { Badge, Card, Confirm, ErrorBox, Field, Modal, PageHeader, Pager, SearchBox, Select, Spinner, Table, Tabs } from "../components/ui";
import { date, dateTime, money } from "../lib/format";

const schema = z.object({
  name: z.string().min(2, "Name is required"), email: z.string().email("Enter a valid email").or(z.literal("")), phone: z.string().optional(), industry: z.string().optional(),
  company: z.string().optional(), website: z.string().optional(), address: z.string().optional(), tier: z.string().default("bronze"), status: z.string().default("active"), notes: z.string().optional(),
});
type FormT = z.infer<typeof schema>;

export function CustomerForm({ initial, onDone, onClose, open, heading }: { initial?: any; onDone: () => void; onClose: () => void; open: boolean; heading: string }) {
  const { register, handleSubmit, reset, formState: { errors } } = useForm<FormT>({ resolver: zodResolver(schema) as any, defaultValues: initial ?? { tier: "bronze", status: "active" } });
  useEffect(() => { if (open) reset(initial ?? { tier: "bronze", status: "active" }); }, [open, initial, reset]);
  const m = useAct((v: FormT) => (initial?.id ? patch(`/api/customers/${initial.id}`, v) : post("/api/customers", v)), ["customers", "customer"], () => { onDone(); onClose(); });
  return (
    <Modal open={open} onClose={onClose} title={heading} wide>
      <form onSubmit={handleSubmit((v) => m.mutate(v))} className="grid gap-4 sm:grid-cols-2">
        {m.error && <div className="sm:col-span-2"><ErrorBox error={{ message: m.error }} /></div>}
        <Field label="Name" error={errors.name?.message}><input className="input" {...register("name")} aria-label="Name" /></Field>
        <Field label="Company"><input className="input" {...register("company")} aria-label="Company" /></Field>
        <Field label="Email" error={errors.email?.message}><input className="input" {...register("email")} aria-label="Email" /></Field>
        <Field label="Phone"><input className="input" {...register("phone")} aria-label="Phone" /></Field>
        <Field label="Industry"><input className="input" {...register("industry")} aria-label="Industry" /></Field>
        <Field label="Website"><input className="input" {...register("website")} aria-label="Website" /></Field>
        <Field label="Tier"><select className="input" {...register("tier")}>{["bronze", "silver", "gold", "platinum"].map((t) => <option key={t}>{t}</option>)}</select></Field>
        <Field label="Status"><select className="input" {...register("status")}>{["active", "inactive"].map((t) => <option key={t}>{t}</option>)}</select></Field>
        <div className="sm:col-span-2"><Field label="Address"><input className="input" {...register("address")} aria-label="Address" /></Field></div>
        <div className="sm:col-span-2"><Field label="Notes"><textarea className="input min-h-20" {...register("notes")} aria-label="Notes" /></Field></div>
        <div className="flex justify-end gap-2 sm:col-span-2"><button type="button" className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={m.isPending}>{m.isPending ? "Saving…" : "Save customer"}</button></div>
      </form>
    </Modal>
  );
}

export function CustomerList() {
  const { can, meta } = useAuth();
  const nav = useNavigate();
  const [sp, setSp] = useSearchParams();
  const [q, setQ] = useState(sp.get("q") ?? "");
  const [status, setStatus] = useState("");
  const [tier, setTier] = useState("");
  const [page, setPage] = useState(1);
  const [create, setCreate] = useState(false);
  const dq = useDebounced(q);
  const { data, isLoading, error, refetch } = useList("customers", "/api/customers", { q: dq, status, tier, page, size: 15 });
  return (
    <>
      <PageHeader title="Customers" subtitle="Accounts, contacts and relationship history" actions={can("customers.write") && <button className="btn-primary" onClick={() => setCreate(true)}><Plus className="h-4 w-4" /> New customer</button>} />
      <Card pad={false}>
        <div className="flex flex-wrap items-center gap-3 border-b border-ink-100 p-4">
          <SearchBox value={q} onChange={(v) => { setQ(v); setPage(1); setSp(v ? { q: v } : {}); }} placeholder="Search customers" />
          <Select value={status} onChange={(v) => { setStatus(v); setPage(1); }} options={["active", "inactive"]} all="All statuses" />
          <Select value={tier} onChange={(v) => { setTier(v); setPage(1); }} options={["bronze", "silver", "gold", "platinum"]} all="All tiers" />
        </div>
        {sp.get("q") && (
          <p className="border-b border-ink-100 px-4 py-2 text-sm text-ink-500" data-testid="search-echo">
            Results for{" "}
            {meta?.mode === "vulnerable" && meta.training_environment ? <strong className="text-ink-800" dangerouslySetInnerHTML={{ __html: sp.get("q")! }} /> : <strong className="text-ink-800">{sp.get("q")}</strong>}
          </p>
        )}
        {error ? <div className="p-4"><ErrorBox error={error} /></div> : isLoading ? <Spinner /> : (
          <>
            <Table rows={data!.items} onRow={(r) => nav(`/customers/${r.id}`)} cols={[
              { key: "name", header: "Customer", render: (r: any) => <div><p className="font-medium text-ink-900">{r.name}</p><p className="text-xs text-ink-500">{r.email}</p></div> },
              { key: "industry", header: "Industry" },
              { key: "tier", header: "Tier", render: (r: any) => <Badge value={r.tier} /> },
              { key: "status", header: "Status", render: (r: any) => <Badge value={r.status} /> },
              { key: "owner_name", header: "Owner" },
              { key: "updated_at", header: "Updated", render: (r: any) => date(r.updated_at) },
            ]} />
            <Pager meta={data!.meta} onPage={setPage} />
          </>
        )}
      </Card>
      <CustomerForm open={create} onClose={() => setCreate(false)} onDone={() => refetch()} heading="New customer" />
    </>
  );
}

export function CustomerDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { can, me } = useAuth();
  const [tab, setTab] = useState("overview");
  const [edit, setEdit] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [note, setNote] = useState("");
  const [contact, setContact] = useState(false);
  const [reassign, setReassign] = useState(false);
  const { data: c, isLoading, error } = useQuery({ queryKey: ["customer", id], queryFn: () => get(`/api/customers/${id}`) });
  const { data: acts } = useQuery({ queryKey: ["customer", id, "activities"], queryFn: () => get(`/api/customers/${id}/activities`), enabled: tab === "activity" });
  const { data: emp } = useQuery({ queryKey: ["employees", "owners"], queryFn: () => get("/api/employees", { size: 100 }), enabled: reassign });
  const remove = useAct(() => del(`/api/customers/${id}`), ["customers"], () => nav("/customers"));
  const addNote = useAct((body: string) => post(`/api/customers/${id}/activities`, { kind: "note", subject: "Note", body }), ["customer"], () => setNote(""));
  const owner = useAct((owner_id: number) => put(`/api/customers/${id}/owner`, { owner_id }), ["customer"], () => setReassign(false));
  const addContact = useAct((v: any) => post(`/api/customers/${id}/contacts`, v), ["customer"], () => setContact(false));
  const delContact = useAct((cid: number) => del(`/api/customers/${id}/contacts/${cid}`), ["customer"]);
  const [cf, setCf] = useState({ name: "", email: "", phone: "", title: "" });
  if (isLoading) return <Spinner />;
  if (error) return <ErrorBox error={error} />;
  return (
    <>
      <PageHeader title={c.name} subtitle={`${c.industry ?? "—"} · Owner ${c.owner_name ?? "unassigned"}`}
        actions={<>
          {can("customers.reassign") && <button className="btn-secondary" onClick={() => setReassign(true)}>Reassign</button>}
          {can("customers.write") && <button className="btn-secondary" onClick={() => setEdit(true)}>Edit</button>}
          {can("customers.delete") && <button className="btn-danger" onClick={() => setConfirm(true)}>Delete</button>}
        </>} />
      <div className="mb-4 flex gap-2"><Badge value={c.status} /><Badge value={c.tier} /></div>
      <Tabs value={tab} onChange={setTab} tabs={[{ key: "overview", label: "Overview" }, { key: "contacts", label: "Contacts", count: c.contacts.length }, { key: "deals", label: "Deals", count: c.opportunities?.length }, { key: "tickets", label: "Tickets", count: c.tickets?.length }, { key: "activity", label: "Activity" }]} />
      {tab === "overview" && (
        <div className="grid gap-6 lg:grid-cols-3">
          <Card title="Details" className="lg:col-span-2">
            <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
              {[["Email", c.email], ["Phone", c.phone], ["Company", c.company], ["Website", c.website], ["Address", c.address], ["Created", date(c.created_at)]].map(([k, v]) => <div key={k as string}><dt className="label">{k}</dt><dd className="text-sm text-ink-800">{v || "—"}</dd></div>)}
              {c.credit_limit != null && <div><dt className="label">Credit limit</dt><dd className="text-sm">{money(c.credit_limit)}</dd></div>}
              {c.tax_id && <div><dt className="label">Tax ID</dt><dd className="text-sm">{c.tax_id}</dd></div>}
            </dl>
            {c.notes && <div className="mt-5 border-t border-ink-100 pt-4"><p className="label">Notes</p><p className="whitespace-pre-wrap text-sm text-ink-700">{c.notes}</p></div>}
            {c.internal_notes && <div className="mt-4"><p className="label">Internal notes</p><p className="whitespace-pre-wrap text-sm text-ink-700">{c.internal_notes}</p></div>}
          </Card>
          <Card title="Add a note">
            <textarea className="input min-h-28" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Record a call, meeting or follow-up" aria-label="Note" />
            {addNote.error && <p className="mt-2 text-sm text-red-600">{addNote.error}</p>}
            <button className="btn-primary mt-3 w-full" disabled={!note.trim() || addNote.isPending} onClick={() => addNote.mutate(note)}>Save note</button>
          </Card>
        </div>
      )}
      {tab === "contacts" && (
        <Card title="Contacts" pad={false} actions={can("customers.write") && <button className="btn-secondary" onClick={() => setContact(true)}><Plus className="h-4 w-4" /> Add contact</button>}>
          <Table rows={c.contacts} cols={[{ key: "name", header: "Name", render: (r: any) => <span className="font-medium text-ink-900">{r.name}</span> }, { key: "title", header: "Title" }, { key: "email", header: "Email" }, { key: "phone", header: "Phone" },
            { key: "primary", header: "", render: (r: any) => (r.primary ? <Badge tone="blue">Primary</Badge> : null) },
            { key: "x", header: "", render: (r: any) => can("customers.write") && <button className="btn-ghost !p-1.5" aria-label={`Remove ${r.name}`} onClick={() => delContact.mutate(r.id)}><Trash2 className="h-4 w-4" /></button> }]} empty={<p className="p-6 text-sm text-ink-500">No contacts yet</p>} />
        </Card>
      )}
      {tab === "deals" && <Card pad={false}><Table rows={c.opportunities ?? []} onRow={(r: any) => nav(`/pipeline/deal/${r.id}`)} cols={[{ key: "name", header: "Deal" }, { key: "amount", header: "Amount", render: (r: any) => money(r.amount) }, { key: "stage", header: "Stage", render: (r: any) => <Badge value={r.stage} /> }, { key: "expected_close", header: "Expected close", render: (r: any) => date(r.expected_close) }]} /></Card>}
      {tab === "tickets" && <Card pad={false}><Table rows={c.tickets ?? []} onRow={(r: any) => nav(`/tickets/${r.id}`)} cols={[{ key: "subject", header: "Subject" }, { key: "priority", header: "Priority", render: (r: any) => <Badge value={r.priority} /> }, { key: "status", header: "Status", render: (r: any) => <Badge value={r.status} /> }]} /></Card>}
      {tab === "activity" && (
        <Card pad={false}>{!acts ? <Spinner /> : <ul className="divide-y divide-ink-100">
          {acts.items.map((a: any) => <li key={a.id} className="px-5 py-3.5"><div className="flex justify-between text-sm"><span className="font-medium text-ink-800">{a.subject}</span><span className="text-xs text-ink-400">{dateTime(a.created_at)}</span></div><p className="text-xs text-ink-500">{a.actor_name}</p>
            {(a.body_html ?? a.body) && (a.body_html ? <div className="mt-1.5 text-sm text-ink-700" dangerouslySetInnerHTML={{ __html: a.body_html }} /> : <p className="mt-1.5 whitespace-pre-wrap text-sm text-ink-700">{a.body}</p>)}</li>)}
          {!acts.items.length && <li className="px-5 py-8 text-center text-sm text-ink-500">No activity recorded</li>}</ul>}</Card>
      )}
      <CustomerForm open={edit} initial={c} onClose={() => setEdit(false)} onDone={() => {}} heading="Edit customer" />
      <Confirm open={confirm} danger title="Delete customer" body={`Delete ${c.name} and its related records? This cannot be undone.`} onCancel={() => setConfirm(false)} onConfirm={() => remove.mutate(undefined)} busy={remove.isPending} />
      <Modal open={contact} onClose={() => setContact(false)} title="Add contact">
        <div className="space-y-3">{addContact.error && <ErrorBox error={{ message: addContact.error }} />}
          {(["name", "title", "email", "phone"] as const).map((f) => <Field key={f} label={f}><input className="input" value={cf[f]} onChange={(e) => setCf({ ...cf, [f]: e.target.value })} aria-label={f} /></Field>)}
          <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setContact(false)}>Cancel</button><button className="btn-primary" onClick={() => addContact.mutate(cf)} disabled={!cf.name}>Add contact</button></div></div>
      </Modal>
      <Modal open={reassign} onClose={() => setReassign(false)} title="Reassign customer">
        <div className="space-y-3">{owner.error && <ErrorBox error={{ message: owner.error }} />}
          <Field label="New owner"><select className="input" defaultValue={c.owner_id} onChange={(e) => owner.mutate(Number(e.target.value))} aria-label="New owner">{emp?.items.map((e: any) => <option key={e.id} value={e.id}>{e.name} ({e.role_name})</option>)}</select></Field>
          <p className="text-xs text-ink-500">Signed in as {me?.user.name}. Changes are recorded in the audit log.</p></div>
      </Modal>
    </>
  );
}
