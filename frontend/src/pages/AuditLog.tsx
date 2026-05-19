import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { api } from "../api/client";
import type { AuditLine } from "../api/types";
import { useAuditStream } from "../hooks/useAuditStream";

const LEVEL_COLOR: Record<string, string> = {
  INFO: "text-muted",
  WARN: "text-warn",
  ERROR: "text-err",
  ACTION: "text-ok",
  MASTER: "text-accent",
};

export function AuditLog() {
  const [showReport, setShowReport] = useState(false);

  const { data } = useQuery({
    queryKey: ["audit-log"],
    queryFn: () => api<{ lines: AuditLine[] }>("/api/audit/log?limit=300"),
  });

  const live = useAuditStream(true);

  const combined: AuditLine[] = useMemo(() => {
    const seen = new Set<string>();
    const out: AuditLine[] = [];
    for (const l of live) {
      if (!seen.has(l.raw)) { seen.add(l.raw); out.push(l); }
    }
    for (const l of (data?.lines ?? []).slice().reverse()) {
      if (!seen.has(l.raw)) { seen.add(l.raw); out.push(l); }
    }
    return out;
  }, [data, live]);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-accent">Audit Log</h1>
          <p className="text-muted text-sm">
            Live tail of <code className="text-text">security_audit.log</code>.
          </p>
        </div>
        <button
          onClick={() => setShowReport((v) => !v)}
          className="px-3 py-1 rounded border border-edge hover:bg-edge text-sm"
        >
          {showReport ? "Hide HTML report" : "Open HTML report"}
        </button>
      </div>

      {showReport && (
        <iframe
          title="audit-report"
          src="/api/audit/report"
          className="w-full h-[60vh] bg-ink border border-edge rounded mb-6"
        />
      )}

      <div className="bg-slab border border-edge rounded-lg max-h-[70vh] overflow-y-auto scrollbar-thin font-mono text-xs">
        {combined.length === 0 && (
          <div className="px-3 py-6 text-center text-muted">No entries yet.</div>
        )}
        {combined.map((l, i) => (
          <div key={i} className="px-3 py-1 border-b border-edge/40 whitespace-pre-wrap break-all">
            <span className="text-muted">[{l.timestamp}]</span>{" "}
            <span className={LEVEL_COLOR[l.level] || "text-muted"}>[{l.level}]</span>{" "}
            <span className="text-text">{l.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
