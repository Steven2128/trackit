import { Ionicons } from "@expo/vector-icons";
import { useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import {
  useCreateFundHold,
  useDeleteFundHold,
  useFundHolds,
} from "../services/queries/accounts";
import { usePlannedPayments } from "../services/queries/plan";
import { colors } from "../theme/colors";
import { Alert } from "../utils/alert";
import { formatCOPInput, parseCOP } from "../utils/currency";
import MoneyText from "./MoneyText";

/** "Plata que no es tuya": money kept in your accounts for someone else (a
 *  sibling's share of the rent). The cash position doesn't count it as
 *  yours; it moves no money. Remove it once it's handed over or used. */
export default function FundHoldsSection() {
  const { data: holds } = useFundHolds();
  const create = useCreateFundHold();
  const remove = useDeleteFundHold();
  const [name, setName] = useState("");
  const [amount, setAmount] = useState("");
  const [paymentId, setPaymentId] = useState<string | null>(null);
  // Recurring bills only: a hold is for the rent, not for a card payment.
  const payments = (usePlannedPayments().data ?? []).filter(
    (p) => !p.is_debt_payment && p.due_date === null,
  );
  const paymentName = (id: string | null) => payments.find((p) => p.id === id)?.name;

  function handleAdd() {
    const value = parseCOP(amount);
    if (name.trim() === "" || value <= 0) {
      Alert.alert("Faltan datos", "Poné de quién es la plata y cuánto es.");
      return;
    }
    create.mutate(
      { name: name.trim(), amount: value.toString(), planned_payment_id: paymentId },
      {
        onSuccess: () => {
          setName("");
          setAmount("");
          setPaymentId(null);
        },
        onError: (e) => Alert.alert("Error", e instanceof Error ? e.message : "No se pudo guardar."),
      },
    );
  }

  function confirmRemove(id: string, label: string) {
    Alert.alert(
      "Quitar",
      `¿Ya no tenés la plata de "${label}"? (la entregaste o se usó para lo que era)`,
      [
        { text: "Cancelar", style: "cancel" },
        { text: "Quitar", style: "destructive", onPress: () => remove.mutate(id) },
      ],
    );
  }

  return (
    <View style={styles.box}>
      <Text style={styles.title}>Plata que no es tuya</Text>
      <Text style={styles.hint}>
        Está en tus cuentas o en tu efectivo, pero no la cuento como tuya para gastar.
      </Text>
      {(holds ?? []).map((h) => (
        <View key={h.id} style={styles.row}>
          <Text style={styles.name}>
            {h.name}
            {paymentName(h.planned_payment_id) ? (
              <Text style={styles.forPayment}> · para {paymentName(h.planned_payment_id)}</Text>
            ) : null}
          </Text>
          <MoneyText value={h.amount} size="sm" />
          <Pressable
            onPress={() => confirmRemove(h.id, h.name)}
            hitSlop={10}
            accessibilityLabel={`Quitar ${h.name}`}
          >
            <Ionicons name="trash-outline" size={18} color={colors.danger} />
          </Pressable>
        </View>
      ))}
      <View style={styles.form}>
        <TextInput
          style={[styles.input, styles.inputName]}
          placeholder="p.ej. Hermano (arriendo)"
          placeholderTextColor={colors.textSecondary}
          value={name}
          onChangeText={setName}
          maxLength={128}
        />
        <TextInput
          style={[styles.input, styles.inputAmount]}
          placeholder="Monto"
          placeholderTextColor={colors.textSecondary}
          value={amount}
          onChangeText={(v) => setAmount(formatCOPInput(v))}
          keyboardType="numeric"
        />
        <Pressable
          style={[styles.addBtn, create.isPending && { opacity: 0.5 }]}
          disabled={create.isPending}
          onPress={handleAdd}
          accessibilityLabel="Agregar plata que no es tuya"
        >
          <Ionicons name="add" size={20} color="#fff" />
        </Pressable>
      </View>
      {payments.length > 0 ? (
        <>
          <Text style={styles.hint}>
            ¿Es para un pago? Elegilo y en tu quincena ese pago se muestra con esta plata sumada.
          </Text>
          <View style={styles.chips}>
            {payments.map((p) => (
              <Pressable
                key={p.id}
                onPress={() => setPaymentId(paymentId === p.id ? null : p.id)}
                style={[styles.chip, paymentId === p.id && styles.chipActive]}
              >
                <Text style={[styles.chipText, paymentId === p.id && styles.chipTextActive]}>
                  {p.name}
                </Text>
              </Pressable>
            ))}
          </View>
        </>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 14,
    marginTop: 12,
    gap: 8,
  },
  title: { color: colors.textPrimary, fontSize: 15, fontWeight: "600" },
  hint: { color: colors.textSecondary, fontSize: 12, lineHeight: 17 },
  row: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 4 },
  name: { color: colors.textPrimary, fontSize: 14, flex: 1 },
  form: { flexDirection: "row", gap: 8, alignItems: "center", marginTop: 4 },
  input: {
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    padding: 10,
    fontSize: 14,
    color: colors.textPrimary,
  },
  inputName: { flex: 2, minWidth: 0 },
  inputAmount: { flex: 1, minWidth: 0 },
  addBtn: { backgroundColor: colors.primary, borderRadius: 8, padding: 10 },
  forPayment: { color: colors.textSecondary, fontSize: 12 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
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
});
