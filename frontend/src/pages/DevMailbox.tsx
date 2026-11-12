import { useQuery } from "@tanstack/react-query";
import { get } from "../lib/api";
import { Card, Empty, ErrorBox, Spinner } from "../components/ui";
import { dateTime } from "../lib/format";
import { AuthShell } from "./Login";

export default function DevMailbox() {
  const { data, isLoading, error } = useQuery({ queryKey: ["mailbox"], queryFn: () => get("/api/dev/mailbox"), refetchInterval: 5000 });
  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="text-2xl font-semibold">Development mailbox</h1>
      <p className="mb-6 mt-1 text-sm text-ink-500">Messages the platform would send by email appear here in training environments.</p>
      {error ? <ErrorBox error={error} /> : isLoading ? <Spinner /> : !data.items.length ? <Card><Empty title="No messages yet" /></Card> : (
        <div className="space-y-3">{data.items.map((m: any) => <Card key={m.id}><div className="flex justify-between text-xs text-ink-500"><span>To {m.to}</span><span>{dateTime(m.created_at)}</span></div><p className="mt-1 font-semibold">{m.subject}</p><p className="mt-1 whitespace-pre-wrap break-words text-sm text-ink-700">{m.body}</p></Card>)}</div>
      )}
    </div>
  );
}
