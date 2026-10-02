import BottomSheet, { BottomSheetScrollView, BottomSheetTextInput } from "@gorhom/bottom-sheet";
import { useEffect, useMemo, useRef, useState } from "react";
import { Alert, Keyboard, Pressable, StyleSheet, Text, View } from "react-native";

import {
  useCreateCashExpense,
  useReconcileAccount,
  useUpsertAccount,
  type AccountKind,
} from "../services/queries/accounts";
import { colors } from "../theme/colors";
import { CATEGORIES } from "../utils/categories";
import { formatCOP, parseCOP } from "../utils/currency";

export type AccountSheetMode =
  // First balance, or start over from today's real balance.
  | { mode: "setup"; kind: AccountKind; name: string }
  // Compare with the bank: stores the difference as a visible adjustment.
  | { mode: "reconcile"; kind: AccountKind; name: string; computed: string }
  | { mode: "cash" };

type Props = {
  editing: AccountSheetMode | null;
  onClose: () => void;
};

// Categories that make sense for a cash expense (no system-only ones).
const SPENDABLE = CATEGORIES.filter(
  (c) => !["transfer", "cash_withdrawal", "debt_payment"].includes(c.key),
);

export default function AccountSheet({ editing, onClose }: Props) {
  const sheetRef = useRef<BottomSheet>(null);
  const snapPoints = useMemo(() => ["70%"], []);
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<string | null>(null);

  useEffect(() => {
    setAmount("");
    setDescription("");
    setCategory(null);
    if (editing !== null) sheetRef.current?.expand();
    else sheetRef.current?.close();
  }, [editing]);

  const upsert = useUpsertAccount();
  const reconcile = useReconcileAccount();
  const cash = useCreateCashExpense();
  const busy = upsert.isPending || reconcile.isPending || cash.isPending;

  const onError = (e: unknown) =>
    Alert.alert("Error", e instanceof Error ? e.message : "No se pudo guardar.");

  function handleSave() {
    if (!editing) return;
    const value = parseCOP(amount);
    if (amount.trim() === "" || value < 0) {
      Alert.alert("Monto inválido", "Escribí un monto en pesos.");
      return;
    }
    Keyboard.dismiss();

    if (editing.mode === "setup") {
      upsert.mutate({ kind: editing.kind, openingBalance: value }, { onSuccess: onClose, onError });
      return;
    }
    if (editing.mode === "reconcile") {
      reconcile.mutate(
        { kind: editing.kind, balance: value },
        {
          onSuccess: (r) => {
            const diff = Number(r.difference);
            Alert.alert(
              diff === 0 ? "Todo cuadra" : "Diferencia registrada",
              diff === 0
                ? `${editing.name} coincide con lo que calcula la app.`
                : `La app calculaba ${formatCOP(r.computed_balance)}. ` +
                    `${diff < 0 ? "Faltan" : "Sobran"} ${formatCOP(Math.abs(diff))} ` +
                    "que no llegaron por email. Quedó como ajuste visible.",
            );
            onClose();
          },
          onError,
        },
      );
      return;
    }
    if (value <= 0 || description.trim() === "") {
      Alert.alert("Faltan datos", "Poné el monto y en qué gastaste.");
      return;
    }
    cash.mutate(
      { amount: value.toString(), merchant: description.trim(), category },
      { onSuccess: onClose, onError },
    );
  }

  const title =
    editing?.mode === "setup"
      ? `Saldo de ${editing.name}`
      : editing?.mode === "reconcile"
        ? `Conciliar ${editing.name}`
        : "Gasto en efectivo";
  const hint =
    editing?.mode === "setup"
      ? "Escribí el saldo que ves hoy en el banco (o el efectivo que tenés). Desde ahora la app lo actualiza con cada movimiento."
      : editing?.mode === "reconcile"
        ? `La app calcula ${formatCOP(editing.computed)}. Escribí el saldo real; si no coincide, la diferencia queda registrada.`
        : "Resta del efectivo y cuenta como gasto del mes.";

  return (
    <BottomSheet
      ref={sheetRef}
      index={-1}
      snapPoints={snapPoints}
      enablePanDownToClose
      onClose={onClose}
      backgroundStyle={styles.bg}
      handleIndicatorStyle={styles.handle}
    >
      <BottomSheetScrollView contentContainerStyle={styles.body}>
        <Text style={styles.title}>{title}</Text>
        <Text style={styles.hint}>{hint}</Text>

        <Text style={styles.label}>
          {editing?.mode === "cash" ? "Monto (COP)" : "Saldo real (COP)"}
        </Text>
        <BottomSheetTextInput
          style={styles.input}
          placeholder="0"
          placeholderTextColor={colors.textSecondary}
          value={amount}
          onChangeText={setAmount}
          keyboardType="numeric"
        />

        {editing?.mode === "cash" ? (
          <>
            <Text style={styles.label}>¿En qué?</Text>
            <BottomSheetTextInput
              style={styles.input}
              placeholder="p.ej. Almuerzo"
              placeholderTextColor={colors.textSecondary}
              value={description}
              onChangeText={setDescription}
            />
            <Text style={styles.label}>Categoría</Text>
            <View style={styles.chips}>
              {SPENDABLE.map((c) => (
                <Pressable
                  key={c.key}
                  onPress={() => setCategory(category === c.key ? null : c.key)}
                  style={[styles.chip, category === c.key && styles.chipActive]}
                >
                  <Text style={[styles.chipText, category === c.key && styles.chipTextActive]}>
                    {c.label}
                  </Text>
                </Pressable>
              ))}
            </View>
          </>
        ) : null}

        <Pressable
          style={[styles.saveBtn, busy && { opacity: 0.5 }]}
          disabled={busy}
          onPress={handleSave}
        >
          <Text style={styles.saveText}>{busy ? "Guardando..." : "Guardar"}</Text>
        </Pressable>
      </BottomSheetScrollView>
    </BottomSheet>
  );
}

const styles = StyleSheet.create({
  bg: { backgroundColor: colors.surface },
  handle: { backgroundColor: colors.border },
  body: { padding: 16, paddingBottom: 48 },
  title: { color: colors.textPrimary, fontSize: 16, fontWeight: "600", marginBottom: 6 },
  hint: { color: colors.textSecondary, fontSize: 12, lineHeight: 17, marginBottom: 14 },
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
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 12 },
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
  saveBtn: {
    backgroundColor: colors.primary,
    padding: 14,
    borderRadius: 8,
    alignItems: "center",
    marginTop: 8,
  },
  saveText: { color: "#fff", fontWeight: "600", fontSize: 14 },
});
