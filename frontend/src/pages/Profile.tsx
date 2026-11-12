import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { del, get, patch, post } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useAct } from "../lib/hooks";
import { Badge, Card, ErrorBox, Field, PageHeader, Spinner, Table } from "../components/ui";
import { dateTime } from "../lib/format";

export default function Profile() {
  const { me, refresh } = useAuth();
  const { data: p, isLoading } = useQuery({ queryKey: ["profile"], queryFn: () => get("/api/profile") });
  const { data: sess } = useQuery({ queryKey: ["sessions"], queryFn: () => get("/api/auth/sessions") });
  const [f, setF] = useState<any>(null);
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const save = useAct(() => patch("/api/profile", { name: f.name, title: f.title, phone: f.phone, department: f.department }), ["profile"], () => refresh());
  const mfa = useAct((on: boolean) => patch("/api/profile", { mfa_enabled: on }), ["profile"], () => refresh());
  const change = useAct(() => post("/api/auth/change-password", pw), [], () => setPw({ current_password: "", new_password: "" }));
  const revoke = useAct((id: number) => del(`/api/auth/sessions/${id}`), ["sessions"]);
  if (isLoading || !p) return <Spinner />;
  const v = f ?? p;
  return (
    <>
      <PageHeader title="Profile & security" subtitle={me?.user.email} />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Profile">
          <div className="space-y-4">{save.error && <ErrorBox error={{ message: save.error }} />}{save.isSuccess && <p role="status" className="text-sm text-emerald-700">Profile updated.</p>}
            {[["name", "Name"], ["title", "Title"], ["department", "Department"], ["phone", "Phone"]].map(([k, l]) => <Field key={k} label={l}><input className="input" value={v[k] ?? ""} onChange={(e) => setF({ ...v, [k]: e.target.value })} aria-label={l} /></Field>)}
            <button className="btn-primary" disabled={!f || save.isPending} onClick={() => save.mutate(undefined)}>Save profile</button></div>
        </Card>
        <div className="space-y-6">
          <Card title="Two-step verification"><div className="flex items-center justify-between"><div><p className="text-sm font-medium">Email verification codes</p><p className="text-xs text-ink-500">Require a one-time code at sign-in.</p></div><button className={p.mfa_enabled ? "btn-secondary" : "btn-primary"} onClick={() => mfa.mutate(!p.mfa_enabled)}>{p.mfa_enabled ? "Turn off" : "Turn on"}</button></div></Card>
          <Card title="Change password"><div className="space-y-3">{change.error && <ErrorBox error={{ message: change.error }} />}{change.isSuccess && <p role="status" className="text-sm text-emerald-700">Password changed.</p>}
            <Field label="Current password"><input className="input" type="password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} aria-label="Current password" /></Field>
            <Field label="New password"><input className="input" type="password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} aria-label="New password" /></Field>
            <button className="btn-primary" disabled={!pw.current_password || !pw.new_password} onClick={() => change.mutate(undefined)}>Update password</button></div></Card>
        </div>
      </div>
      <Card title="Active sessions" className="mt-6" pad={false}>
        {revoke.error && <div className="p-4"><ErrorBox error={{ message: revoke.error }} /></div>}
        <Table rows={sess?.items ?? []} cols={[{ key: "ip", header: "IP address" }, { key: "user_agent", header: "Device", render: (r: any) => <span className="line-clamp-1 max-w-xs text-xs">{r.user_agent}</span> }, { key: "method", header: "Method", render: (r: any) => <Badge tone="gray">{r.method ?? "password"}</Badge> }, { key: "created_at", header: "Started", render: (r: any) => dateTime(r.created_at) },
          { key: "x", header: "", render: (r: any) => (r.current ? <Badge tone="green">This device</Badge> : <button className="btn-ghost text-red-600" onClick={() => revoke.mutate(r.id)}>Sign out</button>) }]} />
      </Card>
    </>
  );
}
