import { ReactNode, useEffect } from "react";
import { X, Loader2, ChevronLeft, ChevronRight, Search } from "lucide-react";
import clsx from "clsx";
import { title as nice } from "../lib/format";

const TONES: Record<string, string> = {
  green: "bg-emerald-50 text-emerald-700 ring-emerald-200", red: "bg-red-50 text-red-700 ring-red-200", amber: "bg-amber-50 text-amber-800 ring-amber-200",
  blue: "bg-brand-50 text-brand-700 ring-brand-100", gray: "bg-ink-100 text-ink-600 ring-ink-200", purple: "bg-violet-50 text-violet-700 ring-violet-200",
};
const AUTO: Record<string, string> = {
  active: "green", won: "green", closed_won: "green", resolved: "green", approved: "green", qualified: "green", converted: "green", open: "blue", new: "blue", pending: "amber", prospecting: "blue",
  negotiation: "amber", proposal: "purple", qualification: "blue", contacted: "blue", in_progress: "amber", waiting: "amber", escalated: "red", lost: "red", closed_lost: "red", rejected: "red",
  closed: "gray", inactive: "gray", critical: "red", high: "amber", medium: "blue", low: "gray", platinum: "purple", gold: "amber", silver: "gray", bronze: "gray", disqualified: "gray",
  required: "amber", not_required: "gray", draft: "gray", published: "green",
};

export function Badge({ children, tone, value }: { children?: ReactNode; tone?: string; value?: string }) {
  const t = tone ?? AUTO[(value ?? "").toLowerCase()] ?? "gray";
  return <span className={clsx("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset", TONES[t])}>{children ?? nice(value)}</span>;
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-ink-500" role="status">
      <Loader2 className="h-4 w-4 animate-spin" /> {label ?? "Loading"}
    </div>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  return <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{(error as Error)?.message ?? "Something went wrong"}</div>;
}

export function Empty({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="px-6 py-14 text-center">
      <p className="text-sm font-semibold text-ink-700">{title}</p>
      {hint && <p className="mt-1 text-sm text-ink-500">{hint}</p>}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-ink-500">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-2">{actions}</div>
    </div>
  );
}

export function Card({ title, actions, children, className, pad = true }: { title?: string; actions?: ReactNode; children: ReactNode; className?: string; pad?: boolean }) {
  return (
    <section className={clsx("card", className)}>
      {title && (
        <header className="flex items-center justify-between border-b border-ink-100 px-5 py-3.5">
          <h2 className="text-sm font-semibold text-ink-900">{title}</h2>
          {actions}
        </header>
      )}
      <div className={pad ? "p-5" : ""}>{children}</div>
    </section>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="card p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-ink-500">{label}</p>
      <p className="mt-1.5 text-2xl font-semibold text-ink-900">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-ink-500">{hint}</p>}
    </div>
  );
}

export function Field({ label, error, children, hint }: { label: string; error?: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      {children}
      {hint && !error && <span className="mt-1 block text-xs text-ink-500">{hint}</span>}
      {error && <span className="mt-1 block text-xs text-red-600">{error}</span>}
    </label>
  );
}

export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink-900/40 p-4 pt-[8vh]" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-label={title} className={clsx("card w-full", wide ? "max-w-3xl" : "max-w-lg")}>
        <header className="flex items-center justify-between border-b border-ink-100 px-5 py-3.5">
          <h2 className="text-base font-semibold">{title}</h2>
          <button className="btn-ghost !p-1.5" onClick={onClose} aria-label="Close"><X className="h-4 w-4" /></button>
        </header>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

export function Tabs({ tabs, value, onChange }: { tabs: { key: string; label: string; count?: number }[]; value: string; onChange: (k: string) => void }) {
  return (
    <div className="mb-5 flex gap-1 border-b border-ink-200" role="tablist">
      {tabs.map((t) => (
        <button key={t.key} role="tab" aria-selected={value === t.key} onClick={() => onChange(t.key)}
          className={clsx("-mb-px border-b-2 px-3.5 py-2.5 text-sm font-medium", value === t.key ? "border-brand-600 text-brand-700" : "border-transparent text-ink-500 hover:text-ink-800")}>
          {t.label}{t.count != null && <span className="ml-1.5 rounded-full bg-ink-100 px-1.5 text-xs">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function Pager({ meta, onPage }: { meta?: { page: number; size: number; total: number }; onPage: (p: number) => void }) {
  if (!meta) return null;
  const pages = Math.max(1, Math.ceil(meta.total / meta.size));
  const from = meta.total ? (meta.page - 1) * meta.size + 1 : 0;
  return (
    <div className="flex items-center justify-between border-t border-ink-100 px-4 py-3 text-sm text-ink-500">
      <span>{from}–{Math.min(meta.page * meta.size, meta.total)} of {meta.total}</span>
      <div className="flex items-center gap-1">
        <button className="btn-ghost !p-1.5" disabled={meta.page <= 1} onClick={() => onPage(meta.page - 1)} aria-label="Previous page"><ChevronLeft className="h-4 w-4" /></button>
        <span className="px-2">Page {meta.page} of {pages}</span>
        <button className="btn-ghost !p-1.5" disabled={meta.page >= pages} onClick={() => onPage(meta.page + 1)} aria-label="Next page"><ChevronRight className="h-4 w-4" /></button>
      </div>
    </div>
  );
}

export type Col<T> = { key: string; header: string; render?: (r: T) => ReactNode; className?: string };

export function Table<T extends { id?: number | string }>({ cols, rows, onRow, empty }: { cols: Col<T>[]; rows: T[]; onRow?: (r: T) => void; empty?: ReactNode }) {
  if (!rows.length) return <>{empty ?? <Empty title="Nothing to show" />}</>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] border-collapse">
        <thead className="bg-ink-50"><tr>{cols.map((c) => <th key={c.key} className={clsx("th", c.className)}>{c.header}</th>)}</tr></thead>
        <tbody className="divide-y divide-ink-100">
          {rows.map((r, i) => (
            <tr key={(r.id as any) ?? i} className={clsx(onRow && "cursor-pointer hover:bg-ink-50")} onClick={() => onRow?.(r)}>
              {cols.map((c) => <td key={c.key} className={clsx("td", c.className)}>{c.render ? c.render(r) : String((r as any)[c.key] ?? "—")}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SearchBox({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <div className="relative w-full max-w-xs">
      <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-ink-400" />
      <input className="input pl-9" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder ?? "Search"} aria-label={placeholder ?? "Search"} />
    </div>
  );
}

export function Select({ value, onChange, options, all, label }: { value: string; onChange: (v: string) => void; options: (string | { value: string; label: string })[]; all?: string; label?: string }) {
  return (
    <select className="input !w-auto" value={value} onChange={(e) => onChange(e.target.value)} aria-label={label ?? all ?? "Select"}>
      {all !== undefined && <option value="">{all}</option>}
      {options.map((o) => {
        const v = typeof o === "string" ? o : o.value;
        return <option key={v} value={v}>{typeof o === "string" ? nice(o) : o.label}</option>;
      })}
    </select>
  );
}

export function Avatar({ name, color }: { name: string; color?: string }) {
  return <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-white" style={{ background: color || "#46526f" }}>{name.split(/\s+/).map((x) => x[0]).slice(0, 2).join("").toUpperCase()}</span>;
}

export function Confirm({ open, title, body, onCancel, onConfirm, danger, busy }: { open: boolean; title: string; body: string; onCancel: () => void; onConfirm: () => void; danger?: boolean; busy?: boolean }) {
  return (
    <Modal open={open} onClose={onCancel} title={title}>
      <p className="text-sm text-ink-600">{body}</p>
      <div className="mt-5 flex justify-end gap-2">
        <button className="btn-secondary" onClick={onCancel}>Cancel</button>
        <button className={danger ? "btn-danger" : "btn-primary"} onClick={onConfirm} disabled={busy}>{busy ? "Working…" : "Confirm"}</button>
      </div>
    </Modal>
  );
}
