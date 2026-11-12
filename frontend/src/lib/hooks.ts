import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { get } from "./api";

export function useList<T = any>(key: string, path: string, params: Record<string, unknown> = {}) {
  return useQuery({ queryKey: [key, params], queryFn: () => get<{ items: T[]; meta?: { page: number; size: number; total: number } }>(path, params), placeholderData: (prev) => prev });
}

export function useAct<V = any, R = any>(fn: (v: V) => Promise<R>, invalidate: string[] = [], onDone?: (r: R) => void) {
  const qc = useQueryClient();
  const [error, setError] = useState<string>("");
  const m = useMutation({
    mutationFn: fn,
    onMutate: () => setError(""),
    onSuccess: (r) => { invalidate.forEach((k) => qc.invalidateQueries({ queryKey: [k] })); onDone?.(r); },
    onError: (e: any) => setError(e.message),
  });
  return { ...m, error, setError };
}

export function useDebounced(v: string, ms = 300) {
  const [d, setD] = useState(v);
  const [last, setLast] = useState(v);
  if (v !== last) { setLast(v); setTimeout(() => setD(v), ms); }
  return d;
}
