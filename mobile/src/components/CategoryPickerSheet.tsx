import BottomSheet, {
  BottomSheetScrollView,
  BottomSheetTextInput,
} from "./sheet";
import { Ionicons } from "@expo/vector-icons";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Keyboard,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { useBudgetStatus } from "../services/queries/budgets";
import {
  useUpdateTransaction,
  type TransactionOut,
} from "../services/queries/transactions";
import { colors } from "../theme/colors";
import { CATEGORIES, customCategoryKeys, getCategory } from "../utils/categories";
import { Alert } from "../utils/alert";
import CategoryIcon from "./CategoryIcon";
import MoneyText from "./MoneyText";
import { useWebSheet } from "./useWebSheet";

type Props = {
  isVisible: boolean;
  transaction: TransactionOut | null;
  onClose: () => void;
};

export default function CategoryPickerSheet({ isVisible, transaction, onClose }: Props) {
  const sheetRef = useRef<BottomSheet>(null);
  const sheet = useWebSheet(isVisible);
  const snapPoints = useMemo(() => ["85%"], []);
  const mutation = useUpdateTransaction();
  const { data: budgetStatus } = useBudgetStatus();

  const [merchant, setMerchant] = useState("");
  const [note, setNote] = useState("");
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    if (transaction) {
      setMerchant(transaction.merchant ?? "");
      setNote(transaction.note ?? "");
      setSelected(transaction.category);
    }
  }, [transaction]);

  useEffect(() => {
    if (isVisible) sheetRef.current?.expand();
    else sheetRef.current?.close();
  }, [isVisible]);

  // User-defined categories: whatever budgets or this transaction reference
  // beyond the built-in set.
  const customKeys = useMemo(
    () =>
      customCategoryKeys([
        ...(budgetStatus?.items ?? []).map((i) => i.category),
        transaction?.category,
      ]),
    [budgetStatus, transaction],
  );

  function handleSave() {
    if (!transaction || mutation.isPending) return;
    const name = merchant.trim();
    Keyboard.dismiss();
    mutation.mutate(
      {
        id: transaction.id,
        category: selected,
        merchant: name || null,
        note: note.trim() || null,
      },
      {
        onSuccess: onClose,
        onError: (e) =>
          Alert.alert("Error", e instanceof Error ? e.message : "Error al guardar."),
      },
    );
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
      {/* Pinned header: with a dozen category rows below, a Guardar at the
          end of the list was off-screen until you scrolled to it. */}
      <View style={styles.header}>
        <View style={styles.headerText}>
          <Text style={styles.title}>Editar movimiento</Text>
          {transaction ? (
            <Text style={styles.subtitle} numberOfLines={1}>
              {transaction.merchant ?? "Sin nombre"} ·{" "}
              <MoneyText value={transaction.amount} size="sm" />
            </Text>
          ) : null}
        </View>
        <Pressable
          style={[styles.saveBtn, mutation.isPending && { opacity: 0.5 }]}
          disabled={mutation.isPending}
          onPress={handleSave}
        >
          <Text style={styles.saveText}>
            {mutation.isPending ? "Guardando..." : "Guardar"}
          </Text>
        </Pressable>
      </View>

      <BottomSheetScrollView
        contentContainerStyle={styles.body}
        keyboardShouldPersistTaps="handled"
      >

        <Text style={styles.label}>Nombre</Text>
        <BottomSheetTextInput
          style={styles.input}
          placeholder="Ej: Mercado de la semana"
          placeholderTextColor={colors.textSecondary}
          value={merchant}
          onChangeText={setMerchant}
          maxLength={255}
        />

        <Text style={styles.label}>Descripción (opcional)</Text>
        <BottomSheetTextInput
          style={[styles.input, styles.noteInput]}
          placeholder="Ej: Regalo cumpleaños de mamá, mitad con Juan"
          placeholderTextColor={colors.textSecondary}
          value={note}
          onChangeText={setNote}
          maxLength={500}
          multiline
        />

        <Text style={styles.label}>Categoría</Text>
        {CATEGORIES.map((cat) => (
          <OptionRow
            key={cat.key}
            categoryKey={cat.key}
            label={cat.label}
            selected={selected === cat.key}
            onPress={() => setSelected(cat.key)}
          />
        ))}
        {customKeys.map((key) => (
          <OptionRow
            key={key}
            categoryKey={key}
            label={getCategory(key).label}
            selected={selected === key}
            onPress={() => setSelected(key)}
          />
        ))}
        <OptionRow
          categoryKey={null}
          label="Otros (sin categoría)"
          selected={selected === null}
          onPress={() => setSelected(null)}
        />
      </BottomSheetScrollView>
    </BottomSheet>
  );
}

function OptionRow({
  categoryKey,
  label,
  selected,
  onPress,
}: {
  categoryKey: string | null;
  label: string;
  selected: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      style={({ pressed }) => [
        styles.option,
        selected && styles.optionSelected,
        pressed && styles.pressed,
      ]}
      onPress={onPress}
    >
      <CategoryIcon categoryKey={categoryKey} />
      <Text style={[styles.optionLabel, selected && styles.optionLabelSelected]}>
        {label}
      </Text>
      {selected ? (
        <Ionicons name="checkmark-circle" size={20} color={colors.primary} />
      ) : (
        <View style={styles.checkPlaceholder} />
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  bg: { backgroundColor: colors.surface },
  handle: { backgroundColor: colors.border },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 16,
    paddingTop: 4,
    paddingBottom: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  headerText: { flex: 1 },
  body: { padding: 16, paddingTop: 4, paddingBottom: 32, gap: 6 },
  title: { color: colors.textPrimary, fontSize: 16, fontWeight: "600" },
  subtitle: { color: colors.textSecondary, fontSize: 13, marginTop: 2 },
  label: {
    color: colors.textSecondary,
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginTop: 8,
    marginBottom: 2,
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
  noteInput: { minHeight: 64, textAlignVertical: "top" },
  option: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.background,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 12,
    gap: 12,
  },
  optionSelected: { borderColor: colors.primary, backgroundColor: colors.primarySoft },
  pressed: { opacity: 0.6 },
  optionLabel: { color: colors.textPrimary, fontSize: 14, fontWeight: "600", flex: 1 },
  optionLabelSelected: { color: colors.primary },
  checkPlaceholder: { width: 20 },
  saveBtn: {
    backgroundColor: colors.primary,
    paddingVertical: 10,
    paddingHorizontal: 18,
    borderRadius: 8,
    alignItems: "center",
  },
  saveText: { color: "#fff", fontWeight: "600", fontSize: 14 },
});
