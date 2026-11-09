import BottomSheet, { BottomSheetScrollView, BottomSheetTextInput } from "./sheet";
import { useEffect, useMemo, useRef, useState } from "react";
import { Keyboard, Pressable, StyleSheet, Text, View } from "react-native";

import { useContacts } from "../services/queries/contacts";
import { useCreateManualMovement, type ManualMovement } from "../services/queries/transactions";
import { colors } from "../theme/colors";
import { Alert } from "../utils/alert";
import { CATEGORIES, INTERNAL_CATEGORIES } from "../utils/categories";
import { formatCOPInput, parseCOP, toCOPInput } from "../utils/currency";
import { expenseInstant } from "../utils/dates";
import ContactPicker from "./ContactPicker";
import ExpenseDayPicker from "./ExpenseDayPicker";
import MoneyText from "./MoneyText";
import { useWebSheet } from "./useWebSheet";

// received: they paid the user back (or lent them) — e.g. a "llave" transfer
//   whose email never came. sent: the user paid them back or lent them.
// theyPaid: a shared expense the person paid; only the user's part is spending.
export type PersonMovementKind = "received" | "sent" | "theyPaid";

export type PersonMovementPreset = {
  kind: PersonMovementKind;
  contactId?: string | null;
  amount?: number;
};

const KINDS: { key: PersonMovementKind; label: string }[] = [
  { key: "received", label: "Me pagó / me pasó plata" },
  { key: "sent", label: "Le pagué / le presté" },
  { key: "theyPaid", label: "Pagó un gasto compartido" },
];

const ACCOUNTS: { key: ManualMovement["account"]; label: string }[] = [
  { key: "davivienda", label: "Davivienda" },
  { key: "nequi", label: "Nequi" },
  { key: "cash", label: "Efectivo" },
];

const SPENDABLE = CATEGORIES.filter((c) => !INTERNAL_CATEGORIES.includes(c.key));

type Props = { preset: PersonMovementPreset | null; onClose: () => void };

/** Logs money with a person that no email brought in: paybacks by "llave",
 * loans, or an expense they paid. */
export default function PersonMovementSheet({ preset, onClose }: Props) {
  const sheetRef = useRef<BottomSheet>(null);
  const sheet = useWebSheet(preset !== null);
  const snapPoints = useMemo(() => ["90%"], []);
  const create = useCreateManualMovement();
  const { data: contacts } = useContacts();

  const [kind, setKind] = useState<PersonMovementKind>("received");
  const [contactId, setContactId] = useState<string | null>(null);
  const [amount, setAmount] = useState("");
  // Their part of an expense they paid; follows half the total until edited.
  const [theirPart, setTheirPart] = useState("");
  const [partEdited, setPartEdited] = useState(false);
  const [account, setAccount] = useState<ManualMovement["account"]>("davivienda");
  const [merchant, setMerchant] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const [daysAgo, setDaysAgo] = useState(0);
  const [note, setNote] = useState("");

  useEffect(() => {
    if (preset) {
      setKind(preset.kind);
      setContactId(preset.contactId ?? null);
      setAmount(preset.amount ? toCOPInput(String(preset.amount)) : "");
      setTheirPart(preset.amount ? toCOPInput(String(Math.round(preset.amount / 2))) : "");
      setPartEdited(false);
      setAccount("davivienda");
      setMerchant("");
      setCategory(null);
      setDaysAgo(0);
      setNote("");
      sheetRef.current?.expand();
    } else {
      sheetRef.current?.close();
    }
  }, [preset]);

  const name = contacts?.find((c) => c.id === contactId)?.name ?? "la otra persona";
  const total = parseCOP(amount);
  const theirs = parseCOP(theirPart);

  function changeAmount(v: string) {
    const formatted = formatCOPInput(v);
    setAmount(formatted);
    if (!partEdited) setTheirPart(toCOPInput(String(Math.round(parseCOP(formatted) / 2))));
  }

  function handleSave() {
    if (create.isPending) return;
    if (!contactId) {
      Alert.alert("Falta la persona", "Elegí con quién fue (o creala con + Nueva).");
      return;
    }
    if (total <= 0) {
      Alert.alert("Monto inválido", "Escribí un monto en pesos mayor a 0.");
      return;
    }
    if (kind === "theyPaid" && (theirs > total || !merchant.trim())) {
      Alert.alert(
        "Faltan datos",
        !merchant.trim()
          ? "Poné en qué fue el gasto."
          : "La parte de la otra persona no puede pasar del total.",
      );
      return;
    }
    const fallbackName =
      kind === "received" ? `Me pagó ${name}` : kind === "sent" ? `Le pagué a ${name}` : "";
    const payload: ManualMovement =
      kind === "theyPaid"
        ? {
            account: "contact",
            transaction_type: "debit",
            amount: total,
            shared_amount: theirs,
            category,
            merchant: merchant.trim(),
            contact_id: contactId,
          }
        : {
            account,
            transaction_type: kind === "received" ? "credit" : "debit",
            amount: total,
            category: "reimbursement",
            merchant: merchant.trim() || fallbackName,
            contact_id: contactId,
          };
    Keyboard.dismiss();
    create.mutate(
      {
        ...payload,
        note: note.trim() || null,
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
      <BottomSheetScrollView contentContainerStyle={styles.body} keyboardShouldPersistTaps="handled">
        <Text style={styles.title}>Movimiento con una persona</Text>
        <Text style={styles.hint}>{HINTS[kind]}</Text>

        <Text style={styles.label}>¿Qué pasó?</Text>
        <View style={styles.chips}>
          {KINDS.map((k) => (
            <Chip key={k.key} label={k.label} active={kind === k.key} onPress={() => setKind(k.key)} />
          ))}
        </View>

        <Text style={styles.label}>¿Con quién?</Text>
        <View style={styles.block}>
          <ContactPicker value={contactId} onChange={setContactId} allowNone={false} />
        </View>

        <Text style={styles.label}>{kind === "theyPaid" ? "Total del gasto (COP)" : "Monto (COP)"}</Text>
        <BottomSheetTextInput
          style={styles.input}
          placeholder="0"
          placeholderTextColor={colors.textSecondary}
          value={amount}
          onChangeText={changeAmount}
          keyboardType="number-pad"
          inputMode="numeric"
        />

        {kind === "theyPaid" ? (
          <>
            <Text style={styles.label}>Parte de {name} (COP)</Text>
            <BottomSheetTextInput
              style={styles.input}
              placeholder="0"
              placeholderTextColor={colors.textSecondary}
              value={theirPart}
              onChangeText={(v) => {
                setPartEdited(true);
                setTheirPart(formatCOPInput(v));
              }}
              keyboardType="number-pad"
              inputMode="numeric"
            />
            <Text style={styles.sub}>
              Tu parte: <MoneyText value={String(Math.max(0, total - theirs))} size="sm" /> —
              cuenta como gasto tuyo y es lo que le vas a deber.
            </Text>
            <Text style={styles.label}>¿En qué?</Text>
            <BottomSheetTextInput
              style={styles.input}
              placeholder="Ej: Mercado D1"
              placeholderTextColor={colors.textSecondary}
              value={merchant}
              onChangeText={setMerchant}
              maxLength={255}
            />
            <Text style={styles.label}>Categoría</Text>
            <View style={styles.chips}>
              {SPENDABLE.map((c) => (
                <Chip
                  key={c.key}
                  label={c.label}
                  active={category === c.key}
                  onPress={() => setCategory(category === c.key ? null : c.key)}
                />
              ))}
            </View>
          </>
        ) : (
          <>
            <Text style={styles.label}>
              {kind === "received" ? "¿A qué cuenta llegó?" : "¿De qué cuenta salió?"}
            </Text>
            <View style={styles.chips}>
              {ACCOUNTS.map((a) => (
                <Chip key={a.key} label={a.label} active={account === a.key} onPress={() => setAccount(a.key)} />
              ))}
            </View>
            <Text style={styles.label}>Nombre (opcional)</Text>
            <BottomSheetTextInput
              style={styles.input}
              placeholder={kind === "received" ? `Me pagó ${name}` : `Le pagué a ${name}`}
              placeholderTextColor={colors.textSecondary}
              value={merchant}
              onChangeText={setMerchant}
              maxLength={255}
            />
          </>
        )}

        <Text style={styles.label}>¿Cuándo?</Text>
        <View style={styles.block}>
          <ExpenseDayPicker daysAgo={daysAgo} onChange={setDaysAgo} />
        </View>

        <Text style={styles.label}>Descripción (opcional)</Text>
        <BottomSheetTextInput
          style={styles.input}
          placeholder="Ej: Mitad de la boleta"
          placeholderTextColor={colors.textSecondary}
          value={note}
          onChangeText={setNote}
          maxLength={500}
        />

        <Pressable
          style={[styles.saveBtn, create.isPending && { opacity: 0.5 }]}
          disabled={create.isPending}
          onPress={handleSave}
        >
          <Text style={styles.saveText}>{create.isPending ? "Guardando..." : "Guardar"}</Text>
        </Pressable>
      </BottomSheetScrollView>
    </BottomSheet>
  );
}

const HINTS: Record<PersonMovementKind, string> = {
  received:
    "Para plata que te llegó por llave (o en efectivo) sin email del banco. Suma a la cuenta, " +
    "no cuenta como ingreso y baja lo que te debe. Si ya conciliaste ese día, el saldo no se duplica.",
  sent:
    "Cuando le devolvés plata o le prestás. Resta de la cuenta, no cuenta como gasto y " +
    "sube lo que te debe (o baja lo que le debés).",
  theyPaid:
    "Un gasto que pagó la otra persona. No mueve tus cuentas: tu parte cuenta como gasto tuyo " +
    "y queda como lo que le debés.",
};

function Chip({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={[styles.chip, active && styles.chipActive]}>
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  bg: { backgroundColor: colors.surface },
  handle: { backgroundColor: colors.border },
  body: { padding: 16, paddingBottom: 48 },
  title: { color: colors.textPrimary, fontSize: 16, fontWeight: "600", marginBottom: 6 },
  hint: { color: colors.textSecondary, fontSize: 12, lineHeight: 17, marginBottom: 14 },
  sub: { color: colors.textSecondary, fontSize: 12, marginTop: -4, marginBottom: 10 },
  label: {
    color: colors.textSecondary,
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 6,
    marginTop: 4,
  },
  block: { marginBottom: 12 },
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
