import BottomSheet, { BottomSheetTextInput, BottomSheetView } from "./sheet";
import { useEffect, useMemo, useRef, useState } from "react";
import { Keyboard, Pressable, StyleSheet, Text, View } from "react-native";

import {
  parseRef,
  plainName,
  useObligationPayments,
  useRecordObligationPayment,
  useUndoObligationPayment,
  type ObligationPayment,
  type PositionLine,
} from "../services/queries/cashPosition";
import { colors } from "../theme/colors";
import { Alert } from "../utils/alert";
import { formatCOP, formatCOPInput, parseCOP, toCOPInput } from "../utils/currency";
import { formatIsoDay, localIsoDate } from "../utils/dates";
import ExpenseDayPicker from "./ExpenseDayPicker";
import { useWebSheet } from "./useWebSheet";

type Props = {
  line: PositionLine | null;
  onClose: () => void;
};

/** Mark money put toward one due date: all of it, part of it, or ahead.
 *  Cash payments also log the cash expense (the balance must drop with
 *  them); bank ones arrive by email, here they're only marked as paid. */
export default function PayObligationSheet({ line, onClose }: Props) {
  const sheetRef = useRef<BottomSheet>(null);
  const sheet = useWebSheet(line !== null);
  const snapPoints = useMemo(() => ["70%"], []);
  const record = useRecordObligationPayment();
  const undo = useUndoObligationPayment();
  const recorded = useObligationPayments(line?.ref ?? null);
  const [amount, setAmount] = useState("");
  const [fromCash, setFromCash] = useState(false);
  const [daysAgo, setDaysAgo] = useState(0);

  useEffect(() => {
    setAmount(line ? toCOPInput(line.amount) : "");
    setFromCash(false);
    setDaysAgo(0);
    if (line !== null) sheetRef.current?.expand();
    else sheetRef.current?.close();
  }, [line]);

  function handleSave() {
    const target = parseRef(line?.ref ?? null);
    if (!line || !target) return;
    const value = parseCOP(amount);
    if (value <= 0) {
      Alert.alert("Monto inválido", "Escribí cuánto pagaste.");
      return;
    }
    Keyboard.dismiss();
    record.mutate(
      {
        ...(target.kind === "planned"
          ? { planned_payment_id: target.id }
          : { debt_id: target.id }),
        due_date: target.due,
        amount: value.toString(),
        paid_on: localIsoDate(daysAgo),
        from_cash: fromCash,
      },
      {
        onSuccess: onClose,
        onError: (e) =>
          Alert.alert("Error", e instanceof Error ? e.message : "No se pudo registrar el pago."),
      },
    );
  }

  function handleUndo(p: ObligationPayment) {
    Alert.alert(
      "Deshacer pago",
      `Se borra el pago de ${formatCOP(p.amount)} del ${formatIsoDay(p.paid_on)}` +
        (p.transaction_id ? " y el gasto en efectivo que generó." : "."),
      [
        { text: "Cancelar", style: "cancel" },
        {
          text: "Deshacer",
          style: "destructive",
          onPress: () =>
            undo.mutate(p.id, {
              onError: (e) =>
                Alert.alert("Error", e instanceof Error ? e.message : "No se pudo deshacer."),
            }),
        },
      ],
    );
  }

  if (!sheet.mounted) return null;
  const paid = line ? Number(line.total) - Number(line.amount) : 0;
  const done = line !== null && Number(line.amount) === 0;
  const payments = recorded.data ?? [];

  return (
    <BottomSheet
      ref={sheetRef}
      index={-1}
      snapPoints={snapPoints}
      enablePanDownToClose
      onClose={onClose}
      backgroundStyle={styles.bg}
      handleIndicatorStyle={styles.handle}
      {...sheet.props}
    >
      <BottomSheetView style={styles.body}>
        <Text style={styles.title}>
          {done ? "Pagado" : "Pagar"} · {line ? plainName(line.name) : ""}
        </Text>
        {line ? (
          <Text style={styles.hint}>
            {line.due ? `Vence el ${formatIsoDay(line.due)}. ` : ""}
            {done
              ? `Ya pagaste los ${formatCOP(line.total)}.`
              : paid > 0
                ? `Ya pagaste ${formatCOP(paid)} de ${formatCOP(line.total)}; faltan ${formatCOP(line.amount)}.`
                : `Son ${formatCOP(line.total)}.`}
            {done ? "" : " Si pagás una parte, lo que falte sigue apartado."}
          </Text>
        ) : null}

        {payments.length > 0 ? (
          <>
            <Text style={styles.label}>Pagos registrados</Text>
            {payments.map((p) => (
              <View key={p.id} style={styles.recordRow}>
                <Text style={styles.recordText}>
                  {formatCOP(p.amount)} · {formatIsoDay(p.paid_on)}
                  {p.transaction_id ? " · efectivo" : ""}
                </Text>
                <Pressable
                  onPress={() => handleUndo(p)}
                  disabled={undo.isPending}
                  style={({ pressed }) => [
                    styles.undoBtn,
                    (pressed || undo.isPending) && { opacity: 0.5 },
                  ]}
                >
                  <Text style={styles.undoText}>Deshacer</Text>
                </Pressable>
              </View>
            ))}
          </>
        ) : paid > 0 && !recorded.isLoading ? (
          <Text style={styles.small}>
            Lo marcaste como pagado desde el Plan del mes; desmarcalo ahí para deshacerlo.
          </Text>
        ) : null}

        {done ? null : (
          <>
            <Text style={styles.label}>Cuánto pagaste (COP)</Text>
            <BottomSheetTextInput
              style={styles.input}
              placeholder="0"
              placeholderTextColor={colors.textSecondary}
              value={amount}
              onChangeText={(v) => setAmount(formatCOPInput(v))}
              keyboardType="numeric"
            />

            <Text style={styles.label}>¿Con qué?</Text>
            <View style={styles.chips}>
              {[
                { cash: false, label: "Banco o Nequi" },
                { cash: true, label: "Efectivo" },
              ].map((o) => (
                <Pressable
                  key={o.label}
                  onPress={() => setFromCash(o.cash)}
                  style={[
                    styles.chip,
                    fromCash === o.cash && styles.chipActive,
                  ]}
                >
                  <Text
                    style={[
                      styles.chipText,
                      fromCash === o.cash && styles.chipTextActive,
                    ]}
                  >
                    {o.label}
                  </Text>
                </Pressable>
              ))}
            </View>
            <Text style={styles.small}>
              {fromCash
                ? "También lo resto de tu efectivo."
                : "El movimiento del banco llega solo por email; acá solo lo marcás como pagado."}
            </Text>

            <Text style={styles.label}>¿Cuándo?</Text>
            <ExpenseDayPicker
              daysAgo={daysAgo}
              onChange={setDaysAgo}
              cashNotice={fromCash}
            />

            <Pressable
              style={[styles.saveBtn, record.isPending && { opacity: 0.5 }]}
              disabled={record.isPending}
              onPress={handleSave}
            >
              <Text style={styles.saveText}>
                {record.isPending ? "Guardando..." : "Registrar pago"}
              </Text>
            </Pressable>
          </>
        )}
      </BottomSheetView>
    </BottomSheet>
  );
}

const styles = StyleSheet.create({
  bg: { backgroundColor: colors.surface },
  handle: { backgroundColor: colors.border },
  body: { padding: 16, paddingBottom: 32 },
  title: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: "600",
    marginBottom: 6,
  },
  hint: {
    color: colors.textSecondary,
    fontSize: 12,
    lineHeight: 17,
    marginBottom: 14,
  },
  label: {
    color: colors.textSecondary,
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 6,
    marginTop: 4,
  },
  input: {
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    padding: 12,
    fontSize: 14,
    color: colors.textPrimary,
    marginBottom: 10,
  },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 6 },
  chip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { color: colors.textSecondary, fontSize: 13, fontWeight: "600" },
  chipTextActive: { color: "#fff" },
  small: { color: colors.textSecondary, fontSize: 11, marginBottom: 10 },
  saveBtn: {
    backgroundColor: colors.primary,
    padding: 14,
    borderRadius: 8,
    alignItems: "center",
    marginTop: 8,
  },
  saveText: { color: "#fff", fontWeight: "600", fontSize: 14 },
  recordRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 8,
  },
  recordText: { color: colors.textPrimary, fontSize: 13 },
  undoBtn: {
    borderWidth: 1,
    borderColor: colors.danger,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  undoText: { color: colors.danger, fontSize: 12, fontWeight: "700" },
});
