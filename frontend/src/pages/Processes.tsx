import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api, postJson } from "../api/client";
import type { Gate, ProcessRow } from "../api/types";
import { useGates } from "../stores/gates";

function fmtRuntime(secs: number) {
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  return h >= 1 ? `${h}h ${m}m` : `${m}m`;
}

export function Processes() {
  const { setActive } = useGates();
  const [onlyFlagged, setOnlyFlagged] = useState(false);

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["processes", onlyFlagged],
    queryFn: () =>
      api<{ processes: ProcessRow[] }>(
        `/api/scan/processes?only_flagged=${onlyFlagged}`,
      ),
    refetchInterval: 5_000,
  });

  const onKill = async (pid: number, reason: string) => {
    const res = await postJson<{ gate_id: number }>("/api/act/kill", { pid, reason });
    const gate = await api<Gate>(`/api/gates/${res.gate_id}`);
    setActive(gate);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-accent">Processes</h1>
          <p className="text-muted text-sm">
            Live snapshot from <code className="text-text">ps</code> via WSL. Flagged rows
            exceed CPU/runtime thresholds.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="text-sm text-muted flex items-center gap-2">
            <input
              type="checkbox"
              checked={onlyFlagged}
              onChange={(e) => setOnlyFlagged(e.target.checked)}
            />
            Only flagged
          </label>
          <button
            onClick={() => refetch()}
            className="text-sm px-3 py-1 rounded border border-edge hover:bg-edge"
          >
            {isFetching ? "…" : "Refresh"}
          </button>
        </div>
      </div>

      <div className="bg-slab border border-edge rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-ink text-muted text-left">
            <tr>
              <th className="px-3 py-2">PID</th>
              <th className="px-3 py-2">User</th>
              <th className="px-3 py-2">CPU%</th>
              <th className="px-3 py-2">Mem%</th>
              <th className="px-3 py-2">Runtime</th>
              <th className="px-3 py-2">State</th>
              <th className="px-3 py-2">Command</th>
              <th className="px-3 py-2">Action</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={8} className="px-3 py-6 text-center text-muted">Loading…</td></tr>
            )}
            {data?.processes.length === 0 && (
              <tr><td colSpan={8} className="px-3 py-6 text-center text-muted">No rows.</td></tr>
            )}
            {data?.processes.map((p) => (
              <tr
                key={p.pid}
                className={`border-t border-edge ${p.flagged ? "bg-err/10" : ""}`}
              >
                <td className="px-3 py-2 font-mono">{p.pid}</td>
                <td className="px-3 py-2">{p.user}</td>
                <td className="px-3 py-2">{p.cpuPct.toFixed(1)}</td>
                <td className="px-3 py-2">{p.memPct.toFixed(1)}</td>
                <td className="px-3 py-2">{fmtRuntime(p.runtimeSeconds)}</td>
                <td className="px-3 py-2">{p.state}</td>
                <td className="px-3 py-2 font-mono text-xs">{p.command}</td>
                <td className="px-3 py-2">
                  <button
                    onClick={() =>
                      onKill(p.pid, p.flagged ? p.reasons.join(" | ") : "manual")
                    }
                    className="text-xs px-2 py-1 rounded border border-err text-err hover:bg-err hover:text-white"
                  >
                    Terminate
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
