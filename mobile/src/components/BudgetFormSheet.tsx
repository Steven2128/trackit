import BottomSheet, { BottomSheetTextInput, BottomSheetView } from "@gorhom/bottom-sheet";
import { useEffect, useMemo, useRef, useState } from "react";
import { Alert, Keyboard, Pressable, StyleSheet, Text, View } from "react-native";

import { useDeleteBudget, useRenameBudget, useUpsertBudget } from "../services/queries/budgets";
import { colors } from "../theme/colors";
import { getCategory, slugifyCategory, CATEGORIES } from "../utils/categories";
import { parseCOP } from "../utils/currency";

type Props = {
  isVisible: boolean;
  // null + createCustom → "new custom category" mode with a name input.
  category: string | null;
  currentLimit: string | null;
  createCustom?: boolean;
  onClose: () => void;
};

export default function BudgetFormSheet({
  isVisible,
  category,
  currentLimit,
  createCustom = false,
  onClose,
}: Props) {
  const sheetRef = useRef<BottomSheet>(null);
  const [limit, setLimit] = useState("");
  const [customName, setCustomName] = useState("");
  const hasBudget = currentLimit !== null;

  const isCustomCategory =
    category !== null && !CATEGORIES.some((c) => c.key === category);
  // Custom categories get an editable name both when creating and editing.
  const showNameField = createCustom || isCustomCategory;
  const snapPoints = useMemo(() => [showNameField ? "60%" : "45%"], [showNameField]);

  useEffect(() => {
    setLimit(currentLimit ? Number(currentLimit).toString() : "");
    setCustomName(
      !createCustom && category && isCustomCategory ? getCategory(category).label : "",
    );
  }, [currentLimit, category, createCustom, isCustomCategory]);

  useEffect(() => {
    if (isVisible) sheetRef.current?.expand();
    else sheetRef.current?.close();
  }, [isVisible]);

  const upsertMut = useUpsertBudget();
  const deleteMut = useDeleteBudget();
  const renameMut = useRenameBudget();
  const busy = upsertMut.isPending || deleteMut.isPending || renameMut.isPending;
  const cat = getCategory(category);

  async function handleSave() {
    let targetCategory = category;

    if (showNameField) {
      const slug = slugifyCategory(customName);
      if (!slug) {
        Alert.alert("Nombre inválido", "Escribí un nombre para la categoría.");
        return;
      }
      if (CATEGORIES.some((c) => c.key === slug)) {
        Alert.alert(
          "Categoría existente",
          `"${getCategory(slug).label}" ya existe — editála desde la lista.`,
        );
        return;
      }
      targetCategory = slug;
    }
    if (!targetCategory) return;

    const amount = parseCOP(limit);
    if (amount <= 0) {
      Alert.alert("Monto inválido", "El límite debe ser mayor a 0.");
      return;
    }
    Keyboard.dismiss();
    try {
      // Editing an existing custom category with a new name → rename first
      // (moves the budget row and its transactions), then set the limit.
      if (isCustomCategory && category && targetCategory !== category) {
        await renameMut.mutateAsync({ category, newCategory: targetCategory });
      }
      await upsertMut.mutateAsync({
        category: targetCategory,
        monthly_limit: amount.toString(),
      });
      onClose();
    } catch (e) {
      const status = (e as { response?: { status?: number } })?.response?.status;
      Alert.alert(
        "Error",
        status === 409
          ? "Ya existe una categoría con ese nombre."
          : e instanceof Error
            ? e.message
            : "Error al guardar.",
      );
    }
  }

  function handleDelete() {
    if (!category) return;
    Alert.alert(
      isCustomCategory ? "Eliminar categoría" : "Quitar presupuesto",
      isCustomCategory
        ? `¿Eliminar "${cat.label}"? Sus transacciones pasan a "Otros".`
        : `¿Quitar el límite de ${cat.label}?`,
      [
        { text: "Cancelar", style: "cancel" },
        {
          text: isCustomCategory ? "Eliminar" : "Quitar",
          style: "destructive",
          onPress: () =>
            deleteMut.mutate(category, {
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
        <Text style={styles.title}>
          {createCustom ? "Nueva categoría de presupuesto" : `Presupuesto · ${cat.label}`}
        </Text>

        {showNameField ? (
          <View style={styles.field}>
            <Text style={styles.label}>Nombre de la categoría</Text>
            <BottomSheetTextInput
              style={styles.input}
              placeholder="Ej: Mascotas, Regalos, Gym"
              placeholderTextColor={colors.textSecondary}
              value={customName}
              onChangeText={setCustomName}
              maxLength={40}
              autoFocus={createCustom}
            />
          </View>
        ) : null}

        <View style={styles.field}>
          <Text style={styles.label}>Límite mensual (COP)</Text>
          <BottomSheetTextInput
            style={styles.input}
            placeholder="0"
            placeholderTextColor={colors.textSecondary}
            value={limit}
            onChangeText={setLimit}
            keyboardType="numeric"
            autoFocus={!showNameField}
          />
        </View>

        <Pressable
          style={[styles.saveBtn, busy && { opacity: 0.5 }]}
          disabled={busy}
          onPress={handleSave}
        >
          <Text style={styles.saveText}>{busy ? "Guardando..." : "Guardar"}</Text>
        </Pressable>

        {!createCustom && hasBudget ? (
          <Pressable style={styles.deleteBtn} disabled={busy} onPress={handleDelete}>
            <Text style={styles.deleteText}>
              {isCustomCategory ? "Eliminar categoría" : "Quitar presupuesto"}
            </Text>
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
