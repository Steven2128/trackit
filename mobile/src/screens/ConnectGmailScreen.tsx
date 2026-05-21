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
import { colors } from "../theme/colors";

WebBrowser.maybeCompleteAuthSession();

const RETURN_SCHEME = "trackit";
const RETURN_PATH = "gmail-connected";

type ConnectResponse = { auth_url: string };

export default function ConnectGmailScreen() {
  const [busy, setBusy] = useState(false);
  const [connected, setConnected] = useState<string | null>(null);

  const handleConnect = async () => {
    setBusy(true);
    try {
      const { data } = await api.post<ConnectResponse>("/gmail/connect", {
        return_scheme: RETURN_SCHEME,
      });

      const returnUrl = `${RETURN_SCHEME}://${RETURN_PATH}`;
      const result = await WebBrowser.openAuthSessionAsync(
        data.auth_url,
        returnUrl,
      );

      if (result.type !== "success" || !result.url) {
        return;
      }

      const { queryParams } = Linking.parse(result.url);
      const status = queryParams?.status;
      const email = queryParams?.email;

      if (status === "ok" && typeof email === "string") {
        setConnected(email);
      } else {
        Alert.alert("Gmail connect", "Backend did not confirm the connection.");
      }
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Could not start Gmail OAuth.";
      Alert.alert("Gmail connect failed", message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Connect Gmail</Text>
      <Text style={styles.subtitle}>
        Authorize TrackIt to read your bank notification emails. We only request
        read-only access and store the OAuth tokens encrypted at rest.
      </Text>

      {connected ? (
        <Text style={styles.connected}>Connected as {connected}</Text>
      ) : null}

      <Pressable
        style={({ pressed }) => [
          styles.button,
          (pressed || busy) && styles.buttonDim,
        ]}
        disabled={busy}
        onPress={handleConnect}
      >
        {busy ? (
          <ActivityIndicator color={colors.textPrimary} />
        ) : (
          <Text style={styles.buttonText}>
            {connected ? "Reconnect Gmail" : "Connect Gmail"}
          </Text>
        )}
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    padding: 24,
    justifyContent: "center",
  },
  title: {
    color: colors.textPrimary,
    fontSize: 28,
    fontWeight: "700",
    marginBottom: 12,
  },
  subtitle: {
    color: colors.textSecondary,
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 32,
  },
  connected: {
    color: colors.success,
    fontSize: 14,
    marginBottom: 24,
  },
  button: {
    backgroundColor: colors.primary,
    paddingVertical: 14,
    paddingHorizontal: 32,
    borderRadius: 12,
    alignSelf: "flex-start",
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
