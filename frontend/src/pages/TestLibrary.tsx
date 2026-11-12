import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, Plus, Upload } from "lucide-react";
import { del, get, patch, post } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useAct, useDebounced, useList } from "../lib/hooks";
import { Badge, Card, ErrorBox, Field, Modal, PageHeader, Pager, SearchBox, Select, Spinner, Table, Tabs } from "../components/ui";
import { dateTime, title } from "../lib/format";

const SEV: Record<string, string> = { critical: "red", high: "amber", medium: "blue", low: "gray", info: "gray" };
const EMPTY = { code: "", category: "", title: "", description: "", module: "", preconditions: "", required_role: "", objective: "", procedure: "", expected_secure: "", indicators: "", severity: "medium", evidence: "", remediation: "", references: [], auth_required: true, api_type: "rest", technology: "", execution: "manual", vuln_toggle: "" };
const TEXT: [string, string][] = [["description", "Description"], ["preconditions", "Preconditions"], ["objective", "Test objective"], ["procedure", "Manual test procedure"], ["indicators", "Indicators of weakness"], ["expected_secure", "Expected secure behavior"], ["evidence", "Evidence to collect"], ["remediation", "Remediation guidance"]];

function CaseForm({ initial, onClose, facets }: { initial: any; onClose: () => void; facets: any }) {
  const [f, setF] = useState<any>({ ...EMPTY, ...initial, references: (initial?.references ?? []).join("\n") });
  const m = useAct(() => { const body = { ...f, references: String(f.references).split("\n").map((x: string) => x.trim()).filter(Boolean) }; return initial?.id ? patch(`/api/testlib/cases/${initial.id}`, body) : post("/api/testlib/cases", body); }, ["testlib"], onClose);
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  return (
    <Modal open onClose={onClose} title={initial?.id ? `Edit ${initial.code}` : "New test case"} wide>
      <div className="grid gap-4 sm:grid-cols-2">
        {m.error && <div className="sm:col-span-2"><ErrorBox error={{ message: m.error }} /></div>}
        <Field label="Code"><input className="input" value={f.code} onChange={set("code")} aria-label="Code" /></Field>
        <Field label="Severity"><select className="input" value={f.severity} onChange={set("severity")} aria-label="Severity">{facets.severities.map((s: string) => <option key={s}>{s}</option>)}</select></Field>
        <div className="sm:col-span-2"><Field label="Title"><input className="input" value={f.title} onChange={set("title")} aria-label="Title" /></Field></div>
        <Field label="Category"><input className="input" list="cats" value={f.category} onChange={set("category")} aria-label="Category" /></Field>
        <Field label="Application module"><input className="input" value={f.module} onChange={set("module")} aria-label="Application module" /></Field>
        <Field label="Required role"><input className="input" value={f.required_role} onChange={set("required_role")} aria-label="Required role" /></Field>
        <Field label="Technology"><input className="input" value={f.technology} onChange={set("technology")} aria-label="Technology" /></Field>
        {TEXT.map(([k, l]) => <div key={k} className="sm:col-span-2"><Field label={l}><textarea className="input min-h-16" value={f[k] ?? ""} onChange={set(k)} aria-label={l} /></Field></div>)}
        <div className="sm:col-span-2"><Field label="References" hint="One per line"><textarea className="input min-h-14" value={f.references} onChange={set("references")} aria-label="References" /></Field></div>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.auth_required} onChange={set("auth_required")} /> Authentication required</label>
        <datalist id="cats">{facets.categories.map((c: string) => <option key={c} value={c} />)}</datalist>
        <div className="flex justify-end gap-2 sm:col-span-2"><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={!f.code || !f.title || !f.category || m.isPending} onClick={() => m.mutate(undefined)}>Save test case</button></div>
      </div>
    </Modal>
  );
}

function CaseDetail({ id, onClose, canManage, facets, onEdit }: { id: number; onClose: () => void; canManage: boolean; facets: any; onEdit: (c: any) => void }) {
  const [tab, setTab] = useState("detail");
  const { data: c } = useQuery({ queryKey: ["testlib", "case", id], queryFn: () => get(`/api/testlib/cases/${id}`) });
  const { data: v } = useQuery({ queryKey: ["testlib", "versions", id], queryFn: () => get(`/api/testlib/cases/${id}/versions`), enabled: tab === "versions" });
  const restore = useAct((ver: number) => post(`/api/testlib/cases/${id}/restore/${ver}`), ["testlib"]);
  const rm = useAct(() => del(`/api/testlib/cases/${id}`), ["testlib"], onClose);
  return (
    <Modal open onClose={onClose} title={c ? `${c.code} · ${c.title}` : "Loading"} wide>
      {!c ? <Spinner /> : (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-2"><Badge tone={SEV[c.severity]}>{title(c.severity)}</Badge><Badge tone="gray">{c.category}</Badge><Badge tone="gray">{c.api_type}</Badge><Badge tone="gray">{c.technology}</Badge><Badge tone="gray">{c.execution}</Badge><Badge tone="blue">v{c.version}</Badge></div>
          <Tabs value={tab} onChange={setTab} tabs={[{ key: "detail", label: "Test case" }, { key: "versions", label: "Versions" }]} />
          {tab === "detail" && (
            <div className="space-y-4">
              {[["Description", c.description], ["Preconditions", c.preconditions], ["Test objective", c.objective], ["Manual test procedure", c.procedure], ["Indicators of weakness", c.indicators], ["Expected secure behavior", c.expected_secure], ["Evidence to collect", c.evidence], ["Remediation guidance", c.remediation]].map(([k, v]) => v ? <div key={k}><p className="label">{k}</p><p className="whitespace-pre-wrap text-sm text-ink-700">{v}</p></div> : null)}
              <div className="grid gap-4 sm:grid-cols-3"><div><p className="label">Module</p><p className="text-sm">{c.module}</p></div><div><p className="label">Required role</p><p className="text-sm">{c.required_role}</p></div><div><p className="label">Authentication</p><p className="text-sm">{c.auth_required ? "Required" : "Not required"}</p></div></div>
              {c.vuln_toggle && <div><p className="label">Lab configuration toggle</p><code className="rounded bg-ink-100 px-1.5 py-0.5 text-xs">{c.vuln_toggle}</code></div>}
              <div><p className="label">References</p><div className="flex flex-wrap gap-1.5">{(c.references ?? []).map((r: string) => <Badge key={r} tone="gray">{r}</Badge>)}</div></div>
              {canManage && <div className="flex justify-end gap-2 border-t border-ink-100 pt-4"><button className="btn-ghost text-red-600" onClick={() => rm.mutate(undefined)}>Delete</button><button className="btn-primary" onClick={() => onEdit(c)}>Edit</button></div>}
            </div>
          )}
          {tab === "versions" && (!v ? <Spinner /> : <Table rows={v.items} cols={[{ key: "version", header: "Version", render: (r: any) => `v${r.version}` }, { key: "created_at", header: "Saved", render: (r: any) => dateTime(r.created_at) }, { key: "x", header: "", render: (r: any) => canManage && r.version !== c.version && <button className="btn-secondary !py-1 text-xs" onClick={() => restore.mutate(r.version)}>Restore</button> }]} />)}
        </>
      )}
    </Modal>
  );
}

export default function TestLibrary() {
  const { can } = useAuth();
  const canManage = can("testlib.manage");
  const [q, setQ] = useState(""); const [category, setCategory] = useState(""); const [severity, setSeverity] = useState(""); const [module, setModule] = useState(""); const [tech, setTech] = useState(""); const [auth, setAuth] = useState(""); const [page, setPage] = useState(1);
  const [sel, setSel] = useState<number | null>(null); const [edit, setEdit] = useState<any>(null);
  const file = useRef<HTMLInputElement>(null);
  const dq = useDebounced(q);
  const { data: facets } = useQuery({ queryKey: ["testlib", "facets"], queryFn: () => get("/api/testlib/facets") });
  const { data, isLoading, error } = useList("testlib", "/api/testlib/cases", { q: dq, category, severity, module, technology: tech, auth_required: auth, page, size: 20 });
  const imp = useAct(async () => { const text = await file.current!.files![0].text(); return post("/api/testlib/import", JSON.parse(text)); }, ["testlib"]);
  if (!facets) return <Spinner />;
  const reset = (fn: (v: string) => void) => (v: string) => { fn(v); setPage(1); };
  return (
    <>
      <PageHeader title="Security test library" subtitle={`${facets.total} documented test cases for authorized assessments of this application`}
        actions={<><a className="btn-secondary" href="/api/testlib/export"><Download className="h-4 w-4" /> Export</a>{canManage && <><input ref={file} type="file" accept="application/json" className="hidden" aria-label="Import file" onChange={() => file.current?.files?.length && imp.mutate(undefined)} /><button className="btn-secondary" onClick={() => file.current?.click()}><Upload className="h-4 w-4" /> Import</button><button className="btn-primary" onClick={() => setEdit({})}><Plus className="h-4 w-4" /> New case</button></>}</>} />
      {imp.error && <div className="mb-4"><ErrorBox error={{ message: imp.error }} /></div>}
      {imp.isSuccess && <p role="status" className="mb-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">Import complete.</p>}
      <Card pad={false}>
        <div className="flex flex-wrap items-center gap-3 border-b border-ink-100 p-4">
          <SearchBox value={q} onChange={reset(setQ)} placeholder="Search by code or title" />
          <Select value={category} onChange={reset(setCategory)} options={facets.categories} all="All categories" label="Category" />
          <Select value={severity} onChange={reset(setSeverity)} options={facets.severities} all="All severities" label="Severity" />
          <Select value={module} onChange={reset(setModule)} options={facets.modules} all="All modules" label="Module" />
          <Select value={tech} onChange={reset(setTech)} options={facets.technologies} all="All technologies" label="Technology" />
          <Select value={auth} onChange={reset(setAuth)} options={[{ value: "true", label: "Authenticated" }, { value: "false", label: "Unauthenticated" }]} all="Any authentication" label="Authentication" />
        </div>
        {error ? <div className="p-4"><ErrorBox error={error} /></div> : isLoading ? <Spinner /> : (
          <>
            <Table rows={data!.items} onRow={(r) => setSel(r.id)} cols={[{ key: "code", header: "Code", render: (r: any) => <code className="text-xs font-semibold">{r.code}</code> }, { key: "title", header: "Title", render: (r: any) => <span className="font-medium text-ink-900">{r.title}</span> }, { key: "category", header: "Category" }, { key: "module", header: "Module" }, { key: "severity", header: "Severity", render: (r: any) => <Badge tone={SEV[r.severity]}>{title(r.severity)}</Badge> }, { key: "required_role", header: "Role" }]} empty={<p className="p-8 text-center text-sm text-ink-500">No test cases match these filters</p>} />
            <Pager meta={data!.meta} onPage={setPage} />
          </>
        )}
      </Card>
      {sel && !edit && <CaseDetail id={sel} onClose={() => setSel(null)} canManage={canManage} facets={facets} onEdit={setEdit} />}
      {edit && <CaseForm initial={edit} facets={facets} onClose={() => { setEdit(null); }} />}
    </>
  );
}
