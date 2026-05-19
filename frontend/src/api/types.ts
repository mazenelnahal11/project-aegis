export type ProcessRow = {
  pid: number;
  user: string;
  cpuPct: number;
  memPct: number;
  runtimeSeconds: number;
  command: string;
  state: string;
  flagged: boolean;
  reasons: string[];
};

export type PermissionRow = {
  path: string;
  owner: string;
  fileType: string;
  currentMode: string;
  recommendedMode: string;
};

export type AuditLine = {
  timestamp: string;
  level: string;
  message: string;
  raw: string;
};

export type GateKind = "kill" | "fix_permission";
export type GateStatus = "pending" | "approved" | "rejected" | "executed" | "failed";

export type Gate = {
  id: number;
  kind: GateKind;
  payload: Record<string, unknown>;
  origin: "ui" | "llm";
  status: GateStatus;
  requested_at: string;
  executed_at: string | null;
  result: Record<string, unknown> | null;
  chat_session_id: string | null;
  tool_use_id: string | null;
};
