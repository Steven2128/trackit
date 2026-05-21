import * as SecureStore from "expo-secure-store";
import { create } from "zustand";

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
      SecureStore.getItemAsync(KEY_USER),
      SecureStore.getItemAsync(KEY_ACCESS),
      SecureStore.getItemAsync(KEY_REFRESH),
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
      SecureStore.setItemAsync(KEY_USER, JSON.stringify(user)),
      SecureStore.setItemAsync(KEY_ACCESS, accessToken),
      SecureStore.setItemAsync(KEY_REFRESH, refreshToken),
    ]);
    set({ user, accessToken, refreshToken });
  },

  setAccessToken: async (token) => {
    await SecureStore.setItemAsync(KEY_ACCESS, token);
    set({ accessToken: token });
  },

  clearSession: async () => {
    await Promise.all([
      SecureStore.deleteItemAsync(KEY_USER),
      SecureStore.deleteItemAsync(KEY_ACCESS),
      SecureStore.deleteItemAsync(KEY_REFRESH),
    ]);
    set({ user: null, accessToken: null, refreshToken: null });
  },
}));
