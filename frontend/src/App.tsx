import { useEffect } from "react";
import { Link, NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";

import { api } from "./api/client";
import { ConfirmGateModal } from "./components/ConfirmGateModal";
import { AuditLog } from "./pages/AuditLog";
import { Copilot } from "./pages/Copilot";
import { Dashboard } from "./pages/Dashboard";
import { Login } from "./pages/Login";
import { Permissions } from "./pages/Permissions";
import { Processes } from "./pages/Processes";
import { Warnings } from "./pages/Warnings";
import { useAuth } from "./stores/auth";
import { useGates } from "./stores/gates";

function Shell() {
  const { logout } = useAuth();
  const { refresh, pending } = useGates();
  const nav = useNavigate();

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 5_000);
    return () => clearInterval(t);
  }, [refresh]);

  const linkCls = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-1.5 rounded text-sm ${
      isActive ? "bg-accent text-ink font-medium" : "text-muted hover:text-text"
    }`;

  return (
    <div className="h-full flex flex-col">
      <header className="border-b border-edge bg-slab px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <Link to="/" className="text-accent font-bold text-lg">Aegis</Link>
          <nav className="flex items-center gap-1">
            <NavLink to="/" end className={linkCls}>Dashboard</NavLink>
            <NavLink to="/processes" className={linkCls}>Processes</NavLink>
            <NavLink to="/permissions" className={linkCls}>Permissions</NavLink>
            <NavLink to="/warnings" className={linkCls}>Warnings</NavLink>
            <NavLink to="/audit" className={linkCls}>Audit Log</NavLink>
            <NavLink to="/copilot" className={linkCls}>Copilot</NavLink>
          </nav>
        </div>
        <div className="flex items-center gap-3">
          {pending.length > 0 && (
            <span className="text-xs text-warn">{pending.length} pending</span>
          )}
          <button
            onClick={async () => { await logout(); nav("/login"); }}
            className="text-xs text-muted hover:text-text"
          >
            Sign out
          </button>
        </div>
      </header>
      <main className="flex-1 p-6 overflow-y-auto">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/processes" element={<Processes />} />
          <Route path="/permissions" element={<Permissions />} />
          <Route path="/warnings" element={<Warnings />} />
          <Route path="/audit" element={<AuditLog />} />
          <Route path="/copilot" element={<Copilot />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <ConfirmGateModal />
    </div>
  );
}

export default function App() {
  const { loggedIn, setLoggedIn } = useAuth();

  useEffect(() => {
    // Optimistic session probe: any 401 on a cheap call means we're logged out.
    api("/api/audit/summary")
      .then(() => setLoggedIn(true))
      .catch(() => setLoggedIn(false));
  }, [setLoggedIn]);

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="*" element={loggedIn ? <Shell /> : <Navigate to="/login" replace />} />
    </Routes>
  );
}
