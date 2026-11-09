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
import { useDebts } from "../services/queries/debts";
import { useRuleSuggestion, useSaveCategoryRule } from "../services/queries/categoryRules";
import {
  useDeleteCashTransaction,
  useUpdateTransaction,
  type TransactionOut,
} from "../services/queries/transactions";
import { colors } from "../theme/colors";
import { CATEGORIES, INTERNAL_CATEGORIES, customCategoryKeys, getCategory } from "../utils/categories";
import { formatCOPInput, parseCOP, toCOPInput } from "../utils/currency";
import { Alert } from "../utils/alert";
import { daysAgo as daysAgoOf, expenseInstant } from "../utils/dates";
import CategoryIcon from "./CategoryIcon";
import ExpenseDayPicker from "./ExpenseDayPicker";
import MoneyText from "./MoneyText";
import { useWebSheet } from "./useWebSheet";

// What else a category change applies to — "one" is just this movement.
type RuleScope = "one" | "future" | "all";

const SCOPES: { key: RuleScope; label: string }[] = [
  { key: "one", label: "Solo este" },
  { key: "future", label: "Este y los próximos" },
  { key: "all", label: "Todos (también los anteriores)" },
];


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
  const removal = useDeleteCashTransaction();
  const saveRule = useSaveCategoryRule();
  const { data: budgetStatus } = useBudgetStatus();

  const [merchant, setMerchant] = useState("");
  const [note, setNote] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [amount, setAmount] = useState("");
  const [daysAgo, setDaysAgo] = useState(0);
  const [scope, setScope] = useState<RuleScope>("one");
  // Shared expense: the part someone else pays back (debits only).
  const [isShared, setIsShared] = useState(false);
  const [shared, setShared] = useState("");
  // Typed-in cash expenses: amount and day editable, and deletable. Bank rows mirror
  // their notification email, so their amount stays read-only.
  const isCash = transaction?.source === "cash";
  const isDebit = transaction?.transaction_type === "debit";
  // Which hand-entered debt a payment went to (a loan from mom, a bank loan
  // without emails). Cards read by email are left out: their own payment
  // email already lowers them. Card purchases keep their card.
  const [debtId, setDebtId] = useState<string | null>(null);
  const { data: debts } = useDebts();
  const manualDebts = useMemo(() => (debts ?? []).filter((d) => !d.email_sender), [debts]);
  const canPickDebt =
    isDebit && transaction?.source !== "card" && selected === "debt_payment";

  useEffect(() => {
    if (transaction) {
      setMerchant(transaction.merchant ?? "");
      setNote(transaction.note ?? "");
      setSelected(transaction.category);
      setAmount(toCOPInput(transaction.amount));
      setDaysAgo(daysAgoOf(transaction.occurred_at));
      setScope("one");
      setIsShared(!!transaction.shared_amount);
      setShared(transaction.shared_amount ? toCOPInput(transaction.shared_amount) : "");
      setDebtId(transaction.debt_id);
    }
  }, [transaction]);

  // Amount the shared part is measured against: the edited one for cash.
  const total = isCash ? parseCOP(amount) : Math.round(Number(transaction?.amount ?? 0));

  function toggleShared() {
    if (!isShared && !shared) setShared(toCOPInput(String(Math.round(total / 2))));
    setIsShared(!isShared);
  }

  const suggestion = useRuleSuggestion(transaction?.merchant);
  const pattern = suggestion.data ?? null;
  // Offer a merchant rule only for a real category change on a named
  // movement. Not for "Otros" (null), nor for the internal-movement
  // categories, which come from what the email says (the API refuses them).
  const offerRule =
    !!transaction &&
    pattern !== null &&
    selected !== null &&
    !INTERNAL_CATEGORIES.includes(selected) &&
    selected !== transaction.category;

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
    const newAmount = parseCOP(amount);
    if (isCash && newAmount <= 0) {
      Alert.alert("Monto inválido", "Escribí un monto en pesos mayor a 0.");
      return;
    }
    const sharedValue = isDebit && isShared ? parseCOP(shared) : 0;
    if (isDebit && isShared && (sharedValue <= 0 || sharedValue > total)) {
      Alert.alert(
        "Parte compartida inválida",
        "Lo que pone la otra persona tiene que ser mayor a 0 y no pasar del monto.",
      );
      return;
    }
    const previousShared = Math.round(Number(transaction.shared_amount ?? 0));
    // Leaving "Pago de deuda" unlinks it (the backend gives the amount back).
    const nextDebtId = canPickDebt ? debtId : null;
    const debtChanged = transaction.source !== "card" && nextDebtId !== transaction.debt_id;
    Keyboard.dismiss();
    mutation.mutate(
      {
        id: transaction.id,
        category: selected,
        merchant: name || null,
        note: note.trim() || null,
        ...(isCash && newAmount !== Math.round(Number(transaction.amount))
          ? { amount: newAmount }
          : {}),
        // Only when the day changed: keeps the original time otherwise.
        ...(isCash && daysAgo !== daysAgoOf(transaction.occurred_at)
          ? { occurred_at: expenseInstant(daysAgo) }
          : {}),
        ...(isDebit && sharedValue !== previousShared ? { shared_amount: sharedValue } : {}),
        ...(debtChanged ? { debt_id: nextDebtId } : {}),
      },
      {
        onSuccess: () => {
          if (offerRule && scope !== "one" && pattern && selected) {
            saveRule.mutate(
              { pattern, category: selected, apply_to_past: scope === "all" },
              {
                onSuccess: ({ updated }) => {
                  const label = getCategory(selected).label;
                  Alert.alert(
                    "Regla guardada",
                    `Los próximos de "${pattern}" van a ${label}.` +
                      (scope === "all"
                        ? ` Además, ${updated} movimiento${updated === 1 ? "" : "s"} anterior${updated === 1 ? "" : "es"} pasaron a ${label}.`
                        : ""),
                  );
                  onClose();
                },
                onError: (e) =>
                  Alert.alert(
                    "Error",
                    "Se guardó el cambio de este movimiento, pero no la regla. " +
                      (e instanceof Error ? e.message : ""),
                  ),
              },
            );
            return;
          }
          onClose();
        },
        onError: (e) =>
          Alert.alert("Error", e instanceof Error ? e.message : "Error al guardar."),
      },
    );
  }

  function handleDelete() {
    if (!transaction || removal.isPending) return;
    Alert.alert(
      "Eliminar gasto",
      `¿Eliminar "${transaction.merchant ?? "este gasto"}"? Vuelve a sumar al efectivo.`,
      [
        { text: "Cancelar", style: "cancel" },
        {
          text: "Eliminar",
          style: "destructive",
          onPress: () =>
            removal.mutate(transaction.id, {
              onSuccess: onClose,
              onError: (e) =>
                Alert.alert("Error", e instanceof Error ? e.message : "Error al eliminar."),
            }),
        },
      ],
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
        {/* In the header, not after the category list, so it's findable. */}
        {isCash ? (
          <Pressable
            style={({ pressed }) => [styles.deleteBtn, pressed && styles.pressed]}
            disabled={removal.isPending}
            onPress={handleDelete}
            hitSlop={6}
            accessibilityRole="button"
            accessibilityLabel="Eliminar gasto"
          >
            <Ionicons name="trash-outline" size={20} color={colors.danger} />
          </Pressable>
        ) : null}
        <Pressable
          style={[styles.saveBtn, (mutation.isPending || saveRule.isPending) && { opacity: 0.5 }]}
          disabled={mutation.isPending || saveRule.isPending}
          onPress={handleSave}
        >
          <Text style={styles.saveText}>
            {mutation.isPending || saveRule.isPending ? "Guardando..." : "Guardar"}
          </Text>
        </Pressable>
      </View>

      {/* Pinned like the rule box: "Pago de deuda" sits far down the list. */}
      {canPickDebt ? (
        <View style={styles.scopeBox}>
          <Text style={styles.scopeTitle}>¿A qué deuda fue este pago?</Text>
          {manualDebts.length === 0 ? (
            <Text style={styles.scopeHint}>
              No tenés deudas cargadas a mano. Creala en Deudas (ej: "Mamá") y volvé.
            </Text>
          ) : (
            <View style={styles.scopeChips}>
              {[{ id: null, bank_name: "Ninguna" }, ...manualDebts].map((d) => (
                <Pressable
                  key={d.id ?? "none"}
                  onPress={() => setDebtId(d.id)}
                  style={[styles.scopeChip, debtId === d.id && styles.scopeChipActive]}
                >
                  <Text style={[styles.scopeText, debtId === d.id && styles.scopeTextActive]}>
                    {d.bank_name}
                  </Text>
                </Pressable>
              ))}
            </View>
          )}
          {debtId && debtId !== transaction?.debt_id ? (
            <Text style={styles.scopeHint}>
              Le baja <MoneyText value={transaction?.amount ?? "0"} size="sm" /> al saldo de{" "}
              {manualDebts.find((d) => d.id === debtId)?.bank_name}.
            </Text>
          ) : null}
        </View>
      ) : null}

      {/* Pinned too: it appears right when a category is tapped, which is
          usually far down the list. */}
      {offerRule ? (
        <View style={styles.scopeBox}>
          <Text style={styles.scopeTitle}>
            ¿Y los otros de "{pattern}"? → {getCategory(selected).label}
          </Text>
          <View style={styles.scopeChips}>
            {SCOPES.map((s) => (
              <Pressable
                key={s.key}
                onPress={() => setScope(s.key)}
                style={[styles.scopeChip, scope === s.key && styles.scopeChipActive]}
              >
                <Text style={[styles.scopeText, scope === s.key && styles.scopeTextActive]}>
                  {s.label}
                </Text>
              </Pressable>
            ))}
          </View>
          {scope === "all" ? (
            <Text style={styles.scopeHint}>
              Los que ya cambiaste a mano no se tocan.
            </Text>
          ) : null}
        </View>
      ) : null}

      <BottomSheetScrollView
        contentContainerStyle={styles.body}
        keyboardShouldPersistTaps="handled"
      >
        {isCash ? (
          <>
            <Text style={styles.label}>Monto (COP)</Text>
            <BottomSheetTextInput
              style={styles.input}
              placeholder="0"
              placeholderTextColor={colors.textSecondary}
              value={amount}
              onChangeText={(v) => setAmount(formatCOPInput(v))}
              keyboardType="number-pad"
              inputMode="numeric"
            />
            <Text style={styles.label}>Día</Text>
            <ExpenseDayPicker daysAgo={daysAgo} onChange={setDaysAgo} />
          </>
        ) : null}

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

        {isDebit ? (
          <>
            <Pressable
              style={({ pressed }) => [styles.sharedToggle, pressed && styles.pressed]}
              onPress={toggleShared}
              accessibilityRole="checkbox"
              accessibilityState={{ checked: isShared }}
            >
              <Ionicons
                name={isShared ? "checkbox" : "square-outline"}
                size={20}
                color={isShared ? colors.primary : colors.textSecondary}
              />
              <Text style={styles.sharedToggleText}>
                Lo comparto (otra persona me devuelve una parte)
              </Text>
            </Pressable>
            {isShared ? (
              <>
                <Text style={styles.label}>Lo pone la otra persona (COP)</Text>
                <BottomSheetTextInput
                  style={styles.input}
                  placeholder="0"
                  placeholderTextColor={colors.textSecondary}
                  value={shared}
                  onChangeText={(v) => setShared(formatCOPInput(v))}
                  keyboardType="number-pad"
                  inputMode="numeric"
                />
                <Text style={styles.sharedHint}>
                  Tu parte: <MoneyText value={String(Math.max(0, total - parseCOP(shared)))} size="sm" />
                  {" "}— es lo que cuenta como gasto. Cuando te devuelva, marcá esa entrada
                  como Reembolso.
                </Text>
              </>
            ) : null}
          </>
        ) : null}

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
  sharedToggle: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginTop: 10,
    paddingVertical: 6,
  },
  sharedToggleText: { color: colors.textPrimary, fontSize: 14, flex: 1 },
  sharedHint: { color: colors.textSecondary, fontSize: 12, marginTop: 4 },
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
  scopeBox: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    backgroundColor: colors.primarySoft,
    gap: 8,
  },
  scopeTitle: { color: colors.textPrimary, fontSize: 13, fontWeight: "600" },
  scopeChips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  scopeChip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
    backgroundColor: colors.surface,
  },
  scopeChipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  scopeText: { color: colors.textSecondary, fontSize: 12, fontWeight: "600" },
  scopeTextActive: { color: "#fff" },
  scopeHint: { color: colors.textSecondary, fontSize: 11 },
  deleteBtn: {
    padding: 9,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.danger,
  },
});
