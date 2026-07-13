import BottomSheet, { BottomSheetTextInput, BottomSheetView } from "@gorhom/bottom-sheet";
import { useEffect, useMemo, useRef, useState } from "react";
import { Alert, Keyboard, Pressable, StyleSheet, Text, View } from "react-native";

import {
  useCreateGoal,
  useDeleteGoal,
  useUpdateGoal,
  type SavingsGoalOut,
  type SavingsGoalPayload,
} from "../services/queries/goals";
import { colors } from "../theme/colors";
import { parseCOP } from "../utils/currency";

type Props = {
  isVisible: boolean;
  goal?: SavingsGoalOut;
  onClose: () => void;
};

type FormState = {
  name: string;
  target: string;
  current: string;
  date: string; // YYYY-MM-DD or empty
};

const EMPTY: FormState = { name: "", target: "", current: "", date: "" };

function fromGoal(g?: SavingsGoalOut): FormState {
  if (!g) return EMPTY;
  return {
    name: g.name,
    target: g.target_amount ? Number(g.target_amount).toString() : "",
    current: g.current_amount ? Number(g.current_amount).toString() : "",
    date: g.target_date ?? "",
  };
}

export default function GoalFormSheet({ isVisible, goal, onClose }: Props) {
  const sheetRef = useRef<BottomSheet>(null);
  const snapPoints = useMemo(() => ["80%"], []);
  const [form, setForm] = useState<FormState>(fromGoal(goal));
  const isEdit = !!goal;

  useEffect(() => {
    setForm(fromGoal(goal));
  }, [goal]);

  useEffect(() => {
    if (isVisible) sheetRef.current?.expand();
    else sheetRef.current?.close();
  }, [isVisible]);

  const createMut = useCreateGoal();
  const updateMut = useUpdateGoal();
  const deleteMut = useDeleteGoal();
  const busy = createMut.isPending || updateMut.isPending || deleteMut.isPending;

  function buildPayload(): SavingsGoalPayload | null {
    const name = form.name.trim();
    const target = parseCOP(form.target);
    if (name.length === 0) {
      Alert.alert("Falta el nombre", "Ponele un nombre a la meta.");
      return null;
    }
    if (target <= 0) {
      Alert.alert("Monto inválido", "El monto objetivo debe ser mayor a 0.");
      return null;
    }
    const date = form.date.trim();
    if (date !== "" && !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
      Alert.alert("Fecha inválida", "Usá el formato AAAA-MM-DD, p.ej. 2026-12-31.");
      return null;
    }
    const current = form.current.trim() === "" ? 0 : parseCOP(form.current);
    return {
      name,
      target_amount: target.toString(),
      current_amount: current.toString(),
      target_date: date === "" ? null : date,
    };
  }

  function handleSave() {
    const payload = buildPayload();
    if (!payload) return;
    Keyboard.dismiss();
    const onError = (e: unknown) => {
      Alert.alert("Error", e instanceof Error ? e.message : "Error al guardar.");
    };
    if (isEdit && goal) {
      updateMut.mutate({ id: goal.id, payload }, { onSuccess: onClose, onError });
    } else {
      createMut.mutate(payload, { onSuccess: onClose, onError });
    }
  }

  function handleDelete() {
    if (!goal) return;
    Alert.alert("Eliminar meta", `¿Eliminar "${goal.name}"?`, [
      { text: "Cancelar", style: "cancel" },
      {
        text: "Eliminar",
        style: "destructive",
        onPress: () =>
          deleteMut.mutate(goal.id, {
            onSuccess: onClose,
            onError: (e) =>
              Alert.alert("Error", e instanceof Error ? e.message : "Error al eliminar."),
          }),
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
        <Text style={styles.title}>{isEdit ? "Editar meta" : "Nueva meta"}</Text>

        <Field label="Nombre">
          <BottomSheetTextInput
            style={styles.input}
            placeholder="p.ej. Fondo de emergencia"
            placeholderTextColor={colors.textSecondary}
            value={form.name}
            onChangeText={(v) => setForm((f) => ({ ...f, name: v }))}
            autoCapitalize="sentences"
          />
        </Field>

        <Field label="Monto objetivo (COP)">
          <BottomSheetTextInput
            style={styles.input}
            placeholder="0"
            placeholderTextColor={colors.textSecondary}
            value={form.target}
            onChangeText={(v) => setForm((f) => ({ ...f, target: v }))}
            keyboardType="numeric"
          />
        </Field>

        <Field label="Ahorrado hasta ahora (COP)">
          <BottomSheetTextInput
            style={styles.input}
            placeholder="0"
            placeholderTextColor={colors.textSecondary}
            value={form.current}
            onChangeText={(v) => setForm((f) => ({ ...f, current: v }))}
            keyboardType="numeric"
          />
        </Field>

        <Field label="Fecha objetivo (AAAA-MM-DD, opcional)">
          <BottomSheetTextInput
            style={styles.input}
            placeholder="2026-12-31"
            placeholderTextColor={colors.textSecondary}
            value={form.date}
            onChangeText={(v) => setForm((f) => ({ ...f, date: v }))}
            autoCapitalize="none"
          />
        </Field>

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
            <Text style={styles.deleteText}>Eliminar meta</Text>
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
