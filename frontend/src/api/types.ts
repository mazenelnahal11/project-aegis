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
  origin: string;
  status: GateStatus;
  requested_at: string;
  executed_at: string | null;
  result: Record<string, unknown> | null;
  chat_session_id: string | null;
  tool_use_id: string | null;
};

export type GraceStatus = "sent" | "stop" | "explained" | "expired" | "escalated" | "failed";

export type GraceWarning = {
  id: number;
  target_kind: GateKind;
  target_payload: Record<string, unknown>;
  owner_linux_user: string | null;
  owner_slack_id: string | null;
  channel: string;
  reason: string;
  ack_token: string;
  sent_at: string;
  expires_at: string;
  status: GraceStatus;
  ack_at: string | null;
  ack_action: string | null;
  ack_reason: string | null;
  escalated_gate_id: number | null;
  origin: string;
};
