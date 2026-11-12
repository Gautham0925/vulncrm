import { useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Download, FileText, Upload } from "lucide-react";
import { api, del, get, patch, post, put } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useAct, useDebounced, useList } from "../lib/hooks";
import { Badge, Card, Confirm, ErrorBox, Field, Modal, PageHeader, Pager, SearchBox, Select, Spinner, Table } from "../components/ui";
import { bytes, date, dateTime } from "../lib/format";

export function DocumentList() {
  const { can } = useAuth();
  const nav = useNavigate();
  const [q, setQ] = useState(""); const [kind, setKind] = useState(""); const [page, setPage] = useState(1); const [up, setUp] = useState(false);
  const [name, setName] = useState(""); const [dkind, setDkind] = useState("general"); const [vis, setVis] = useState("private"); const [cid, setCid] = useState("");
  const file = useRef<HTMLInputElement>(null);
  const dq = useDebounced(q);
  const { data, isLoading, error } = useList("documents", "/api/documents", { q: dq, kind, page, size: 15 });
  const { data: cust } = useQuery({ queryKey: ["customers", "pick"], queryFn: () => get("/api/customers", { size: 100 }), enabled: up });
  const m = useAct(() => { const fd = new FormData(); fd.append("file", file.current!.files![0]); fd.append("name", name); fd.append("kind", dkind); fd.append("visibility", vis); if (cid) fd.append("customer_id", cid); return api("/api/documents", { form: fd }); }, ["documents"], (r: any) => { setUp(false); nav(`/documents/${r.id}`); });
  return (
    <>
      <PageHeader title="Documents" subtitle="Contracts, proposals and customer files" actions={can("documents.write") && <button className="btn-primary" onClick={() => setUp(true)}><Upload className="h-4 w-4" /> Upload document</button>} />
      <Card pad={false}>
        <div className="flex flex-wrap items-center gap-3 border-b border-ink-100 p-4"><SearchBox value={q} onChange={(v) => { setQ(v); setPage(1); }} placeholder="Search documents" /><Select value={kind} onChange={(v) => { setKind(v); setPage(1); }} options={["general", "contract", "proposal", "invoice", "report"]} all="All types" /></div>
        {error ? <div className="p-4"><ErrorBox error={error} /></div> : isLoading ? <Spinner /> : (
          <>
            <Table rows={data!.items} onRow={(r) => nav(`/documents/${r.id}`)} cols={[
              { key: "name", header: "Document", render: (r: any) => <div className="flex items-center gap-3"><FileText className="h-5 w-5 text-ink-400" /><div><p className="font-medium text-ink-900">{r.name}</p><p className="text-xs text-ink-500">{r.original_name} · {bytes(r.size)}</p></div></div> },
              { key: "kind", header: "Type", render: (r: any) => <Badge tone="gray">{r.kind}</Badge> }, { key: "visibility", header: "Visibility", render: (r: any) => <Badge tone={r.visibility === "private" ? "gray" : "blue"}>{r.visibility}</Badge> },
              { key: "owner_name", header: "Owner" }, { key: "current_version", header: "Version", render: (r: any) => `v${r.current_version}` }, { key: "updated_at", header: "Updated", render: (r: any) => date(r.updated_at) },
            ]} />
            <Pager meta={data!.meta} onPage={setPage} />
          </>
        )}
      </Card>
      <Modal open={up} onClose={() => setUp(false)} title="Upload document">
        <div className="space-y-3">{m.error && <ErrorBox error={{ message: m.error }} />}
          <Field label="File" hint="PDF, images, text, CSV and Office documents up to 10 MB"><input ref={file} type="file" className="input" aria-label="File" /></Field>
          <Field label="Display name"><input className="input" value={name} onChange={(e) => setName(e.target.value)} aria-label="Display name" /></Field>
          <div className="grid grid-cols-2 gap-3"><Field label="Type"><select className="input" value={dkind} onChange={(e) => setDkind(e.target.value)} aria-label="Type">{["general", "contract", "proposal", "invoice", "report"].map((k) => <option key={k}>{k}</option>)}</select></Field>
            <Field label="Visibility"><select className="input" value={vis} onChange={(e) => setVis(e.target.value)} aria-label="Visibility">{["private", "team", "organization"].map((k) => <option key={k}>{k}</option>)}</select></Field></div>
          <Field label="Customer"><select className="input" value={cid} onChange={(e) => setCid(e.target.value)} aria-label="Customer"><option value="">None</option>{cust?.items.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
          <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setUp(false)}>Cancel</button><button className="btn-primary" disabled={m.isPending} onClick={() => file.current?.files?.length ? m.mutate(undefined) : m.setError("Choose a file to upload")}>Upload</button></div></div>
      </Modal>
    </>
  );
}

export function DocumentDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { can } = useAuth();
  const [share, setShare] = useState(false); const [confirm, setConfirm] = useState(false); const [target, setTarget] = useState(""); const [level, setLevel] = useState("read");
  const ver = useRef<HTMLInputElement>(null);
  const { data: d, isLoading, error } = useQuery({ queryKey: ["document", id], queryFn: () => get(`/api/documents/${id}`) });
  const { data: emp } = useQuery({ queryKey: ["employees", "share"], queryFn: () => get("/api/employees", { size: 100 }), enabled: share });
  const addShare = useAct(() => post(`/api/documents/${id}/share`, { membership_id: Number(target), level }), ["document"], () => setShare(false));
  const unshare = useAct((mid: number) => del(`/api/documents/${id}/share/${mid}`), ["document"]);
  const newVer = useAct(() => { const fd = new FormData(); fd.append("file", ver.current!.files![0]); return api(`/api/documents/${id}/versions`, { form: fd }); }, ["document", "documents"]);
  const archive = useAct(() => patch(`/api/documents/${id}`, { status: "archived" }), ["document", "documents"]);
  const remove = useAct(() => del(`/api/documents/${id}`), ["documents"], () => nav("/documents"));
  if (isLoading) return <Spinner />;
  if (error) return <ErrorBox error={error} />;
  const canWrite = can("documents.write") && d.access !== "read";
  return (
    <>
      <PageHeader title={d.name} subtitle={`${d.original_name} · ${bytes(d.size)} · v${d.current_version}`}
        actions={<><a className="btn-secondary" href={`/api/documents/${id}/download`}><Download className="h-4 w-4" /> Download</a>{can("documents.share") && <button className="btn-secondary" onClick={() => setShare(true)}>Share</button>}{canWrite && <button className="btn-danger" onClick={() => setConfirm(true)}>Delete</button>}</>} />
      {(newVer.error || unshare.error || archive.error) && <div className="mb-4"><ErrorBox error={{ message: newVer.error || unshare.error || archive.error }} /></div>}
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card title="Preview" pad={false}>{d.content_type?.startsWith("image/") ? <img className="max-h-96 w-full object-contain p-4" src={`/api/documents/${id}/preview`} alt={d.name} /> : d.content_type === "application/pdf" ? <iframe title="Document preview" className="h-[28rem] w-full" src={`/api/documents/${id}/preview`} /> : <p className="p-6 text-sm text-ink-500">Preview is not available for this file type. Use Download to open it.</p>}</Card>
          <Card title="Versions" pad={false} actions={canWrite && <><input ref={ver} type="file" className="hidden" onChange={() => ver.current?.files?.length && newVer.mutate(undefined)} aria-label="New version file" /><button className="btn-secondary" onClick={() => ver.current?.click()}>Upload new version</button></>}>
            <Table rows={d.versions} cols={[{ key: "version", header: "Version", render: (r: any) => `v${r.version}` }, { key: "original_name", header: "File" }, { key: "size", header: "Size", render: (r: any) => bytes(r.size) }, { key: "created_at", header: "Uploaded", render: (r: any) => dateTime(r.created_at) }]} />
          </Card>
        </div>
        <div className="space-y-6">
          <Card title="Details"><dl className="space-y-3 text-sm">{[["Owner", d.owner_name], ["Type", d.kind], ["Visibility", d.visibility], ["Status", d.status], ["Your access", d.access]].map(([k, v]) => <div key={k} className="flex justify-between"><dt className="text-ink-500">{k}</dt><dd className="font-medium">{v}</dd></div>)}</dl>{canWrite && d.status !== "archived" && <button className="btn-secondary mt-4 w-full" onClick={() => archive.mutate(undefined)}>Archive</button>}</Card>
          <Card title="Shared with" pad={false}><ul className="divide-y divide-ink-100">{d.shared_with.map((s: any) => <li key={s.membership_id ?? s.id} className="flex items-center justify-between px-5 py-3 text-sm"><span>{s.name ?? `Member ${s.membership_id}`} <Badge tone="gray">{s.level}</Badge></span>{can("documents.share") && <button className="text-xs text-red-600 hover:underline" onClick={() => unshare.mutate(s.membership_id ?? s.id)}>Remove</button>}</li>)}{!d.shared_with.length && <li className="px-5 py-5 text-sm text-ink-500">Not shared with anyone</li>}</ul></Card>
        </div>
      </div>
      <Modal open={share} onClose={() => setShare(false)} title="Share document">
        <div className="space-y-3">{addShare.error && <ErrorBox error={{ message: addShare.error }} />}
          <Field label="Person"><select className="input" value={target} onChange={(e) => setTarget(e.target.value)} aria-label="Person"><option value="">Select a person</option>{emp?.items.map((x: any) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>
          <Field label="Access"><select className="input" value={level} onChange={(e) => setLevel(e.target.value)} aria-label="Access">{["read", "write"].map((x) => <option key={x}>{x}</option>)}</select></Field>
          <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setShare(false)}>Cancel</button><button className="btn-primary" disabled={!target} onClick={() => addShare.mutate(undefined)}>Share</button></div></div>
      </Modal>
      <Confirm open={confirm} danger title="Delete document" body="All versions will be removed." onCancel={() => setConfirm(false)} onConfirm={() => remove.mutate(undefined)} />
    </>
  );
}
