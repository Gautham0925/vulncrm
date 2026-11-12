import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { del, get, patch, post, put } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useAct, useDebounced, useList } from "../lib/hooks";
import { Avatar, Badge, Card, Confirm, ErrorBox, Field, Modal, PageHeader, Pager, SearchBox, Select, Spinner, Table } from "../components/ui";
import { dateTime, money, title } from "../lib/format";

export function EmployeeList() {
  const { can } = useAuth();
  const nav = useNavigate();
  const [q, setQ] = useState(""); const [role, setRole] = useState(""); const [status, setStatus] = useState(""); const [page, setPage] = useState(1); const [invite, setInvite] = useState(false);
  const [f, setF] = useState<any>({ role_key: "sales_rep" });
  const dq = useDebounced(q);
  const { data, isLoading, error } = useList("employees", "/api/employees", { q: dq, role, status, page, size: 15 });
  const { data: roles } = useQuery({ queryKey: ["roles"], queryFn: () => get("/api/roles") });
  const { data: teams } = useQuery({ queryKey: ["teams"], queryFn: () => get("/api/teams") });
  const m = useAct(() => post("/api/employees", f), ["employees"], () => setInvite(false));
  return (
    <>
      <PageHeader title="Employees" subtitle="People, roles and access in your organization" actions={can("employees.manage") && <button className="btn-primary" onClick={() => setInvite(true)}><Plus className="h-4 w-4" /> Invite employee</button>} />
      <Card pad={false}>
        <div className="flex flex-wrap items-center gap-3 border-b border-ink-100 p-4">
          <SearchBox value={q} onChange={(v) => { setQ(v); setPage(1); }} placeholder="Search people" />
          <Select value={role} onChange={(v) => { setRole(v); setPage(1); }} options={(roles?.items ?? []).map((r: any) => ({ value: r.key, label: r.name }))} all="All roles" />
          <Select value={status} onChange={(v) => { setStatus(v); setPage(1); }} options={["active", "inactive"]} all="All statuses" />
        </div>
        {error ? <div className="p-4"><ErrorBox error={error} /></div> : isLoading ? <Spinner /> : (
          <>
            <Table rows={data!.items} onRow={(r) => nav(`/employees/${r.id}`)} cols={[
              { key: "name", header: "Person", render: (r: any) => <div className="flex items-center gap-3"><Avatar name={r.name} color={r.avatar_color} /><div><p className="font-medium text-ink-900">{r.name}</p><p className="text-xs text-ink-500">{r.email}</p></div></div> },
              { key: "role_name", header: "Role", render: (r: any) => <Badge tone="blue">{r.role_name}</Badge> },
              { key: "title", header: "Title" }, { key: "team_name", header: "Team" },
              { key: "status", header: "Status", render: (r: any) => <Badge value={r.active ? "active" : "inactive"} /> },
              { key: "last_login", header: "Last sign-in", render: (r: any) => dateTime(r.last_login) },
            ]} />
            <Pager meta={data!.meta} onPage={setPage} />
          </>
        )}
      </Card>
      <Modal open={invite} onClose={() => setInvite(false)} title="Invite employee" wide>
        <div className="grid gap-4 sm:grid-cols-2">
          {m.error && <div className="sm:col-span-2"><ErrorBox error={{ message: m.error }} /></div>}
          <Field label="Name"><input className="input" value={f.name ?? ""} onChange={(e) => setF({ ...f, name: e.target.value })} aria-label="Name" /></Field>
          <Field label="Email"><input className="input" value={f.email ?? ""} onChange={(e) => setF({ ...f, email: e.target.value })} aria-label="Email" /></Field>
          <Field label="Role"><select className="input" value={f.role_key} onChange={(e) => setF({ ...f, role_key: e.target.value })} aria-label="Role">{roles?.items.filter((r: any) => r.system && r.key !== "super_admin").map((r: any) => <option key={r.key} value={r.key}>{r.name}</option>)}</select></Field>
          <Field label="Team"><select className="input" value={f.team_id ?? ""} onChange={(e) => setF({ ...f, team_id: e.target.value ? Number(e.target.value) : null })} aria-label="Team"><option value="">No team</option>{teams?.items.map((t: any) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></Field>
          <Field label="Title"><input className="input" value={f.title ?? ""} onChange={(e) => setF({ ...f, title: e.target.value })} aria-label="Title" /></Field>
          <Field label="Department"><input className="input" value={f.department ?? ""} onChange={(e) => setF({ ...f, department: e.target.value })} aria-label="Department" /></Field>
          <div className="flex justify-end gap-2 sm:col-span-2"><button className="btn-secondary" onClick={() => setInvite(false)}>Cancel</button><button className="btn-primary" disabled={!f.name || !f.email || m.isPending} onClick={() => m.mutate(undefined)}>Send invitation</button></div>
        </div>
      </Modal>
    </>
  );
}

export function EmployeeDetail() {
  const { id } = useParams();
  const { can } = useAuth();
  const [role, setRole] = useState(false); const [edit, setEdit] = useState(false);
  const [f, setF] = useState<any>({});
  const { data: e, isLoading, error } = useQuery({ queryKey: ["employee", id], queryFn: () => get(`/api/employees/${id}`) });
  const { data: act } = useQuery({ queryKey: ["employee", id, "activity"], queryFn: () => get(`/api/employees/${id}/activity`) });
  const { data: roles } = useQuery({ queryKey: ["roles"], queryFn: () => get("/api/roles"), enabled: role });
  const setRoleM = useAct((role_id: number) => put(`/api/employees/${id}/role`, { role_id }), ["employee", "employees"], () => setRole(false));
  const toggle = useAct((on: boolean) => post(`/api/employees/${id}/${on ? "activate" : "deactivate"}`), ["employee", "employees"]);
  const save = useAct(() => patch(`/api/employees/${id}`, f), ["employee", "employees"], () => setEdit(false));
  if (isLoading) return <Spinner />;
  if (error) return <ErrorBox error={error} />;
  return (
    <>
      <PageHeader title={e.name} subtitle={`${e.title ?? "—"} · ${e.email}`}
        actions={can("employees.manage") && <>
          <button className="btn-secondary" onClick={() => { setF({ name: e.name, title: e.title, department: e.department, phone: e.phone }); setEdit(true); }}>Edit</button>
          <button className="btn-secondary" onClick={() => setRole(true)}>Change role</button>
          <button className={e.active ? "btn-danger" : "btn-primary"} onClick={() => toggle.mutate(!e.active)}>{e.active ? "Deactivate" : "Activate"}</button>
        </>} />
      {(toggle.error || setRoleM.error) && <div className="mb-4"><ErrorBox error={{ message: toggle.error || setRoleM.error }} /></div>}
      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Profile" className="lg:col-span-2">
          <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
            {[["Role", e.role_name], ["Team", e.team_name], ["Department", e.department], ["Phone", e.phone], ["Status", title(e.active ? "active" : "inactive")], ["Last sign-in", dateTime(e.last_login)]].map(([k, v]) => <div key={k as string}><dt className="label">{k}</dt><dd className="text-sm">{v || "—"}</dd></div>)}
            {e.salary != null && <div><dt className="label">Compensation</dt><dd className="text-sm">{money(e.salary)}</dd></div>}
          </dl>
          {e.internal_notes && <div className="mt-5 border-t border-ink-100 pt-4"><p className="label">HR notes</p><p className="text-sm text-ink-700">{e.internal_notes}</p></div>}
        </Card>
        <Card title="Recent activity" pad={false}><ul className="divide-y divide-ink-100">{act?.items.map((a: any) => <li key={a.id} className="px-5 py-3 text-sm"><p>{a.subject}</p><p className="text-xs text-ink-400">{dateTime(a.created_at)}</p></li>)}{!act?.items.length && <li className="px-5 py-6 text-sm text-ink-500">No recent activity</li>}</ul></Card>
      </div>
      <Modal open={role} onClose={() => setRole(false)} title="Change role"><Field label="Role"><select className="input" defaultValue={e.role_id} onChange={(ev) => setRoleM.mutate(Number(ev.target.value))} aria-label="Role">{roles?.items.map((r: any) => <option key={r.id} value={r.id}>{r.name}</option>)}</select></Field></Modal>
      <Modal open={edit} onClose={() => setEdit(false)} title="Edit employee">
        <div className="space-y-3">{save.error && <ErrorBox error={{ message: save.error }} />}
          {["name", "title", "department", "phone"].map((k) => <Field key={k} label={k}><input className="input" value={f[k] ?? ""} onChange={(ev) => setF({ ...f, [k]: ev.target.value })} aria-label={k} /></Field>)}
          <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setEdit(false)}>Cancel</button><button className="btn-primary" onClick={() => save.mutate(undefined)}>Save</button></div></div>
      </Modal>
    </>
  );
}

export function TeamList() {
  const { can } = useAuth();
  const [open, setOpen] = useState(false); const [f, setF] = useState<any>({}); const [del_, setDel] = useState<any>(null);
  const { data, isLoading, error } = useQuery({ queryKey: ["teams"], queryFn: () => get("/api/teams") });
  const { data: emp } = useQuery({ queryKey: ["employees", "mgr"], queryFn: () => get("/api/employees", { size: 100 }), enabled: open });
  const m = useAct(() => post("/api/teams", f), ["teams"], () => setOpen(false));
  const rm = useAct((id: number) => del(`/api/teams/${id}`), ["teams"], () => setDel(null));
  return (
    <>
      <PageHeader title="Teams" subtitle="Group employees for reporting and visibility" actions={can("teams.manage") && <button className="btn-primary" onClick={() => { setF({}); setOpen(true); }}><Plus className="h-4 w-4" /> New team</button>} />
      {error ? <ErrorBox error={error} /> : isLoading ? <Spinner /> : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.items.map((t: any) => (
            <Card key={t.id}><div className="flex items-start justify-between"><div><h3 className="font-semibold">{t.name}</h3><p className="text-sm text-ink-500">{t.department ?? "—"}</p></div><Badge tone="blue">{t.member_count} {t.member_count === 1 ? "member" : "members"}</Badge></div>
              <p className="mt-3 text-sm text-ink-600">{t.description || "No description"}</p><p className="mt-3 text-xs text-ink-500">Manager: {t.manager_name ?? "Unassigned"}</p>
              {can("teams.manage") && <button className="btn-ghost mt-3 !px-0 text-red-600" onClick={() => setDel(t)}>Delete team</button>}</Card>
          ))}
          {!data.items.length && <p className="text-sm text-ink-500">No teams yet</p>}
        </div>
      )}
      <Modal open={open} onClose={() => setOpen(false)} title="New team">
        <div className="space-y-3">{m.error && <ErrorBox error={{ message: m.error }} />}
          <Field label="Name"><input className="input" value={f.name ?? ""} onChange={(e) => setF({ ...f, name: e.target.value })} aria-label="Team name" /></Field>
          <Field label="Department"><input className="input" value={f.department ?? ""} onChange={(e) => setF({ ...f, department: e.target.value })} aria-label="Department" /></Field>
          <Field label="Manager"><select className="input" value={f.manager_id ?? ""} onChange={(e) => setF({ ...f, manager_id: e.target.value ? Number(e.target.value) : null })} aria-label="Manager"><option value="">None</option>{emp?.items.map((x: any) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>
          <Field label="Description"><textarea className="input" value={f.description ?? ""} onChange={(e) => setF({ ...f, description: e.target.value })} aria-label="Description" /></Field>
          <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button><button className="btn-primary" disabled={!f.name} onClick={() => m.mutate(undefined)}>Create team</button></div></div>
      </Modal>
      <Confirm open={!!del_} danger title="Delete team" body={`Delete ${del_?.name}? Members stay in the organization.`} onCancel={() => setDel(null)} onConfirm={() => rm.mutate(del_.id)} />
    </>
  );
}

export function RoleList() {
  const [sel, setSel] = useState<any>(null); const [create, setCreate] = useState(false); const [name, setName] = useState("");
  const { data: roles, isLoading, error } = useQuery({ queryKey: ["roles"], queryFn: () => get("/api/roles") });
  const { data: perms } = useQuery({ queryKey: ["permissions"], queryFn: () => get("/api/permissions") });
  const [draft, setDraft] = useState<string[] | null>(null);
  const save = useAct(() => patch(`/api/roles/${sel.id}`, { permissions: draft }), ["roles"], () => setDraft(null));
  const add = useAct(() => post("/api/roles", { name, permissions: [] }), ["roles"], () => { setCreate(false); setName(""); });
  const rm = useAct(() => del(`/api/roles/${sel.id}`), ["roles"], () => setSel(null));
  if (isLoading) return <Spinner />;
  if (error) return <ErrorBox error={error} />;
  const catalog: Record<string, string> = perms?.permissions ?? perms?.items ?? {};
  const keys = Array.isArray(catalog) ? (catalog as any[]).map((p) => p.key ?? p) : Object.keys(catalog);
  const current = draft ?? sel?.permissions ?? [];
  const groups = keys.reduce((a: Record<string, string[]>, k: string) => ((a[k.split(".")[0]] ||= []).push(k), a), {});
  return (
    <>
      <PageHeader title="Roles & permissions" subtitle="Define what each role can do" actions={<button className="btn-primary" onClick={() => setCreate(true)}><Plus className="h-4 w-4" /> New role</button>} />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Roles" pad={false}>
          <ul className="divide-y divide-ink-100">{roles.items.map((r: any) => (
            <li key={r.id}><button className={`flex w-full items-center justify-between px-5 py-3 text-left hover:bg-ink-50 ${sel?.id === r.id ? "bg-brand-50" : ""}`} onClick={() => { setSel(r); setDraft(null); }}>
              <div><p className="text-sm font-medium">{r.name}</p><p className="text-xs text-ink-500">{r.member_count} {r.member_count === 1 ? "member" : "members"} · {r.permissions.length} permissions</p></div>{r.system && <Badge tone="gray">System</Badge>}</button></li>
          ))}</ul>
        </Card>
        <Card title={sel ? `${sel.name} permissions` : "Select a role"} className="lg:col-span-2"
          actions={sel && !sel.system && <div className="flex gap-2"><button className="btn-secondary text-red-600" onClick={() => rm.mutate(undefined)}>Delete</button><button className="btn-primary" disabled={!draft || save.isPending} onClick={() => save.mutate(undefined)}>Save changes</button></div>}>
          {!sel ? <p className="text-sm text-ink-500">Choose a role to review its permissions.</p> : (
            <div className="space-y-5">
              {(save.error || rm.error) && <ErrorBox error={{ message: save.error || rm.error }} />}
              {sel.system && <p className="rounded-lg bg-ink-50 p-3 text-sm text-ink-600">System roles are read-only.</p>}
              {Object.entries(groups).map(([g, ks]) => (
                <div key={g}><p className="label">{title(g)}</p><div className="grid gap-2 sm:grid-cols-2">{(ks as string[]).map((k) => (
                  <label key={k} className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-0.5" disabled={sel.system} checked={current.includes(k)} onChange={(e) => setDraft(e.target.checked ? [...current, k] : current.filter((x: string) => x !== k))} /><span>{(catalog as any)[k] ?? k}</span></label>
                ))}</div></div>
              ))}
            </div>
          )}
        </Card>
      </div>
      <Modal open={create} onClose={() => setCreate(false)} title="New role">
        <div className="space-y-3">{add.error && <ErrorBox error={{ message: add.error }} />}<Field label="Role name"><input className="input" value={name} onChange={(e) => setName(e.target.value)} aria-label="Role name" /></Field>
          <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setCreate(false)}>Cancel</button><button className="btn-primary" disabled={!name} onClick={() => add.mutate(undefined)}>Create role</button></div></div>
      </Modal>
    </>
  );
}
