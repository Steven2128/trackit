import BottomSheet, { BottomSheetScrollView, BottomSheetTextInput } from "./sheet";
import { useEffect, useMemo, useRef, useState } from "react";
import { Keyboard, Pressable, StyleSheet, Text, View } from "react-native";

import { useCreateManualMovement } from "../services/queries/transactions";
import { colors } from "../theme/colors";
import { Alert } from "../utils/alert";
import { formatCOPInput, parseCOP } from "../utils/currency";
import { expenseInstant } from "../utils/dates";
import ExpenseDayPicker from "./ExpenseDayPicker";
import { useWebSheet } from "./useWebSheet";

type Props = {
  isVisible: boolean;
  onClose: () => void;
};

// Where the money landed. Same accounts the manual-expense sheet offers; the
// backend raises that balance and, if the bank email shows up later, the sync
// attaches it instead of duplicating.
const INTO: { key: "davivienda" | "nequi" | "cash"; label: string }[] = [
  { key: "davivienda", label: "Davivienda" },
  { key: "nequi", label: "Nequi" },
  { key: "cash", label: "Efectivo" },
];

/** Income typed by hand, for deposits whose email never arrived. */
export default function IncomeSheet({ isVisible, onClose }: Props) {
  const sheetRef = useRef<BottomSheet>(null);
  const sheet = useWebSheet(isVisible);
  const snapPoints = useMemo(() => ["70%"], []);
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [note, setNote] = useState("");
  const [into, setInto] = useState<(typeof INTO)[number]["key"]>("davivienda");
  const [daysAgo, setDaysAgo] = useState(0);
  const create = useCreateManualMovement();

  useEffect(() => {
    setAmount("");
    setDescription("");
    setNote("");
    setInto("davivienda");
    setDaysAgo(0);
    if (isVisible) sheetRef.current?.expand();
    else sheetRef.current?.close();
  }, [isVisible]);

  function handleSave() {
    const value = parseCOP(amount);
    if (value <= 0 || description.trim() === "") {
      Alert.alert("Faltan datos", "Poné el monto y de qué es el ingreso.");
      return;
    }
    Keyboard.dismiss();
    create.mutate(
      {
        account: into,
        transaction_type: "credit",
        amount: value,
        merchant: description.trim(),
        note: note.trim() || null,
        // Today goes without a date so the server stamps "now".
        ...(daysAgo > 0 ? { occurred_at: expenseInstant(daysAgo) } : {}),
      },
      {
        onSuccess: onClose,
        onError: (e) =>
          Alert.alert("Error", e instanceof Error ? e.message : "No se pudo guardar."),
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
      <BottomSheetScrollView contentContainerStyle={styles.body}>
        <Text style={styles.title}>Registrar ingreso</Text>
        <Text style={styles.hint}>
          Para plata que entró y cuyo email no llegó. Suma a la cuenta que elijas y cuenta
          como recibido del día. Si el email llega después, no se duplica.
        </Text>

        <Text style={styles.label}>Monto (COP)</Text>
        <BottomSheetTextInput
          style={styles.input}
          placeholder="0"
          placeholderTextColor={colors.textSecondary}
          value={amount}
          onChangeText={(v) => setAmount(formatCOPInput(v))}
          keyboardType="numeric"
        />

        <Text style={styles.label}>¿De qué?</Text>
        <BottomSheetTextInput
          style={styles.input}
          placeholder="p.ej. Pago freelance"
          placeholderTextColor={colors.textSecondary}
          value={description}
          onChangeText={setDescription}
        />

        <Text style={styles.label}>¿A dónde entró?</Text>
        <View style={styles.chips}>
          {INTO.map((a) => (
            <Pressable
              key={a.key}
              onPress={() => setInto(a.key)}
              style={[styles.chip, into === a.key && styles.chipActive]}
            >
              <Text style={[styles.chipText, into === a.key && styles.chipTextActive]}>
                {a.label}
              </Text>
            </Pressable>
          ))}
        </View>

        <Text style={styles.label}>¿Cuándo?</Text>
        <ExpenseDayPicker daysAgo={daysAgo} onChange={setDaysAgo} />

        <Text style={styles.label}>Nota (opcional)</Text>
        <BottomSheetTextInput
          style={styles.input}
          placeholder="Algo para recordar"
          placeholderTextColor={colors.textSecondary}
          value={note}
          onChangeText={setNote}
        />

        <Pressable
          style={[styles.saveBtn, create.isPending && { opacity: 0.5 }]}
          disabled={create.isPending}
          onPress={handleSave}
        >
          <Text style={styles.saveText}>
            {create.isPending ? "Guardando..." : "Guardar ingreso"}
          </Text>
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
  chipActive: { backgroundColor: colors.success, borderColor: colors.success },
  chipText: { color: colors.textSecondary, fontSize: 13, fontWeight: "600" },
  chipTextActive: { color: "#fff" },
  saveBtn: {
    backgroundColor: colors.success,
    padding: 14,
    borderRadius: 8,
    alignItems: "center",
    marginTop: 8,
  },
  saveText: { color: "#fff", fontWeight: "600", fontSize: 14 },
});
