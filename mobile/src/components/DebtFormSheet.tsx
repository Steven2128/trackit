import BottomSheet, { BottomSheetTextInput, BottomSheetView } from "@gorhom/bottom-sheet";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Keyboard,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import type { DebtOut, DebtPayload } from "../services/queries/debts";
import {
  useCreateDebt,
  useDeleteDebt,
  useUpdateDebt,
} from "../services/queries/debts";
import { colors } from "../theme/colors";
import { parseCOP } from "../utils/currency";

type Props = {
  isVisible: boolean;
  debt?: DebtOut;
  onClose: () => void;
};

type FormState = {
  bank: string;
  amount: string;
  rate: string;
  min: string;
};

const EMPTY: FormState = { bank: "", amount: "", rate: "", min: "" };

function fromDebt(d?: DebtOut): FormState {
  if (!d) return EMPTY;
  return {
    bank: d.bank_name,
    amount: d.total_amount ? Number(d.total_amount).toString() : "",
    rate: d.interest_rate ? Number(d.interest_rate).toString() : "",
    min: d.minimum_payment ? Number(d.minimum_payment).toString() : "",
  };
}

export default function DebtFormSheet({ isVisible, debt, onClose }: Props) {
  const sheetRef = useRef<BottomSheet>(null);
  const snapPoints = useMemo(() => ["80%"], []);
  const [form, setForm] = useState<FormState>(fromDebt(debt));
  const isEdit = !!debt;

  useEffect(() => {
    setForm(fromDebt(debt));
  }, [debt]);

  useEffect(() => {
    if (isVisible) sheetRef.current?.expand();
    else sheetRef.current?.close();
  }, [isVisible]);

  const createMut = useCreateDebt();
  const updateMut = useUpdateDebt();
  const deleteMut = useDeleteDebt();
  const busy = createMut.isPending || updateMut.isPending || deleteMut.isPending;

  function buildPayload(): DebtPayload | null {
    const bank = form.bank.trim();
    const amount = parseCOP(form.amount);
    if (bank.length === 0) {
      Alert.alert("Falta el banco", "El nombre del banco es obligatorio.");
      return null;
    }
    if (amount <= 0) {
      Alert.alert("Monto inválido", "El monto debe ser mayor a 0.");
      return null;
    }
    const rate = form.rate.trim() === "" ? null : Number(form.rate.replace(",", "."));
    const min = form.min.trim() === "" ? null : parseCOP(form.min);
    return {
      bank_name: bank,
      total_amount: amount.toString(),
      interest_rate: rate !== null && !Number.isNaN(rate) ? rate.toString() : null,
      minimum_payment: min !== null ? min.toString() : null,
    };
  }

  function handleSave() {
    const payload = buildPayload();
    if (!payload) return;
    Keyboard.dismiss();
    const onError = (e: unknown) => {
      const message = e instanceof Error ? e.message : "Error al guardar.";
      Alert.alert("Error", message);
    };
    if (isEdit && debt) {
      updateMut.mutate(
        { id: debt.id, payload },
        { onSuccess: onClose, onError },
      );
    } else {
      createMut.mutate(payload, { onSuccess: onClose, onError });
    }
  }

  function handleDelete() {
    if (!debt) return;
    Alert.alert(
      "Eliminar deuda",
      `¿Eliminar la deuda con ${debt.bank_name}?`,
      [
        { text: "Cancelar", style: "cancel" },
        {
          text: "Eliminar",
          style: "destructive",
          onPress: () =>
            deleteMut.mutate(debt.id, {
              onSuccess: onClose,
              onError: (e) =>
                Alert.alert("Error", e instanceof Error ? e.message : "Error al eliminar."),
            }),
        },
      ],
    );
  }

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
      <BottomSheetView style={styles.body}>
        <Text style={styles.title}>{isEdit ? "Editar deuda" : "Nueva deuda"}</Text>

        <Field label="Banco / Entidad">
          <BottomSheetTextInput
            style={styles.input}
            placeholder="p.ej. Falabella"
            placeholderTextColor={colors.textSecondary}
            value={form.bank}
            onChangeText={(v) => setForm((f) => ({ ...f, bank: v }))}
            autoCapitalize="words"
          />
        </Field>

        <Field label="Monto total (COP)">
          <BottomSheetTextInput
            style={styles.input}
            placeholder="0"
            placeholderTextColor={colors.textSecondary}
            value={form.amount}
            onChangeText={(v) => setForm((f) => ({ ...f, amount: v }))}
            keyboardType="numeric"
          />
        </Field>

        <Field label="Tasa interés % EA">
          <BottomSheetTextInput
            style={styles.input}
            placeholder="0"
            placeholderTextColor={colors.textSecondary}
            value={form.rate}
            onChangeText={(v) => setForm((f) => ({ ...f, rate: v }))}
            keyboardType="decimal-pad"
          />
        </Field>

        <Field label="Pago mínimo mensual (COP)">
          <BottomSheetTextInput
            style={styles.input}
            placeholder="0"
            placeholderTextColor={colors.textSecondary}
            value={form.min}
            onChangeText={(v) => setForm((f) => ({ ...f, min: v }))}
            keyboardType="numeric"
          />
        </Field>

        <Pressable
          style={[styles.saveBtn, busy && { opacity: 0.5 }]}
          disabled={busy}
          onPress={handleSave}
        >
          <Text style={styles.saveText}>{busy ? "Guardando..." : "Guardar"}</Text>
        </Pressable>

        {isEdit ? (
          <Pressable style={styles.deleteBtn} disabled={busy} onPress={handleDelete}>
            <Text style={styles.deleteText}>Eliminar deuda</Text>
          </Pressable>
        ) : null}
      </BottomSheetView>
    </BottomSheet>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  bg: { backgroundColor: colors.surface },
  handle: { backgroundColor: colors.border },
  body: { padding: 16, gap: 4 },
  title: { color: colors.textPrimary, fontSize: 16, fontWeight: "600", marginBottom: 8 },
  field: { marginBottom: 12 },
  label: {
    color: colors.textSecondary,
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  input: {
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    padding: 12,
    fontSize: 14,
    color: colors.textPrimary,
  },
  saveBtn: {
    backgroundColor: colors.primary,
    padding: 14,
    borderRadius: 8,
    alignItems: "center",
    marginTop: 8,
  },
  saveText: { color: "#fff", fontWeight: "600", fontSize: 14 },
  deleteBtn: {
    borderWidth: 1,
    borderColor: colors.danger,
    padding: 12,
    borderRadius: 8,
    alignItems: "center",
    marginTop: 12,
  },
  deleteText: { color: colors.danger, fontWeight: "600", fontSize: 13 },
});
