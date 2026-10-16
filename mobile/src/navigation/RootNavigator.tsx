import { DarkTheme, NavigationContainer, type Theme } from "@react-navigation/native";
import { useEffect } from "react";

import SplashScreen from "../screens/SplashScreen";
import { api } from "../services/api";
import { registerForPushNotifications } from "../services/notifications";
import { takeOAuthFragment } from "../services/webAuth";
import { AuthUser, useAuthStore } from "../store/auth";
import { colors } from "../theme/colors";
import { Alert } from "../utils/alert";
import AppStack from "./AppStack";
import AuthStack from "./AuthStack";

// Matches the app palette so any area a screen doesn't paint (e.g. the sides
// of a centered page on desktop) stays dark instead of the default light grey.
const navTheme: Theme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    background: colors.background,
    card: colors.surface,
    border: colors.border,
    primary: colors.primary,
    text: colors.textPrimary,
  },
};

/**
 * Web only: finish an OAuth round-trip whose result the backend left in the
 * URL fragment. Runs before hydrate so a fresh login lands straight in the app.
 */
async function completeWebOAuth(): Promise<string | null> {
  const fragment = takeOAuthFragment();
  if (!fragment) return null;

  if (fragment.kind === "auth") {
    const { access_token: accessToken, refresh_token: refreshToken } = fragment;
    if (!accessToken || !refreshToken) return "Login failed: backend did not return tokens.";
    try {
      const me = await api.get<AuthUser>("/auth/me", {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      await useAuthStore.getState().setSession({ user: me.data, accessToken, refreshToken });
    } catch (err) {
      return `Login failed: ${err instanceof Error ? err.message : "could not authenticate."}`;
    }
    return null;
  }

  if (fragment.kind === "gmail-connected") {
    return fragment.status === "ok"
      ? `Gmail conectado: ${fragment.email ?? ""}`
      : "Gmail: el backend no confirmó la conexión.";
  }
  return null;
}

export default function RootNavigator() {
  const hydrated = useAuthStore((s) => s.hydrated);
  const accessToken = useAuthStore((s) => s.accessToken);
  const hydrate = useAuthStore((s) => s.hydrate);

  useEffect(() => {
    if (hydrated) return;
    (async () => {
      const notice = await completeWebOAuth();
      await hydrate();
      if (notice) setTimeout(() => Alert.alert("TrackIt", notice), 0);
    })();
  }, [hydrated, hydrate]);

  useEffect(() => {
    if (accessToken) {
      registerForPushNotifications();
    }
  }, [accessToken]);

  if (!hydrated) {
    return <SplashScreen />;
  }

  return (
    <NavigationContainer theme={navTheme}>
      {accessToken ? <AppStack /> : <AuthStack />}
    </NavigationContainer>
  );
}
