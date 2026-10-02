import BottomSheet, { BottomSheetScrollView, BottomSheetTextInput } from "@gorhom/bottom-sheet";
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
  useCardFormats,
  useCreateDebt,
  useDeleteDebt,
  useUpdateDebt,
} from "../services/queries/debts";
import { useTransactions } from "../services/queries/transactions";
import { colors } from "../theme/colors";
import { parseCOP } from "../utils/currency";
import MoneyText from "./MoneyText";

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
  // Credit-card email link; format null = not linked.
  format: string | null;
  sender: string;
  digits: string;
};

const EMPTY: FormState = {
  bank: "",
  amount: "",
  rate: "",
  min: "",
  format: null,
  sender: "",
  digits: "",
};

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

function fromDebt(d?: DebtOut): FormState {
  if (!d) return EMPTY;
  return {
    bank: d.bank_name,
    amount: d.total_amount ? Number(d.total_amount).toString() : "",
    rate: d.interest_rate ? Number(d.interest_rate).toString() : "",
    min: d.minimum_payment ? Number(d.minimum_payment).toString() : "",
    format: d.email_sender ? d.email_format : null,
    sender: d.email_sender ?? "",
    digits: d.card_last_digits ?? "",
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

  const { data: cardFormats } = useCardFormats();
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
    const sender = form.sender.trim().toLowerCase();
    const digits = form.digits.trim();
    if (form.format) {
      if (!EMAIL_RE.test(sender)) {
        Alert.alert("Remitente inválido", "Escribí el email desde el que te llegan los avisos de la tarjeta.");
        return null;
      }
      if (digits !== "" && !/^\d{4}$/.test(digits)) {
        Alert.alert("Dígitos inválidos", "Los últimos dígitos de la tarjeta son 4 números.");
        return null;
      }
    }
    return {
      bank_name: bank,
      total_amount: amount.toString(),
      interest_rate: rate !== null && !Number.isNaN(rate) ? rate.toString() : null,
      minimum_payment: min !== null ? min.toString() : null,
      email_sender: form.format ? sender : null,
      email_format: form.format,
      card_last_digits: form.format && digits !== "" ? digits : null,
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
      <BottomSheetScrollView contentContainerStyle={styles.body}>
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

        <Text style={styles.section}>Avisos de la tarjeta por email</Text>
        <View style={styles.chips}>
          <Chip
            label="No conectar"
            active={form.format === null}
            onPress={() => setForm((f) => ({ ...f, format: null }))}
          />
          {(cardFormats ?? []).map((cf) => (
            <Chip
              key={cf.key}
              label={cf.label}
              active={form.format === cf.key}
              onPress={() =>
                setForm((f) => ({
                  ...f,
                  format: cf.key,
                  sender: f.sender.trim() === "" ? cf.default_sender ?? "" : f.sender,
                }))
              }
            />
          ))}
        </View>
        {form.format ? (
          <>
            <Field label="Remitente de los avisos">
              <BottomSheetTextInput
                style={styles.input}
                placeholder="noreply@banco.com"
                placeholderTextColor={colors.textSecondary}
                value={form.sender}
                onChangeText={(v) => setForm((f) => ({ ...f, sender: v }))}
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="email-address"
              />
            </Field>
            <Field label="Últimos 4 dígitos (opcional)">
              <BottomSheetTextInput
                style={styles.input}
                placeholder="Solo si tenés varias tarjetas con el mismo remitente"
                placeholderTextColor={colors.textSecondary}
                value={form.digits}
                onChangeText={(v) => setForm((f) => ({ ...f, digits: v }))}
                keyboardType="number-pad"
                maxLength={4}
              />
            </Field>
            <Text style={styles.hint}>
              Poné arriba el saldo de hoy. Desde que guardás, cada compra suma, cada pago resta y
              el extracto actualiza el pago mínimo y la fecha límite.
            </Text>
          </>
        ) : null}

        <Pressable
          style={[styles.saveBtn, busy && { opacity: 0.5 }]}
          disabled={busy}
          onPress={handleSave}
        >
          <Text style={styles.saveText}>{busy ? "Guardando..." : "Guardar"}</Text>
        </Pressable>

        {isEdit && debt?.email_sender ? <DebtMovements debtId={debt.id} /> : null}

        {isEdit ? (
          <Pressable style={styles.deleteBtn} disabled={busy} onPress={handleDelete}>
            <Text style={styles.deleteText}>Eliminar deuda</Text>
          </Pressable>
        ) : null}
      </BottomSheetScrollView>
    </BottomSheet>
  );
}

function DebtMovements({ debtId }: { debtId: string }) {
  const { data, isLoading } = useTransactions({ debtId, limit: 15 });
  const items = data?.items ?? [];
  return (
    <View style={styles.movements}>
      <Text style={styles.section}>Movimientos de la tarjeta</Text>
      {isLoading ? (
        <Text style={styles.hint}>Cargando…</Text>
      ) : items.length === 0 ? (
        <Text style={styles.hint}>Todavía no llegó ningún aviso de esta tarjeta.</Text>
      ) : (
        items.map((tx) => {
          const isPayment = tx.transaction_type === "credit";
          return (
            <View key={tx.id} style={styles.moveRow}>
              <View style={styles.moveBody}>
                <Text style={styles.moveName} numberOfLines={1}>
                  {isPayment ? "Pago a la tarjeta" : tx.merchant ?? "Compra"}
                </Text>
                <Text style={styles.moveDate}>
                  {new Date(tx.occurred_at).toLocaleDateString("es-CO", {
                    day: "numeric",
                    month: "short",
                  })}
                </Text>
              </View>
              <MoneyText
                value={tx.amount}
                size="sm"
                signed={isPayment}
                positive={isPayment}
                negative={!isPayment}
              />
            </View>
          );
        })
      )}
    </View>
  );
}

function Chip({
  label,
  active,
  onPress,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={[styles.chip, active && styles.chipActive]}
      accessibilityState={{ selected: active }}
    >
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </Pressable>
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
  body: { padding: 16, gap: 4, paddingBottom: 48 },
  section: {
    color: colors.textSecondary,
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginTop: 8,
    marginBottom: 8,
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
  hint: { color: colors.textSecondary, fontSize: 12, lineHeight: 17, marginBottom: 8 },
  movements: { marginTop: 16 },
  moveRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    gap: 8,
  },
  moveBody: { flex: 1 },
  moveName: { color: colors.textPrimary, fontSize: 14, fontWeight: "600" },
  moveDate: { color: colors.textSecondary, fontSize: 12, marginTop: 2 },
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
