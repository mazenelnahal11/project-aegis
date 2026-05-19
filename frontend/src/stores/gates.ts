import { create } from "zustand";

import { api, postJson } from "../api/client";
import type { Gate } from "../api/types";

type GatesState = {
  pending: Gate[];
  active: Gate | null;
  setActive(g: Gate | null): void;
  refresh(): Promise<void>;
  approve(id: number): Promise<Gate>;
  reject(id: number): Promise<Gate>;
};

export const useGates = create<GatesState>((set) => ({
  pending: [],
  active: null,
  setActive: (g) => set({ active: g }),
  async refresh() {
    const data = await api<{ gates: Gate[] }>("/api/gates?status=pending");
    set({ pending: data.gates });
  },
  async approve(id) {
    const g = await postJson<Gate>(`/api/gates/${id}/approve`, {});
    set((s) => ({
      pending: s.pending.filter((x) => x.id !== id),
      active: s.active?.id === id ? null : s.active,
    }));
    return g;
  },
  async reject(id) {
    const g = await postJson<Gate>(`/api/gates/${id}/reject`, {});
    set((s) => ({
      pending: s.pending.filter((x) => x.id !== id),
      active: s.active?.id === id ? null : s.active,
    }));
    return g;
  },
}));
