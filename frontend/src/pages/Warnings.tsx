import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { GraceWarning } from "../api/types";

const STATUS_TONE: Record<string, string> = {
  sent: "text-warn",
  stop: "text-accent",
  explained: "text-ok",
  expired: "text-muted",
  escalated: "text-err",
  failed: "text-err",
};

function fmtCountdown(expiresAt: string, now: number): string {
  const exp = new Date(expiresAt).getTime();
  const remaining = exp - now;
  if (remaining <= 0) return "expired";
  const minutes = Math.floor(remaining / 60_000);
  const seconds = Math.floor((remaining % 60_000) / 1000);
  return `${minutes}m ${seconds.toString().padStart(2, "0")}s`;
}

function actionSummary(w: GraceWarning): string {
  const p = w.target_payload as Record<string, string | number>;
  if (w.target_kind === "kill") return `Terminate PID ${p.pid}`;
  return `chmod ${p.mode} ${p.path}`;
}

export function Warnings() {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["grace-warnings"],
    queryFn: () => api<{ warnings: GraceWarning[] }>("/api/grace"),
    refetchInterval: 5_000,
  });

  const warnings = data?.warnings ?? [];
  const active = warnings.filter((w) => w.status === "sent");
  const closed = warnings.filter((w) => w.status !== "sent");

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-accent">Grace warnings</h1>
          <p className="text-muted text-sm">
            Outstanding "warn before kill" notifications. Expired warnings become
            normal kill gates that still need admin approval.
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="text-sm px-3 py-1 rounded border border-edge hover:bg-edge"
        >
          Refresh
        </button>
      </div>

      <h2 className="text-sm font-bold text-muted uppercase mb-2">
        Active ({active.length})
      </h2>
      <div className="bg-slab border border-edge rounded-lg overflow-hidden mb-6">
        <table className="w-full text-sm">
          <thead className="bg-ink text-muted text-left">
            <tr>
              <th className="px-3 py-2">#</th>
              <th className="px-3 py-2">Owner</th>
              <th className="px-3 py-2">Action</th>
              <th className="px-3 py-2">Channel</th>
              <th className="px-3 py-2">Reason</th>
              <th className="px-3 py-2">Time remaining</th>
              <th className="px-3 py-2">Ack URL</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={7} className="px-3 py-4 text-center text-muted">Loading…</td></tr>
            )}
            {!isLoading && active.length === 0 && (
              <tr><td colSpan={7} className="px-3 py-4 text-center text-ok">No active warnings.</td></tr>
            )}
            {active.map((w) => (
              <tr key={w.id} className="border-t border-edge">
                <td className="px-3 py-2 font-mono">{w.id}</td>
                <td className="px-3 py-2">{w.owner_linux_user || "—"}</td>
                <td className="px-3 py-2 font-mono text-xs">{actionSummary(w)}</td>
                <td className="px-3 py-2">{w.channel}</td>
                <td className="px-3 py-2 text-xs">{w.reason}</td>
                <td className="px-3 py-2 font-mono text-warn">{fmtCountdown(w.expires_at, now)}</td>
                <td className="px-3 py-2">
                  <a
                    href={`/api/grace/ack/${w.ack_token}`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-accent hover:underline"
                  >
                    open ↗
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 className="text-sm font-bold text-muted uppercase mb-2">
        History ({closed.length})
      </h2>
      <div className="bg-slab border border-edge rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-ink text-muted text-left">
            <tr>
              <th className="px-3 py-2">#</th>
              <th className="px-3 py-2">Owner</th>
              <th className="px-3 py-2">Action</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Outcome</th>
            </tr>
          </thead>
          <tbody>
            {closed.length === 0 && (
              <tr><td colSpan={5} className="px-3 py-4 text-center text-muted">No history.</td></tr>
            )}
            {closed.map((w) => (
              <tr key={w.id} className="border-t border-edge">
                <td className="px-3 py-2 font-mono">{w.id}</td>
                <td className="px-3 py-2">{w.owner_linux_user || "—"}</td>
                <td className="px-3 py-2 font-mono text-xs">{actionSummary(w)}</td>
                <td className={`px-3 py-2 font-bold ${STATUS_TONE[w.status]}`}>
                  {w.status}
                </td>
                <td className="px-3 py-2 text-xs">
                  {w.status === "escalated" && w.escalated_gate_id && (
                    <>→ gate #{w.escalated_gate_id}</>
                  )}
                  {w.status === "explained" && w.ack_reason && (
                    <em className="text-muted">"{w.ack_reason}"</em>
                  )}
                  {w.status === "stop" && (
                    <span className="text-muted">marked for kill</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
