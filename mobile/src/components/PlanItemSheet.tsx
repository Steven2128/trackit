import BottomSheet, { BottomSheetTextInput, BottomSheetView } from "./sheet";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Keyboard,
  Pressable,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";

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
import { formatCOPInput, parseCOP, toCOPInput } from "../utils/currency";
import { Alert } from "../utils/alert";
import { dmyToIso, isoToDmy } from "../utils/dates";
import { useWebSheet } from "./useWebSheet";

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
  oneOff: boolean; // due once on `date` (a debt with a friend)
  date: string; // DD/MM/AAAA
};

function fromEditing(editing: PlanItemEditing | null): FormState {
  if (!editing?.item)
    return { name: "", amount: "", day: "", grace: "0", isDebt: false, oneOff: false, date: "" };
  if (editing.kind === "income") {
    const i = editing.item;
    return {
      name: i.name,
      amount: toCOPInput(i.amount),
      day: String(i.expected_day),
      grace: "0",
      isDebt: false,
      oneOff: false,
      date: "",
    };
  }
  const p = editing.item;
  return {
    name: p.name,
    amount: toCOPInput(p.amount),
    day: p.due_day !== null ? String(p.due_day) : "",
    grace: String(p.grace_days),
    isDebt: p.is_debt_payment,
    oneOff: p.due_date !== null,
    date: p.due_date ? isoToDmy(p.due_date) : "",
  };
}

export default function PlanItemSheet({ editing, onClose }: Props) {
  const sheetRef = useRef<BottomSheet>(null);
  const sheet = useWebSheet(editing !== null);
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

  function validate(): {
    name: string;
    amount: number;
    day: number | null;
    grace: number;
    date: string | null;
  } | null {
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
    if (!isIncome && form.oneOff) {
      const date = dmyToIso(form.date);
      if (date === null) {
        Alert.alert("Fecha inválida", "Escribí la fecha como DD/MM/AAAA, por ejemplo 25/10/2026.");
        return null;
      }
      return { name, amount, day: null, grace: 0, date };
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
    return { name, amount, day, grace, date: null };
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
        due_date: values.date,
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

  if (!sheet.mounted) return null;

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
            onChangeText={(v) => setForm((f) => ({ ...f, amount: formatCOPInput(v) }))}
            keyboardType="numeric"
          />
        </Field>

        {!isIncome ? (
          <View style={styles.switchRow}>
            <Text style={styles.switchLabel}>Una sola vez (no se repite cada mes)</Text>
            <Switch
              value={form.oneOff}
              onValueChange={(v) => setForm((f) => ({ ...f, oneOff: v }))}
              trackColor={{ false: colors.surfaceMuted, true: colors.primaryDim }}
              thumbColor={form.oneOff ? colors.primary : colors.textSecondary}
            />
          </View>
        ) : null}

        {!isIncome && form.oneOff ? (
          <Field label="Fecha en que lo pagás (DD/MM/AAAA)">
            <BottomSheetTextInput
              style={styles.input}
              placeholder="25/10/2026"
              placeholderTextColor={colors.textSecondary}
              value={form.date}
              onChangeText={(v) => setForm((f) => ({ ...f, date: v }))}
              keyboardType="numbers-and-punctuation"
              maxLength={10}
            />
          </Field>
        ) : (
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
        )}

        {!isIncome && !form.oneOff ? (
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
