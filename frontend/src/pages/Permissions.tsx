import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api, postJson } from "../api/client";
import type { Gate, PermissionRow } from "../api/types";
import { useGates } from "../stores/gates";

export function Permissions() {
  const { setActive } = useGates();
  const [dir, setDir] = useState("/home");
  const [submitted, setSubmitted] = useState("/home");

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["permissions", submitted],
    queryFn: () =>
      api<{ entries: PermissionRow[] }>(
        `/api/scan/permissions?dir=${encodeURIComponent(submitted)}`,
      ),
  });

  const onFix = async (row: PermissionRow) => {
    const res = await postJson<{ gate_id: number }>("/api/act/fix-permission", {
      path: row.path,
      mode: row.recommendedMode,
      reason: `world-writable ${row.fileType}`,
    });
    const gate = await api<Gate>(`/api/gates/${res.gate_id}`);
    setActive(gate);
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-accent mb-1">Permissions</h1>
      <p className="text-muted text-sm mb-4">
        World-writable (mode 777) files. Click <span className="text-text">Fix</span> to
        chmod to a safer mode.
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          setSubmitted(dir);
        }}
        className="flex gap-2 mb-4"
      >
        <input
          value={dir}
          onChange={(e) => setDir(e.target.value)}
          className="flex-1 bg-ink border border-edge rounded px-3 py-2 font-mono text-sm"
          placeholder="/home"
        />
        <button
          type="submit"
          className="px-4 py-2 rounded bg-accent text-ink font-medium hover:opacity-90"
        >
          Scan
        </button>
        <button
          type="button"
          onClick={() => refetch()}
          className="px-3 py-2 rounded border border-edge hover:bg-edge text-sm"
        >
          {isFetching ? "…" : "Refresh"}
        </button>
      </form>

      <div className="bg-slab border border-edge rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-ink text-muted text-left">
            <tr>
              <th className="px-3 py-2">Path</th>
              <th className="px-3 py-2">Owner</th>
              <th className="px-3 py-2">Type</th>
              <th className="px-3 py-2">Mode</th>
              <th className="px-3 py-2">Action</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={5} className="px-3 py-6 text-center text-muted">Loading…</td></tr>
            )}
            {data?.entries.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-ok">
                  No world-writable entries found in {submitted}.
                </td>
              </tr>
            )}
            {data?.entries.map((r) => (
              <tr key={r.path} className="border-t border-edge">
                <td className="px-3 py-2 font-mono text-xs break-all">{r.path}</td>
                <td className="px-3 py-2">{r.owner}</td>
                <td className="px-3 py-2">{r.fileType}</td>
                <td className="px-3 py-2 font-mono text-warn">
                  {r.currentMode} → {r.recommendedMode}
                </td>
                <td className="px-3 py-2">
                  <button
                    onClick={() => onFix(r)}
                    className="text-xs px-2 py-1 rounded border border-ok text-ok hover:bg-ok hover:text-ink"
                  >
                    Fix
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
