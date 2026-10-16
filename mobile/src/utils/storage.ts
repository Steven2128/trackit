import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

// SecureStore has no web implementation — the browser falls back to
// localStorage (same-origin only; the trade-off of running in a browser).
const isWeb = Platform.OS === "web";

export const storage = {
  getItem: async (key: string): Promise<string | null> =>
    isWeb ? window.localStorage.getItem(key) : SecureStore.getItemAsync(key),

  setItem: async (key: string, value: string): Promise<void> => {
    if (isWeb) window.localStorage.setItem(key, value);
    else await SecureStore.setItemAsync(key, value);
  },

  deleteItem: async (key: string): Promise<void> => {
    if (isWeb) window.localStorage.removeItem(key);
    else await SecureStore.deleteItemAsync(key);
  },
};
