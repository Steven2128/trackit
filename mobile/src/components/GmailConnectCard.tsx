import * as Linking from "expo-linking";
import * as WebBrowser from "expo-web-browser";
import { useQueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { api } from "../services/api";
import { gmailStatusQueryKey, useGmailStatus } from "../services/queries/gmail";
import { isWeb, redirectTo, webReturnUrl } from "../services/webAuth";
import { colors } from "../theme/colors";
import { Alert } from "../utils/alert";

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
  const [justConnected, setJustConnected] = useState<string | null>(null);
  const { data: status, isLoading: statusLoading, isError: statusError } = useGmailStatus();
  const connected = justConnected ?? (status?.connected ? status.email : null);
  // Only a confirmed "not connected" blocks syncing; while the status loads
  // (the free API can take a minute to wake up) or if it failed, let the user
  // try — the backend answers with a clear error if there is no Gmail.
  const knownDisconnected = !justConnected && status?.connected === false;
  const queryClient = useQueryClient();

  const handleConnect = async () => {
    setBusy(true);
    try {
      const { data } = await api.post<ConnectResponse>(
        "/gmail/connect",
        isWeb ? { return_url: webReturnUrl() } : { return_scheme: RETURN_SCHEME },
      );

      if (isWeb) {
        // RootNavigator reports the result when Google sends us back.
        redirectTo(data.auth_url);
        return;
      }

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
        setJustConnected(email);
        queryClient.invalidateQueries({ queryKey: gmailStatusQueryKey });
      } else {
        Alert.alert("Gmail", "No se pudo confirmar la conexión con Gmail.");
      }
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "No se pudo iniciar la conexión con Google.";
      Alert.alert("No se pudo conectar Gmail", message);
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
        "Sincronización",
        `${data.created} nuevas · ${data.processed} procesadas · ${data.skipped_duplicate} duplicadas`,
      );
    } catch (err) {
      const message =
        isAxiosError(err) && err.response?.status === 404
          ? "Todavía no hay una cuenta de Gmail conectada. Tocá \"Conectar Gmail\" primero."
          : err instanceof Error
            ? err.message
            : "La sincronización falló.";
      Alert.alert("No se pudo sincronizar", message);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>Gmail</Text>
      {connected ? (
        <Text style={styles.connected}>
          Conectado como {connected}
          {status?.last_sync_at ? (
            <Text style={styles.lastSync}> · última sincronización {formatSync(status.last_sync_at)}</Text>
          ) : null}
        </Text>
      ) : knownDisconnected ? (
        <Text style={styles.notConnected}>Conectá Gmail para que la app lea los emails de tu banco.</Text>
      ) : statusLoading ? (
        <Text style={styles.notConnected}>Revisando la conexión con Gmail…</Text>
      ) : statusError ? (
        <Text style={styles.notConnected}>No pudimos revisar la conexión con Gmail. Probá sincronizar igual.</Text>
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
              {connected ? "Reconectar Gmail" : "Conectar Gmail"}
            </Text>
          )}
        </Pressable>
        <Pressable
          style={({ pressed }) => [
            styles.buttonSecondary,
            (pressed || syncing || knownDisconnected) && styles.buttonDim,
          ]}
          // Nothing to sync until Gmail is linked (the backend would 404).
          disabled={syncing || knownDisconnected}
          onPress={handleSync}
        >
          {syncing ? (
            <ActivityIndicator color={colors.textPrimary} />
          ) : (
            <Text style={styles.buttonText}>Sincronizar ahora</Text>
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
  lastSync: { color: colors.textSecondary },
  notConnected: { color: colors.textSecondary, fontSize: 13, marginBottom: 12 },
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

function formatSync(iso: string): string {
  return new Date(iso).toLocaleString("es-CO", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}
