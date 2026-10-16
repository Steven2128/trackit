import { create } from "zustand";

import { storage } from "../utils/storage";

export type AuthUser = {
  id: string;
  email: string;
  name?: string | null;
  picture?: string | null;
};

type AuthState = {
  user: AuthUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  hydrated: boolean;
  setSession: (params: {
    user: AuthUser;
    accessToken: string;
    refreshToken: string;
  }) => Promise<void>;
  setAccessToken: (token: string) => Promise<void>;
  hydrate: () => Promise<void>;
  clearSession: () => Promise<void>;
};

const KEY_USER = "trackit.user";
const KEY_ACCESS = "trackit.accessToken";
const KEY_REFRESH = "trackit.refreshToken";

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: null,
  refreshToken: null,
  hydrated: false,

  hydrate: async () => {
    const [userRaw, accessToken, refreshToken] = await Promise.all([
      storage.getItem(KEY_USER),
      storage.getItem(KEY_ACCESS),
      storage.getItem(KEY_REFRESH),
    ]);

    set({
      user: userRaw ? (JSON.parse(userRaw) as AuthUser) : null,
      accessToken: accessToken ?? null,
      refreshToken: refreshToken ?? null,
      hydrated: true,
    });
  },

  setSession: async ({ user, accessToken, refreshToken }) => {
    await Promise.all([
      storage.setItem(KEY_USER, JSON.stringify(user)),
      storage.setItem(KEY_ACCESS, accessToken),
      storage.setItem(KEY_REFRESH, refreshToken),
    ]);
    set({ user, accessToken, refreshToken });
  },

  setAccessToken: async (token) => {
    await storage.setItem(KEY_ACCESS, token);
    set({ accessToken: token });
  },

  clearSession: async () => {
    await Promise.all([
      storage.deleteItem(KEY_USER),
      storage.deleteItem(KEY_ACCESS),
      storage.deleteItem(KEY_REFRESH),
    ]);
    set({ user: null, accessToken: null, refreshToken: null });
  },
}));
