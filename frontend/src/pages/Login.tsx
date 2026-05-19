import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../stores/auth";

export function Login() {
  const { login, loading } = useAuth();
  const nav = useNavigate();
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr("");
    try {
      await login(password);
      nav("/");
    } catch {
      setErr("Bad password");
    }
  };

  return (
    <div className="h-full flex items-center justify-center">
      <form
        onSubmit={onSubmit}
        className="bg-slab border border-edge rounded-lg p-6 w-full max-w-sm"
      >
        <h1 className="text-2xl font-bold text-accent mb-1">Aegis</h1>
        <p className="text-muted text-sm mb-6">Security console — admin sign in</p>
        <label className="block text-sm text-muted mb-2">Admin password</label>
        <input
          type="password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full bg-ink border border-edge rounded px-3 py-2 mb-4 outline-none focus:border-accent"
        />
        {err && <div className="text-err text-sm mb-3">{err}</div>}
        <button
          type="submit"
          disabled={loading || !password}
          className="w-full bg-accent text-ink font-medium py-2 rounded hover:opacity-90 disabled:opacity-50"
        >
          {loading ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
