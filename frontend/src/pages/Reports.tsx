import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, Printer } from "lucide-react";
import { get } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Card, ErrorBox, PageHeader, Select, Spinner, Table } from "../components/ui";
import { money, title } from "../lib/format";

export default function Reports() {
  const { can } = useAuth();
  const [kind, setKind] = useState("sales"); const [range, setRange] = useState("90d");
  const { data: idx } = useQuery({ queryKey: ["reports-index"], queryFn: () => get("/api/reports") });
  const { data, isLoading, error } = useQuery({ queryKey: ["report", kind, range], queryFn: () => get(`/api/reports/${kind}`, { range }) });
  const cur = idx?.items.find((r: any) => r.kind === kind);
  const cols = (data?.columns ?? []).map((c: string, i: number) => ({ key: String(i), header: title(c), render: (r: any[]) => (typeof r[i] === "number" && /amount|revenue|value|net|total|pipeline|won/i.test(c) ? money(r[i]) : String(r[i] ?? "—")) }));
  return (
    <>
      <PageHeader title="Reports" subtitle="Operational and sales reporting"
        actions={<>
          <Select value={range} onChange={setRange} label="Date range" options={[{ value: "30d", label: "Last 30 days" }, { value: "90d", label: "Last 90 days" }, { value: "365d", label: "Last 12 months" }]} />
          {can("reports.export") && <><a className="btn-secondary" href={`/api/reports/${kind}/export?format=csv&range=${range}`}><Download className="h-4 w-4" /> CSV</a><a className="btn-secondary" href={`/api/reports/${kind}/export?format=pdf&range=${range}`}><Download className="h-4 w-4" /> PDF</a><a className="btn-secondary" target="_blank" rel="noreferrer" href={`/api/reports/${kind}/print?title=${encodeURIComponent(cur?.name ?? kind)}`}><Printer className="h-4 w-4" /> Print view</a></>}
        </>} />
      <div className="grid gap-6 lg:grid-cols-4">
        <Card title="Report type" pad={false} className="lg:col-span-1 h-fit">
          <ul>{idx?.items.map((r: any) => <li key={r.kind}><button className={`w-full px-5 py-3 text-left text-sm hover:bg-ink-50 ${kind === r.kind ? "bg-brand-50 font-semibold text-brand-700" : ""}`} onClick={() => setKind(r.kind)}>{r.name}</button></li>)}</ul>
        </Card>
        <div className="space-y-6 lg:col-span-3">
          {error ? <ErrorBox error={error} /> : isLoading ? <Spinner /> : (
            <>
              <div className="grid gap-4 sm:grid-cols-3">{Object.entries(data.summary ?? {}).map(([k, v]) => <div key={k} className="card p-4"><p className="label">{title(k)}</p><p className="text-xl font-semibold">{typeof v === "number" && /net|total|revenue|value|amount/i.test(k) ? money(v) : String(v)}</p></div>)}</div>
              <Card title={data.name} pad={false}><Table rows={data.rows.map((r: any[], i: number) => Object.assign([...r], { id: i }))} cols={cols} /></Card>
            </>
          )}
        </div>
      </div>
    </>
  );
}
