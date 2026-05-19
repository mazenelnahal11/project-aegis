import { useEffect, useRef, useState } from "react";

import type { Gate } from "../api/types";
import { useGates } from "../stores/gates";

type ChatBlock =
  | { kind: "user"; text: string }
  | { kind: "assistant"; text: string }
  | { kind: "tool_use"; name: string; input: Record<string, unknown> }
  | { kind: "tool_result"; result: Record<string, unknown> };

function parseSSE(chunk: string): { event: string; data: any }[] {
  const out: { event: string; data: any }[] = [];
  for (const frame of chunk.split("\n\n")) {
    const lines = frame.split("\n");
    let event = "message";
    let data = "";
    for (const line of lines) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      if (line.startsWith("data:")) data += line.slice(5).trim();
    }
    if (data) {
      try { out.push({ event, data: JSON.parse(data) }); } catch { /* ignore */ }
    }
  }
  return out;
}

export function Copilot() {
  const { pending, refresh, setActive } = useGates();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [blocks, setBlocks] = useState<ChatBlock[]>([]);
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [blocks]);

  const send = async () => {
    if (!draft.trim() || busy) return;
    const text = draft.trim();
    setDraft("");
    setBlocks((b) => [...b, { kind: "user", text }]);
    setBusy(true);
    let buffer = "";
    try {
      const res = await fetch("/api/llm/chat", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: text }),
      });
      const reader = res.body!.getReader();
      const dec = new TextDecoder();
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += dec.decode(value, { stream: true });
        const splitAt = buffer.lastIndexOf("\n\n");
        if (splitAt < 0) continue;
        const ready = buffer.slice(0, splitAt + 2);
        buffer = buffer.slice(splitAt + 2);
        for (const ev of parseSSE(ready)) {
          if (ev.event === "session") setSessionId(ev.data.session_id);
          if (ev.event === "text") {
            setBlocks((b) => [...b, { kind: "assistant", text: ev.data.text }]);
          }
          if (ev.event === "tool_use") {
            setBlocks((b) => [...b, {
              kind: "tool_use", name: ev.data.name, input: ev.data.input,
            }]);
          }
          if (ev.event === "tool_result") {
            setBlocks((b) => [...b, { kind: "tool_result", result: ev.data.result }]);
            if (ev.data.result.requires_confirmation) await refresh();
          }
        }
      }
    } catch (e) {
      setBlocks((b) => [...b, { kind: "assistant", text: `Error: ${e}` }]);
    } finally {
      setBusy(false);
      refresh();
    }
  };

  const openGate = async (g: Gate) => setActive(g);

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 h-[calc(100vh-8rem)]">
      <div className="md:col-span-2 flex flex-col bg-slab border border-edge rounded-lg">
        <div className="p-3 border-b border-edge">
          <h1 className="text-lg font-bold text-accent">Copilot</h1>
          <p className="text-xs text-muted">
            Natural-language audit + remediation. Destructive actions always require approval.
          </p>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-3 scrollbar-thin">
          {blocks.length === 0 && (
            <div className="text-muted text-sm text-center mt-12">
              Try: <em>"who is hogging the CPU?"</em> or{" "}
              <em>"find any world-writable files in /home and fix them"</em>.
            </div>
          )}
          {blocks.map((b, i) => (
            <ChatRow key={i} block={b} />
          ))}
          <div ref={endRef} />
        </div>
        <div className="p-3 border-t border-edge flex gap-2">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder={busy ? "Working…" : "Ask Aegis…"}
            disabled={busy}
            className="flex-1 bg-ink border border-edge rounded px-3 py-2 outline-none focus:border-accent"
          />
          <button
            onClick={send}
            disabled={busy || !draft.trim()}
            className="px-4 py-2 rounded bg-accent text-ink font-medium disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </div>

      <aside className="bg-slab border border-edge rounded-lg p-3 overflow-y-auto scrollbar-thin">
        <h2 className="text-sm font-bold text-muted uppercase mb-3">Pending confirmations</h2>
        {pending.length === 0 && (
          <div className="text-xs text-muted">Nothing pending.</div>
        )}
        {pending.map((g) => {
          const payload = g.payload as Record<string, string | number>;
          const summary =
            g.kind === "kill"
              ? `kill ${payload.pid}`
              : `chmod ${payload.mode} ${payload.path}`;
          return (
            <button
              key={g.id}
              onClick={() => openGate(g)}
              className="w-full text-left p-2 rounded border border-edge hover:bg-edge mb-2"
            >
              <div className="font-mono text-xs text-text">{summary}</div>
              <div className="text-[10px] text-muted mt-1">
                #{g.id} • {g.origin} • {g.requested_at}
              </div>
            </button>
          );
        })}
      </aside>
    </div>
  );
}

function ChatRow({ block }: { block: ChatBlock }) {
  if (block.kind === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] bg-accent/20 border border-accent/40 rounded px-3 py-2 text-sm">
          {block.text}
        </div>
      </div>
    );
  }
  if (block.kind === "assistant") {
    return (
      <div className="max-w-[80%] bg-ink border border-edge rounded px-3 py-2 text-sm whitespace-pre-wrap">
        {block.text}
      </div>
    );
  }
  if (block.kind === "tool_use") {
    return (
      <div className="text-xs text-muted font-mono">
        → tool: {block.name}({JSON.stringify(block.input)})
      </div>
    );
  }
  return (
    <div className="text-xs text-muted font-mono">
      ← result: {JSON.stringify(block.result).slice(0, 200)}
      {JSON.stringify(block.result).length > 200 ? "…" : ""}
    </div>
  );
}
