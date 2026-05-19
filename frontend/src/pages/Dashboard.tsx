import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";
import { StatCard } from "../components/StatCard";

type Summary = {
  rogue: number;
  sigterm: number;
  sigkill: number;
  perm_fixed: number;
  errors: number;
  warns: number;
};

export function Dashboard() {
  const { data } = useQuery({
    queryKey: ["audit-summary"],
    queryFn: () => api<Summary>("/api/audit/summary"),
    refetchInterval: 10_000,
  });

  return (
    <div>
      <h1 className="text-2xl font-bold text-accent mb-1">Dashboard</h1>
      <p className="text-muted text-sm mb-6">
        Aggregate counts from <code className="text-text">security_audit.log</code>.
      </p>
      <div className="flex flex-wrap gap-3 mb-8">
        <StatCard label="Rogue processes" value={data?.rogue ?? "—"} tone="warn" />
        <StatCard label="SIGTERM sent" value={data?.sigterm ?? "—"} />
        <StatCard label="SIGKILL sent" value={data?.sigkill ?? "—"} tone="err" />
        <StatCard label="Perms fixed" value={data?.perm_fixed ?? "—"} tone="ok" />
        <StatCard label="Warnings" value={data?.warns ?? "—"} tone="warn" />
        <StatCard label="Errors" value={data?.errors ?? "—"} tone="err" />
      </div>
      <p className="text-sm text-muted">
        Use the nav above to inspect live processes, world-writable files, the audit log, or
        ask the Copilot a question.
      </p>
    </div>
  );
}
