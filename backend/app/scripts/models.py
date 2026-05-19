from typing import Literal

from pydantic import BaseModel, Field


class ProcessRow(BaseModel):
    pid: int
    user: str
    cpu_pct: float = Field(alias="cpuPct")
    mem_pct: float = Field(alias="memPct")
    runtime_seconds: int = Field(alias="runtimeSeconds")
    command: str
    state: str = ""
    flagged: bool = False
    reasons: list[str] = []

    model_config = {"populate_by_name": True, "json_schema_extra": {"by_alias": True}}


class PermissionRow(BaseModel):
    path: str
    owner: str
    file_type: str = Field(alias="fileType")
    current_mode: str = Field(alias="currentMode")
    recommended_mode: str = Field(alias="recommendedMode")

    model_config = {"populate_by_name": True}


class AuditLine(BaseModel):
    timestamp: str
    level: Literal["INFO", "WARN", "ERROR", "ACTION", "MASTER"] | str
    message: str
    raw: str


class ScanResult(BaseModel):
    scanned_at: str = Field(alias="scannedAt")
    processes: list[ProcessRow] = []
    flagged_pids: list[int] = Field(default_factory=list, alias="flaggedPids")
    stderr: str = ""

    model_config = {"populate_by_name": True}


class PermissionScanResult(BaseModel):
    scanned_at: str = Field(alias="scannedAt")
    scan_dir: str = Field(alias="scanDir")
    entries: list[PermissionRow] = []
    stderr: str = ""

    model_config = {"populate_by_name": True}
