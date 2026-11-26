import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { useContacts } from "../services/queries/contacts";
import { colors } from "../theme/colors";
import { formatCOPInput, parseCOP, toCOPInput } from "../utils/currency";
import ContactPicker from "./ContactPicker";
import MoneyText from "./MoneyText";
import { BottomSheetTextInput } from "./sheet";

export type ShareRow = { contactId: string; amount: string };

type Props = {
  total: number;
  rows: ShareRow[];
  onChange: (rows: ShareRow[]) => void;
};

/** Equal parts for everyone, the user included: total / (people + 1). */
function equalSplit(rows: ShareRow[], total: number): ShareRow[] {
  const part = Math.round(total / (rows.length + 1));
  return rows.map((r) => ({ ...r, amount: toCOPInput(String(part)) }));
}

/** Split a debit the user paid among several people: pick them, then each
 * one's part. Parts follow an equal split until one is typed by hand. */
export default function ShareSplitEditor({ total, rows, onChange }: Props) {
  const { data: contacts } = useContacts();
  // Rows loaded from a saved split were set by hand already.
  const [edited, setEdited] = useState(rows.length > 0);
  const nameOf = (id: string) => contacts?.find((c) => c.id === id)?.name ?? "…";

  function toggle(id: string | null) {
    if (!id) return;
    const next = rows.some((r) => r.contactId === id)
      ? rows.filter((r) => r.contactId !== id)
      : [...rows, { contactId: id, amount: "" }];
    onChange(edited ? next : equalSplit(next, total));
  }

  function setPart(id: string, value: string) {
    setEdited(true);
    onChange(rows.map((r) => (r.contactId === id ? { ...r, amount: formatCOPInput(value) } : r)));
  }

  function splitEvenly() {
    setEdited(false);
    onChange(equalSplit(rows, total));
  }

  const others = rows.reduce((sum, r) => sum + parseCOP(r.amount), 0);
  const mine = total - others;

  return (
    <View style={styles.wrap}>
      <Text style={styles.label}>¿Con quién lo compartís?</Text>
      <ContactPicker
        value={rows.map((r) => r.contactId)}
        onChange={toggle}
        allowNone={false}
      />
      {rows.length > 0 ? (
        <>
          <Text style={styles.label}>Lo que pone cada uno (COP)</Text>
          {rows.map((r) => (
            <View key={r.contactId} style={styles.row}>
              <Text style={styles.name} numberOfLines={1}>
                {nameOf(r.contactId)}
              </Text>
              <BottomSheetTextInput
                style={styles.input}
                placeholder="0"
                placeholderTextColor={colors.textSecondary}
                value={r.amount}
                onChangeText={(v) => setPart(r.contactId, v)}
                keyboardType="number-pad"
                inputMode="numeric"
              />
            </View>
          ))}
          <Pressable onPress={splitEvenly} hitSlop={8}>
            <Text style={styles.link}>
              Dividir en partes iguales ({rows.length + 1} con vos)
            </Text>
          </Pressable>
          <Text style={[styles.hint, mine < 0 && styles.error]}>
            {mine < 0 ? (
              "Las partes de los demás pasan del total."
            ) : (
              <>
                Tu parte: <MoneyText value={String(mine)} size="sm" /> — es lo que cuenta como
                gasto. Cuando cada uno te devuelva, registralo como Reembolso.
              </>
            )}
          </Text>
        </>
      ) : (
        <Text style={styles.hint}>Elegí una o varias personas.</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 8 },
  label: {
    color: colors.textSecondary,
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginTop: 8,
  },
  row: { flexDirection: "row", alignItems: "center", gap: 10 },
  name: { flex: 1, color: colors.textPrimary, fontSize: 14 },
  input: {
    width: 140,
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    padding: 10,
    fontSize: 14,
    color: colors.textPrimary,
    textAlign: "right",
  },
  link: { color: colors.primary, fontSize: 13, fontWeight: "600" },
  hint: { color: colors.textSecondary, fontSize: 12, marginTop: 4 },
  error: { color: colors.danger },
});
