import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { get } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Card, ErrorBox, PageHeader, Select, Spinner, Stat } from "../components/ui";
import { dateTime, money, title } from "../lib/format";

const COLORS = ["#2f5bea", "#5f86f2", "#8aa7f5", "#b6c8f9", "#10b981", "#ef4444"];
const linkFor = (t: string, id: number) => ({ customer: `/customers/${id}`, lead: `/leads/${id}`, opportunity: `/pipeline/deal/${id}`, ticket: `/tickets/${id}` } as any)[t];

const SHORTCUTS = [
  { to: "/tickets", label: "Support tickets", perm: "tickets.read", hint: "Work the support queue" },
  { to: "/customers", label: "Customers", perm: "customers.read", hint: "Find accounts and contacts" },
  { to: "/documents", label: "Documents", perm: "documents.read", hint: "Contracts and customer files" },
  { to: "/leads", label: "Leads", perm: "leads.read", hint: "Qualify inbound interest" },
  { to: "/pipeline", label: "Sales pipeline", perm: "opportunities.read", hint: "Track open deals" },
];

function Home() {
  const { me, can } = useAuth();
  const items = SHORTCUTS.filter((s) => can(s.perm));
  return (
    <>
      <PageHeader title={`Welcome back, ${me?.user.name.split(" ")[0]}`} subtitle={`${me?.organization.name} · ${me?.role.name}`} />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((s) => <Link key={s.to} to={s.to} className="card p-5 hover:border-brand-500"><p className="font-semibold text-ink-900">{s.label}</p><p className="mt-1 text-sm text-ink-500">{s.hint}</p></Link>)}
      </div>
    </>
  );
}

export default function Dashboard() {
  const { can } = useAuth();
  return can("reports.read") ? <Analytics /> : <Home />;
}

function Analytics() {
  const { me } = useAuth();
  const [range, setRange] = useState("30d");
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard", range], queryFn: () => get("/api/dashboard", { range }) });
  if (isLoading) return <Spinner />;
  if (error) return <ErrorBox error={error} />;
  const k = data.kpis;
  return (
    <>
      <PageHeader title={`Welcome back, ${me?.user.name.split(" ")[0]}`} subtitle={`${me?.organization.name} · ${me?.role.name}`}
        actions={<Select value={range} onChange={setRange} label="Date range" options={[{ value: "7d", label: "Last 7 days" }, { value: "30d", label: "Last 30 days" }, { value: "90d", label: "Last 90 days" }, { value: "365d", label: "Last 12 months" }]} />} />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4 xl:grid-cols-5">
        <Stat label="Customers" value={k.customers} hint={`${k.active_accounts} active`} />
        <Stat label="Leads" value={k.leads} />
        <Stat label="Open deals" value={k.open_opportunities} hint={`${money(k.pipeline_value, true)} in pipeline`} />
        <Stat label="Closed deals" value={k.closed_deals} hint={`${money(k.period_revenue, true)} this period`} />
        <Stat label="Open tickets" value={k.open_tickets} hint={k.pending_approvals ? `${k.pending_approvals} approvals pending` : undefined} />
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card title="Revenue by month">
          <div className="h-64"><ResponsiveContainer><LineChart data={data.revenue_by_month}><CartesianGrid stroke="#eceff6" vertical={false} /><XAxis dataKey="month" tickLine={false} axisLine={false} fontSize={12} /><YAxis tickLine={false} axisLine={false} fontSize={12} tickFormatter={(v) => money(v, true)} width={56} /><Tooltip formatter={(v: any) => money(v)} /><Line type="monotone" dataKey="revenue" stroke="#2449cc" strokeWidth={2.5} dot={false} /></LineChart></ResponsiveContainer></div>
        </Card>
        <Card title="Pipeline by stage">
          <div className="h-64"><ResponsiveContainer><BarChart data={data.pipeline_by_stage.map((s: any) => ({ ...s, stage: title(s.stage) }))}><CartesianGrid stroke="#eceff6" vertical={false} /><XAxis dataKey="stage" tickLine={false} axisLine={false} fontSize={12} /><YAxis tickLine={false} axisLine={false} fontSize={12} tickFormatter={(v) => money(v, true)} width={56} /><Tooltip formatter={(v: any) => money(v)} /><Bar dataKey="value" radius={[6, 6, 0, 0]}>{data.pipeline_by_stage.map((_: any, i: number) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}</Bar></BarChart></ResponsiveContainer></div>
        </Card>
        <Card title="Team performance" pad={false}>
          <table className="w-full"><thead className="bg-ink-50"><tr><th className="th">Name</th><th className="th text-right">Won</th><th className="th text-right">Deals</th><th className="th text-right">Open</th></tr></thead>
            <tbody className="divide-y divide-ink-100">{data.team_performance.map((t: any) => <tr key={t.name}><td className="td font-medium">{t.name}</td><td className="td text-right">{money(t.won)}</td><td className="td text-right">{t.deals}</td><td className="td text-right">{t.open}</td></tr>)}
              {!data.team_performance.length && <tr><td className="td text-ink-500" colSpan={4}>No activity in this range</td></tr>}</tbody></table>
        </Card>
        <Card title="Recent activity" pad={false}>
          <ul className="divide-y divide-ink-100">
            {data.recent_activities.slice(0, 8).map((a: any) => (
              <li key={a.id} className="flex items-start justify-between gap-3 px-5 py-3 text-sm">
                <div><Link className="font-medium text-ink-800 hover:text-brand-700" to={linkFor(a.entity_type, a.entity_id) ?? "#"}>{a.subject}</Link><p className="text-xs text-ink-500">{a.actor} · {title(a.entity_type)}</p></div>
                <span className="whitespace-nowrap text-xs text-ink-400">{dateTime(a.created_at)}</span>
              </li>
            ))}
            {!data.recent_activities.length && <li className="px-5 py-6 text-sm text-ink-500">No recent activity</li>}
          </ul>
        </Card>
      </div>
    </>
  );
}
