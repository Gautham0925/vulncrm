import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, BriefcaseBusiness, Building2, ChevronDown, FileText, FlaskConical, Gauge, KeyRound, LayoutDashboard, LifeBuoy, ListChecks, LogOut, Network, ScrollText, Search, Settings, ShieldCheck, TrendingUp, UserCog, Users, UsersRound, UserRoundPlus } from "lucide-react";
import clsx from "clsx";
import { get, post } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Avatar } from "./ui";
import { title } from "../lib/format";

const NAV = [
  { group: "Workspace", items: [
    { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
    { to: "/customers", label: "Customers", icon: Building2, perm: "customers.read" },
    { to: "/leads", label: "Leads", icon: UserRoundPlus, perm: "leads.read" },
    { to: "/pipeline", label: "Sales pipeline", icon: TrendingUp, perm: "opportunities.read" },
    { to: "/tickets", label: "Support tickets", icon: LifeBuoy, perm: "tickets.read" },
    { to: "/documents", label: "Documents", icon: FileText, perm: "documents.read" },
    { to: "/reports", label: "Reports", icon: Gauge, perm: "reports.read" },
  ] },
  { group: "Organization", items: [
    { to: "/employees", label: "Employees", icon: Users, perm: "employees.read" },
    { to: "/teams", label: "Teams", icon: UsersRound, perm: "employees.read" },
    { to: "/roles", label: "Roles & permissions", icon: UserCog, perm: "roles.manage" },
  ] },
  { group: "Developer", items: [
    { to: "/integrations", label: "API & integrations", icon: Network, perm: "integrations.manage" },
    { to: "/oauth-apps", label: "OAuth applications", icon: KeyRound, perm: "oauth.manage" },
  ] },
  { group: "Administration", items: [
    { to: "/sso", label: "Single sign-on", icon: ShieldCheck, perm: "sso.manage" },
    { to: "/audit", label: "Audit logs", icon: ScrollText, perm: "audit.read" },
    { to: "/admin", label: "Organization settings", icon: Settings, perm: "org.manage" },
    { to: "/platform", label: "Platform", icon: BriefcaseBusiness, perm: "platform.manage" },
    { to: "/test-library", label: "Security test library", icon: FlaskConical, perm: "testlib.read" },
  ] },
];

function GlobalSearch() {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const nav = useNavigate();
  const ref = useRef<HTMLDivElement>(null);
  const { data } = useQuery({ queryKey: ["search", q], queryFn: () => get("/api/search", { q }), enabled: q.length >= 2 });
  useEffect(() => {
    const h = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);
  const groups: [string, string, any[]][] = data ? [["Customers", "/customers", data.customers], ["Leads", "/leads", data.leads], ["Deals", "/pipeline/deal", data.opportunities], ["Tickets", "/tickets", data.tickets]] : [];
  return (
    <div className="relative w-full max-w-md" ref={ref}>
      <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-ink-400" />
      <input className="input pl-9" placeholder="Search customers, leads, deals, tickets" value={q} onChange={(e) => { setQ(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)} aria-label="Global search" />
      {open && q.length >= 2 && (
        <div className="card absolute z-40 mt-1 max-h-96 w-full overflow-y-auto p-1.5 shadow-lg">
          {groups.every(([, , r]) => !r?.length) && <p className="px-3 py-3 text-sm text-ink-500">No results</p>}
          {groups.map(([label, base, rows]) => rows?.length ? (
            <div key={label}>
              <p className="px-3 pb-1 pt-2 text-xs font-semibold uppercase tracking-wide text-ink-400">{label}</p>
              {rows.map((r) => (
                <button key={r.id} className="block w-full rounded-md px-3 py-2 text-left text-sm hover:bg-ink-50" onClick={() => { nav(`${base}/${r.id}`); setOpen(false); setQ(""); }}>
                  <span className="font-medium text-ink-800">{r.name ?? r.subject}</span> <span className="text-ink-500">{r.sub}</span>
                </button>
              ))}
            </div>
          ) : null)}
        </div>
      )}
    </div>
  );
}

function Notifications() {
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();
  const nav = useNavigate();
  const { data } = useQuery({ queryKey: ["notifications"], queryFn: () => get("/api/notifications"), refetchInterval: 60000 });
  const read = async () => { await post("/api/notifications/read", { all: true }); qc.invalidateQueries({ queryKey: ["notifications"] }); };
  return (
    <div className="relative">
      <button className="btn-ghost relative !p-2" onClick={() => setOpen(!open)} aria-label="Notifications">
        <Bell className="h-5 w-5" />
        {data?.unread > 0 && <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-bold text-white">{data.unread}</span>}
      </button>
      {open && (
        <div className="card absolute right-0 z-40 mt-1 w-80 shadow-lg">
          <div className="flex items-center justify-between border-b border-ink-100 px-4 py-2.5"><span className="text-sm font-semibold">Notifications</span><button className="text-xs text-brand-600 hover:underline" onClick={read}>Mark all read</button></div>
          <div className="max-h-80 overflow-y-auto">
            {!data?.items?.length && <p className="px-4 py-6 text-center text-sm text-ink-500">You are all caught up</p>}
            {data?.items?.map((n: any) => (
              <button key={n.id} className={clsx("block w-full border-b border-ink-50 px-4 py-3 text-left hover:bg-ink-50", !n.read && "bg-brand-50/50")} onClick={() => { setOpen(false); if (n.link) nav(n.link); }}>
                <p className="text-sm font-medium text-ink-800">{n.title}</p><p className="text-xs text-ink-500">{n.body}</p>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function UserMenu() {
  const { me, logout, refresh } = useAuth();
  const [open, setOpen] = useState(false);
  const nav = useNavigate();
  const qc = useQueryClient();
  if (!me) return null;
  const switchOrg = async (id: number) => { await post("/api/auth/switch-org", { org_id: id }); qc.clear(); await refresh(); setOpen(false); nav("/"); };
  return (
    <div className="relative">
      <button className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-ink-100" onClick={() => setOpen(!open)} aria-label="Account menu">
        <Avatar name={me.user.name} color={me.user.avatar_color} />
        <span className="hidden text-left sm:block"><span className="block text-sm font-medium leading-tight text-ink-800">{me.user.name}</span><span className="block text-xs leading-tight text-ink-500">{me.role.name}</span></span>
        <ChevronDown className="h-4 w-4 text-ink-400" />
      </button>
      {open && (
        <div className="card absolute right-0 z-40 mt-1 w-64 p-1.5 shadow-lg">
          <p className="px-3 py-2 text-xs text-ink-500">{me.user.email}</p>
          {me.organizations.length > 1 && (
            <div className="border-y border-ink-100 py-1.5">
              <p className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-ink-400">Switch organization</p>
              {me.organizations.map((o) => <button key={o.id} onClick={() => switchOrg(o.id)} className={clsx("block w-full rounded-md px-3 py-1.5 text-left text-sm hover:bg-ink-50", o.id === me.organization.id && "font-semibold text-brand-700")}>{o.name}</button>)}
            </div>
          )}
          <button className="block w-full rounded-md px-3 py-2 text-left text-sm hover:bg-ink-50" onClick={() => { setOpen(false); nav("/profile"); }}>Profile & security</button>
          <button className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50" onClick={async () => { await logout(); nav("/login"); }}><LogOut className="h-4 w-4" /> Sign out</button>
        </div>
      )}
    </div>
  );
}

export default function Layout() {
  const { me, meta, can } = useAuth();
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-ink-200 bg-white md:flex">
        <div className="flex items-center gap-2.5 px-5 py-5">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-white"><ShieldCheck className="h-5 w-5" /></span>
          <div><p className="text-base font-bold leading-tight tracking-tight text-ink-900">VULNCRM</p><p className="text-[11px] leading-tight text-ink-500">{me?.organization.name}</p></div>
        </div>
        <nav className="flex-1 overflow-y-auto px-3 pb-4" aria-label="Main">
          {NAV.map((g) => {
            const items = g.items.filter((i) => !i.perm || can(i.perm));
            if (!items.length) return null;
            return (
              <div key={g.group} className="mb-4">
                <p className="px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-ink-400">{g.group}</p>
                {items.map((i) => (
                  <NavLink key={i.to} to={i.to} end={i.end} className={({ isActive }) => clsx("mb-0.5 flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium", isActive ? "bg-brand-50 text-brand-700" : "text-ink-600 hover:bg-ink-50 hover:text-ink-900")}>
                    <i.icon className="h-4 w-4" /> {i.label}
                  </NavLink>
                ))}
              </div>
            );
          })}
        </nav>
        <p className="border-t border-ink-100 px-5 py-3 text-[11px] text-ink-400">{meta?.tagline}</p>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        {meta?.training_environment && meta.mode === "vulnerable" && (
          <div role="note" className="flex items-center justify-center gap-2 bg-amber-100 px-4 py-1.5 text-xs font-medium text-amber-900"><ListChecks className="h-3.5 w-3.5" /> {meta.banner || "Isolated security training environment — synthetic data only. Do not expose to the internet."}</div>
        )}
        <header className="sticky top-0 z-30 flex items-center justify-between gap-4 border-b border-ink-200 bg-white/90 px-6 py-3 backdrop-blur">
          <GlobalSearch />
          <div className="flex items-center gap-1"><Notifications /><UserMenu /></div>
        </header>
        <main className="mx-auto w-full max-w-[1400px] flex-1 px-6 py-8"><Outlet /></main>
        <footer className="px-6 pb-6 text-center text-xs text-ink-400">{title(meta?.mode)} configuration · VULNCRM</footer>
      </div>
    </div>
  );
}
