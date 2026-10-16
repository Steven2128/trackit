import * as Linking from "expo-linking";
import * as WebBrowser from "expo-web-browser";
import { useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { api } from "../services/api";
import { isWeb, redirectTo, webReturnUrl } from "../services/webAuth";
import { colors } from "../theme/colors";
import { Alert } from "../utils/alert";

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
        setConnected(email);
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

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Conectar Gmail</Text>
      <Text style={styles.subtitle}>
        Autorizá a TrackIt a leer los emails de notificación de tu banco. Solo
        pedimos acceso de lectura y guardamos los tokens cifrados.
      </Text>

      {connected ? (
        <Text style={styles.connected}>Conectado como {connected}</Text>
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
            {connected ? "Reconectar Gmail" : "Conectar Gmail"}
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
