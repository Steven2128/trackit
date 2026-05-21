import Constants from "expo-constants";
import * as Linking from "expo-linking";
import * as WebBrowser from "expo-web-browser";
import { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { api } from "../services/api";
import { AuthUser, useAuthStore } from "../store/auth";
import { colors } from "../theme/colors";

WebBrowser.maybeCompleteAuthSession();

const API_URL =
  (Constants.expoConfig?.extra?.apiUrl as string | undefined) ??
  process.env.EXPO_PUBLIC_API_URL ??
  "http://localhost:8000";

const RETURN_SCHEME = "trackit";
const RETURN_PATH = "auth";

export default function LoginScreen() {
  const setSession = useAuthStore((s) => s.setSession);
  const [busy, setBusy] = useState(false);

  const handleLogin = async () => {
    setBusy(true);
    try {
      const returnUrl = `${RETURN_SCHEME}://${RETURN_PATH}`;
      const startUrl = `${API_URL}/auth/google/start?return_scheme=${RETURN_SCHEME}`;

      const result = await WebBrowser.openAuthSessionAsync(startUrl, returnUrl);

      if (result.type !== "success" || !result.url) {
        return;
      }

      const { queryParams } = Linking.parse(result.url);
      const accessToken = queryParams?.access_token;
      const refreshToken = queryParams?.refresh_token;

      if (
        typeof accessToken !== "string" ||
        typeof refreshToken !== "string"
      ) {
        Alert.alert("Login failed", "Backend did not return tokens.");
        return;
      }

      const meResponse = await api.get<AuthUser>("/auth/me", {
        headers: { Authorization: `Bearer ${accessToken}` },
      });

      await setSession({
        user: meResponse.data,
        accessToken,
        refreshToken,
      });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Could not authenticate.";
      Alert.alert("Login failed", message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>TrackIt</Text>
      <Text style={styles.subtitle}>
        Read bank emails. Track every expense.
      </Text>

      <Pressable
        style={({ pressed }) => [
          styles.button,
          (pressed || busy) && styles.buttonDim,
        ]}
        disabled={busy}
        onPress={handleLogin}
      >
        {busy ? (
          <ActivityIndicator color={colors.textPrimary} />
        ) : (
          <Text style={styles.buttonText}>Sign in with Google</Text>
        )}
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 24,
  },
  title: {
    fontSize: 36,
    fontWeight: "700",
    color: colors.textPrimary,
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 14,
    color: colors.textSecondary,
    marginBottom: 48,
    textAlign: "center",
  },
  button: {
    backgroundColor: colors.primary,
    paddingVertical: 14,
    paddingHorizontal: 32,
    borderRadius: 12,
    minWidth: 240,
    alignItems: "center",
  },
  buttonDim: {
    backgroundColor: colors.primaryDim,
    opacity: 0.7,
  },
  buttonText: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: "600",
  },
});
