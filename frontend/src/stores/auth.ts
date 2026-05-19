import { create } from "zustand";

import { postJson } from "../api/client";

type AuthState = {
  loggedIn: boolean;
  loading: boolean;
  setLoggedIn(v: boolean): void;
  login(password: string): Promise<void>;
  logout(): Promise<void>;
};

export const useAuth = create<AuthState>((set) => ({
  loggedIn: false,
  loading: false,
  setLoggedIn: (v) => set({ loggedIn: v }),
  async login(password) {
    set({ loading: true });
    try {
      await postJson("/api/login", { password });
      set({ loggedIn: true });
    } finally {
      set({ loading: false });
    }
  },
  async logout() {
    await postJson("/api/logout", {});
    set({ loggedIn: false });
  },
}));
