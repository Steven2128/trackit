import BottomSheet, { BottomSheetTextInput, BottomSheetView } from "@gorhom/bottom-sheet";
import { useEffect, useMemo, useRef, useState } from "react";
import { Alert, Keyboard, Pressable, StyleSheet, Switch, Text, View } from "react-native";

import {
  useCreateIncomeSource,
  useCreatePlannedPayment,
  useDeleteIncomeSource,
  useDeletePlannedPayment,
  useUpdateIncomeSource,
  useUpdatePlannedPayment,
  type IncomeSourceOut,
  type PlannedPaymentOut,
} from "../services/queries/plan";
import { colors } from "../theme/colors";
import { parseCOP } from "../utils/currency";

export type PlanItemEditing =
  | { kind: "income"; item?: IncomeSourceOut }
  | { kind: "payment"; item?: PlannedPaymentOut };

type Props = {
  editing: PlanItemEditing | null;
  onClose: () => void;
};

type FormState = {
  name: string;
  amount: string;
  day: string;
  grace: string;
  isDebt: boolean;
};

function fromEditing(editing: PlanItemEditing | null): FormState {
  if (!editing?.item) return { name: "", amount: "", day: "", grace: "0", isDebt: false };
  if (editing.kind === "income") {
    const i = editing.item;
    return {
      name: i.name,
      amount: Number(i.amount).toString(),
      day: String(i.expected_day),
      grace: "0",
      isDebt: false,
    };
  }
  const p = editing.item;
  return {
    name: p.name,
    amount: Number(p.amount).toString(),
    day: p.due_day !== null ? String(p.due_day) : "",
    grace: String(p.grace_days),
    isDebt: p.is_debt_payment,
  };
}

export default function PlanItemSheet({ editing, onClose }: Props) {
  const sheetRef = useRef<BottomSheet>(null);
  const snapPoints = useMemo(() => ["80%"], []);
  const [form, setForm] = useState<FormState>(fromEditing(editing));

  useEffect(() => {
    setForm(fromEditing(editing));
  }, [editing]);

  useEffect(() => {
    if (editing !== null) sheetRef.current?.expand();
    else sheetRef.current?.close();
  }, [editing]);

  const createIncome = useCreateIncomeSource();
  const updateIncome = useUpdateIncomeSource();
  const deleteIncome = useDeleteIncomeSource();
  const createPayment = useCreatePlannedPayment();
  const updatePayment = useUpdatePlannedPayment();
  const deletePayment = useDeletePlannedPayment();
  const busy =
    createIncome.isPending ||
    updateIncome.isPending ||
    deleteIncome.isPending ||
    createPayment.isPending ||
    updatePayment.isPending ||
    deletePayment.isPending;

  if (editing === null && !busy) {
    // Sheet closed; render collapsed instance so animations still work.
  }

  const isIncome = editing?.kind === "income";
  const isEdit = !!editing?.item;

  function validate(): { name: string; amount: number; day: number | null; grace: number } | null {
    const name = form.name.trim();
    const amount = parseCOP(form.amount);
    if (name.length === 0) {
      Alert.alert("Falta el nombre", "Ponele un nombre.");
      return null;
    }
    if (amount <= 0) {
      Alert.alert("Monto inválido", "El monto debe ser mayor a 0.");
      return null;
    }
    const dayRaw = form.day.trim();
    let day: number | null = null;
    if (dayRaw !== "") {
      day = Number(dayRaw);
      if (!Number.isInteger(day) || day < 1 || day > 31) {
        Alert.alert("Día inválido", "El día debe estar entre 1 y 31.");
        return null;
      }
    }
    if (isIncome && day === null) {
      Alert.alert("Falta el día", "Indicá el día del mes en que te cae este ingreso.");
      return null;
    }
    const grace = form.grace.trim() === "" ? 0 : Number(form.grace);
    if (!Number.isInteger(grace) || grace < 0 || grace > 60) {
      Alert.alert("Plazo inválido", "Los días de plazo deben estar entre 0 y 60.");
      return null;
    }
    return { name, amount, day, grace };
  }

  function handleSave() {
    if (!editing) return;
    const values = validate();
    if (!values) return;
    Keyboard.dismiss();
    const onError = (e: unknown) =>
      Alert.alert("Error", e instanceof Error ? e.message : "Error al guardar.");

    if (editing.kind === "income") {
      const payload = {
        name: values.name,
        amount: values.amount.toString(),
        expected_day: values.day as number,
      };
      if (editing.item) {
        updateIncome.mutate({ id: editing.item.id, payload }, { onSuccess: onClose, onError });
      } else {
        createIncome.mutate(payload, { onSuccess: onClose, onError });
      }
    } else {
      const payload = {
        name: values.name,
        amount: values.amount.toString(),
        due_day: values.day,
        grace_days: values.grace,
        is_debt_payment: form.isDebt,
      };
      if (editing.item) {
        updatePayment.mutate({ id: editing.item.id, payload }, { onSuccess: onClose, onError });
      } else {
        createPayment.mutate(payload, { onSuccess: onClose, onError });
      }
    }
  }

  function handleDelete() {
    if (!editing?.item) return;
    const { kind, item } = editing;
    Alert.alert("Eliminar", `¿Eliminar "${item.name}"?`, [
      { text: "Cancelar", style: "cancel" },
      {
        text: "Eliminar",
        style: "destructive",
        onPress: () => {
          const onError = (e: unknown) =>
            Alert.alert("Error", e instanceof Error ? e.message : "Error al eliminar.");
          if (kind === "income") {
            deleteIncome.mutate(item.id, { onSuccess: onClose, onError });
          } else {
            deletePayment.mutate(item.id, { onSuccess: onClose, onError });
          }
        },
      },
    ]);
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
        <Text style={styles.title}>
          {isIncome
            ? isEdit
              ? "Editar ingreso"
              : "Nuevo ingreso"
            : isEdit
              ? "Editar pago fijo"
              : "Nuevo pago fijo"}
        </Text>

        <Field label="Nombre">
          <BottomSheetTextInput
            style={styles.input}
            placeholder={isIncome ? "p.ej. Quincena del 20" : "p.ej. Arriendo"}
            placeholderTextColor={colors.textSecondary}
            value={form.name}
            onChangeText={(v) => setForm((f) => ({ ...f, name: v }))}
            autoCapitalize="sentences"
          />
        </Field>

        <Field label="Monto (COP)">
          <BottomSheetTextInput
            style={styles.input}
            placeholder="0"
            placeholderTextColor={colors.textSecondary}
            value={form.amount}
            onChangeText={(v) => setForm((f) => ({ ...f, amount: v }))}
            keyboardType="numeric"
          />
        </Field>

        <Field label={isIncome ? "Día del mes en que cae" : "Día de corte (opcional)"}>
          <BottomSheetTextInput
            style={styles.input}
            placeholder={isIncome ? "20" : "24"}
            placeholderTextColor={colors.textSecondary}
            value={form.day}
            onChangeText={(v) => setForm((f) => ({ ...f, day: v }))}
            keyboardType="numeric"
          />
        </Field>

        {!isIncome ? (
          <>
            <Field label="Días de plazo después del corte">
              <BottomSheetTextInput
                style={styles.input}
                placeholder="0"
                placeholderTextColor={colors.textSecondary}
                value={form.grace}
                onChangeText={(v) => setForm((f) => ({ ...f, grace: v }))}
                keyboardType="numeric"
              />
            </Field>
            <View style={styles.switchRow}>
              <Text style={styles.switchLabel}>Es pago de deuda (va primero)</Text>
              <Switch
                value={form.isDebt}
                onValueChange={(v) => setForm((f) => ({ ...f, isDebt: v }))}
                trackColor={{ false: colors.surfaceMuted, true: colors.primaryDim }}
                thumbColor={form.isDebt ? colors.primary : colors.textSecondary}
              />
            </View>
          </>
        ) : null}

        <Pressable
          style={({ pressed }) => [styles.saveBtn, (busy || pressed) && { opacity: 0.7 }]}
          disabled={busy}
          onPress={handleSave}
        >
          <Text style={styles.saveText}>{busy ? "Guardando..." : "Guardar"}</Text>
        </Pressable>

        {isEdit ? (
          <Pressable
            style={({ pressed }) => [styles.deleteBtn, pressed && { opacity: 0.7 }]}
            disabled={busy}
            onPress={handleDelete}
          >
            <Text style={styles.deleteText}>Eliminar</Text>
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
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.6,
    marginBottom: 6,
  },
  input: {
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    padding: 12,
    fontSize: 15,
    color: colors.textPrimary,
  },
  switchRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 12,
  },
  switchLabel: { color: colors.textPrimary, fontSize: 14, flex: 1 },
  saveBtn: {
    backgroundColor: colors.primary,
    padding: 14,
    borderRadius: 10,
    alignItems: "center",
    marginTop: 8,
  },
  saveText: { color: "#fff", fontWeight: "600", fontSize: 14 },
  deleteBtn: {
    borderWidth: 1,
    borderColor: colors.danger,
    padding: 12,
    borderRadius: 10,
    alignItems: "center",
    marginTop: 12,
  },
  deleteText: { color: colors.danger, fontWeight: "600", fontSize: 13 },
});
