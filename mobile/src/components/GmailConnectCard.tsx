import * as Linking from "expo-linking";
import * as WebBrowser from "expo-web-browser";
import { useQueryClient } from "@tanstack/react-query";
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

type SyncResponse = {
  processed: number;
  created: number;
  skipped_duplicate: number;
  errors: number;
  last_sync_at: string | null;
};

export default function GmailConnectCard() {
  const [busy, setBusy] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [connected, setConnected] = useState<string | null>(null);
  const queryClient = useQueryClient();

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
        Alert.alert("Gmail", "Backend did not confirm the connection.");
      }
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Could not start Gmail OAuth.";
      Alert.alert("Gmail connect failed", message);
    } finally {
      setBusy(false);
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      // First sync walks up to 30 days of emails — well past the global 15s timeout.
      const { data } = await api.post<SyncResponse>("/gmail/sync", null, {
        timeout: 120000,
      });
      await queryClient.invalidateQueries();
      Alert.alert(
        "Sync",
        `${data.created} nuevas · ${data.processed} procesadas · ${data.skipped_duplicate} duplicadas`,
      );
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Sync failed.";
      Alert.alert("Sync failed", message);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>Gmail</Text>
      {connected ? (
        <Text style={styles.connected}>Connected as {connected}</Text>
      ) : null}
      <View style={styles.row}>
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
        <Pressable
          style={({ pressed }) => [
            styles.buttonSecondary,
            (pressed || syncing) && styles.buttonDim,
          ]}
          disabled={syncing}
          onPress={handleSync}
        >
          {syncing ? (
            <ActivityIndicator color={colors.textPrimary} />
          ) : (
            <Text style={styles.buttonText}>Sync now</Text>
          )}
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 16,
    marginBottom: 24,
  },
  cardTitle: {
    color: colors.textSecondary,
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 12,
  },
  connected: {
    color: colors.success,
    fontSize: 13,
    marginBottom: 12,
  },
  row: { flexDirection: "row", gap: 8 },
  button: {
    backgroundColor: colors.primary,
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 10,
  },
  buttonSecondary: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 10,
  },
  buttonDim: {
    opacity: 0.7,
  },
  buttonText: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: "600",
  },
});
