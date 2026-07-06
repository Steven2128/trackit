import BottomSheet, { BottomSheetTextInput, BottomSheetView } from "@gorhom/bottom-sheet";
import { useEffect, useMemo, useRef, useState } from "react";
import { Alert, Keyboard, Pressable, StyleSheet, Text, View } from "react-native";

import { useDeleteBudget, useUpsertBudget } from "../services/queries/budgets";
import { colors } from "../theme/colors";
import { getCategory } from "../utils/categories";
import { parseCOP } from "../utils/currency";

type Props = {
  isVisible: boolean;
  category: string | null;
  currentLimit: string | null;
  onClose: () => void;
};

export default function BudgetFormSheet({ isVisible, category, currentLimit, onClose }: Props) {
  const sheetRef = useRef<BottomSheet>(null);
  const snapPoints = useMemo(() => ["45%"], []);
  const [limit, setLimit] = useState("");
  const hasBudget = currentLimit !== null;

  useEffect(() => {
    setLimit(currentLimit ? Number(currentLimit).toString() : "");
  }, [currentLimit, category]);

  useEffect(() => {
    if (isVisible) sheetRef.current?.expand();
    else sheetRef.current?.close();
  }, [isVisible]);

  const upsertMut = useUpsertBudget();
  const deleteMut = useDeleteBudget();
  const busy = upsertMut.isPending || deleteMut.isPending;
  const cat = getCategory(category);

  function handleSave() {
    if (!category) return;
    const amount = parseCOP(limit);
    if (amount <= 0) {
      Alert.alert("Monto inválido", "El límite debe ser mayor a 0.");
      return;
    }
    Keyboard.dismiss();
    upsertMut.mutate(
      { category, monthly_limit: amount.toString() },
      {
        onSuccess: onClose,
        onError: (e) =>
          Alert.alert("Error", e instanceof Error ? e.message : "Error al guardar."),
      },
    );
  }

  function handleDelete() {
    if (!category) return;
    Alert.alert("Quitar presupuesto", `¿Quitar el límite de ${cat.label}?`, [
      { text: "Cancelar", style: "cancel" },
      {
        text: "Quitar",
        style: "destructive",
        onPress: () =>
          deleteMut.mutate(category, {
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
        <Text style={styles.title}>Presupuesto · {cat.label}</Text>

        <View style={styles.field}>
          <Text style={styles.label}>Límite mensual (COP)</Text>
          <BottomSheetTextInput
            style={styles.input}
            placeholder="0"
            placeholderTextColor={colors.textSecondary}
            value={limit}
            onChangeText={setLimit}
            keyboardType="numeric"
            autoFocus
          />
        </View>

        <Pressable
          style={[styles.saveBtn, busy && { opacity: 0.5 }]}
          disabled={busy}
          onPress={handleSave}
        >
          <Text style={styles.saveText}>{busy ? "Guardando..." : "Guardar"}</Text>
        </Pressable>

        {hasBudget ? (
          <Pressable style={styles.deleteBtn} disabled={busy} onPress={handleDelete}>
            <Text style={styles.deleteText}>Quitar presupuesto</Text>
          </Pressable>
        ) : null}
      </BottomSheetView>
    </BottomSheet>
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
