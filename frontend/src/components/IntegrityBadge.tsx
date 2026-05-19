import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";

type Verify = {
  ok: boolean;
  total: number;
  first_break_seq: number | null;
  first_break_reason: string | null;
};

export function IntegrityBadge() {
  const { data, isLoading } = useQuery({
    queryKey: ["audit-verify"],
    queryFn: () => api<Verify>("/api/audit/verify"),
    refetchInterval: 30_000,
  });

  if (isLoading || !data) {
    return (
      <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-edge text-xs text-muted">
        verifying ledger…
      </span>
    );
  }
  if (data.ok) {
    return (
      <span
        className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-ok bg-ok/10 text-xs text-ok font-medium"
        title="Every entry's hash matches the chain. No retroactive tampering detected."
      >
        🔒 Ledger intact ({data.total.toLocaleString()} entries)
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-err bg-err/10 text-xs text-err font-medium"
      title={data.first_break_reason ?? ""}
    >
      ⚠ Tampering detected at #{data.first_break_seq}
    </span>
  );
}
