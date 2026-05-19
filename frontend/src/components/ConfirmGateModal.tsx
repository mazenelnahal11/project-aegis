import { useState } from "react";

import { useGates } from "../stores/gates";

export function ConfirmGateModal() {
  const { active, setActive, approve, reject } = useGates();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  if (!active) return null;

  const payload = active.payload as Record<string, string | number>;
  const preview =
    active.kind === "kill"
      ? `kill -15 ${payload.pid}; sleep 10; kill -9 ${payload.pid} (if alive)`
      : `chmod ${payload.mode} ${payload.path}`;

  const onApprove = async () => {
    setBusy(true);
    setErr("");
    try {
      await approve(active.id);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const onReject = async () => {
    setBusy(true);
    try {
      await reject(active.id);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
      <div className="bg-slab border border-edge rounded-lg max-w-xl w-full p-6 shadow-2xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-accent">
            {active.kind === "kill" ? "Terminate process?" : "Change file permissions?"}
          </h2>
          <span className="text-xs px-2 py-0.5 rounded bg-edge text-muted">
            origin: {active.origin}
          </span>
        </div>

        <div className="text-sm text-muted mb-2">Command preview</div>
        <pre className="bg-ink border border-edge rounded p-3 text-text font-mono text-sm overflow-x-auto mb-4">
          {preview}
        </pre>

        {payload.reason && (
          <>
            <div className="text-sm text-muted mb-2">Reason</div>
            <div className="bg-ink border border-edge rounded p-3 text-text text-sm mb-4">
              {payload.reason as string}
            </div>
          </>
        )}

        {err && <div className="text-err text-sm mb-3">{err}</div>}

        <div className="flex justify-end gap-2">
          <button
            onClick={() => setActive(null)}
            disabled={busy}
            className="px-4 py-2 rounded text-muted hover:text-text"
          >
            Close
          </button>
          <button
            onClick={onReject}
            disabled={busy}
            className="px-4 py-2 rounded border border-edge text-text hover:bg-edge"
          >
            Reject
          </button>
          <button
            onClick={onApprove}
            disabled={busy}
            className="px-4 py-2 rounded bg-err text-white hover:opacity-90 font-medium"
          >
            {busy ? "Working…" : "Approve & run"}
          </button>
        </div>
      </div>
    </div>
  );
}
