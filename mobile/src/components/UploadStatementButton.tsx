import { Ionicons } from "@expo/vector-icons";
import { ActivityIndicator, Pressable, StyleSheet, Text } from "react-native";

import { useUploadStatement } from "../services/queries/cards";
import { colors } from "../theme/colors";
import { Alert } from "../utils/alert";
import { formatCOP } from "../utils/currency";
import { isoToDmy } from "../utils/dates";
import { canPickPdf, pickPdf } from "../utils/pickPdf";

type Props = { debtId: string; label?: string };

/** Uploads a card statement PDF the user downloaded from the bank (Banco
 * de Bogotá doesn't email it). The backend reads it like an emailed one. */
export default function UploadStatementButton({ debtId, label = "Subir extracto (PDF)" }: Props) {
  const upload = useUploadStatement();

  async function handlePress() {
    if (upload.isPending) return;
    if (!canPickPdf) {
      Alert.alert("Desde la web", "Por ahora el extracto se sube desde la app web.");
      return;
    }
    const file = await pickPdf();
    if (!file) return;
    upload.mutate(
      { debtId, file },
      {
        onSuccess: (r) => {
          const lines = [
            `Corte ${isoToDmy(r.period_end)}.`,
            r.minimum_payment ? `Pago mínimo ${formatCOP(r.minimum_payment)}` : null,
            r.due_date ? `hasta el ${isoToDmy(r.due_date)}.` : null,
            `Saldo actualizado: ${formatCOP(r.balance)}.`,
            r.purchases_added
              ? `${r.purchases_added} compra${r.purchases_added === 1 ? "" : "s"} nueva${r.purchases_added === 1 ? "" : "s"} agregada${r.purchases_added === 1 ? "" : "s"} a Movimientos.`
              : null,
          ];
          Alert.alert("Extracto leído", lines.filter(Boolean).join(" "));
        },
        onError: (e) => {
          const status = (e as { response?: { status?: number } }).response?.status;
          Alert.alert(
            "No se pudo leer",
            status === 422
              ? "Ese PDF no parece un extracto de tarjeta que sepamos leer (Banco de Bogotá o RappiCard)."
              : e instanceof Error
                ? e.message
                : "Probá de nuevo.",
          );
        },
      },
    );
  }

  return (
    <Pressable
      onPress={handlePress}
      style={({ pressed }) => [styles.btn, pressed && styles.pressed]}
      accessibilityRole="button"
      disabled={upload.isPending}
    >
      {upload.isPending ? (
        <ActivityIndicator size="small" color={colors.primary} />
      ) : (
        <Ionicons name="document-attach-outline" size={16} color={colors.primary} />
      )}
      <Text style={styles.text}>{upload.isPending ? "Leyendo extracto…" : label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  btn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    borderWidth: 1,
    borderColor: colors.primary,
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 14,
  },
  pressed: { opacity: 0.7 },
  text: { color: colors.primary, fontSize: 14, fontWeight: "600" },
});
