import { useEffect, useRef, useState } from "react";

import type { AuditLine } from "../api/types";

type Msg = { type: "line"; raw: string } | { type: "error"; message: string };

const AUDIT_RE = /^\[([^\]]+)\]\s+\[([A-Z]+)\]\s+(.*)$/;

function parseLine(raw: string): AuditLine {
  const m = AUDIT_RE.exec(raw);
  if (m) return { timestamp: m[1], level: m[2], message: m[3], raw };
  return { timestamp: "", level: "INFO", message: raw, raw };
}

export function useAuditStream(enabled: boolean) {
  const [lines, setLines] = useState<AuditLine[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!enabled) return;
    const url = `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/ws/audit`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      const cookie = document.cookie
        .split("; ")
        .find((c) => c.startsWith("aegis_session="))
        ?.split("=")[1];
      ws.send(cookie || "");
    };
    ws.onmessage = (ev) => {
      try {
        const msg: Msg = JSON.parse(ev.data);
        if (msg.type === "line") {
          setLines((prev) => [parseLine(msg.raw), ...prev].slice(0, 500));
        }
      } catch {
        /* ignore */
      }
    };
    return () => ws.close();
  }, [enabled]);

  return lines;
}
