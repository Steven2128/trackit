import { Ionicons } from "@expo/vector-icons";
import { StyleSheet, Text, View } from "react-native";

import { colors } from "../theme/colors";
import { getCategory } from "../utils/categories";
import CategoryIcon from "./CategoryIcon";
import MoneyText from "./MoneyText";

type Props = {
  merchant: string | null;
  category: string | null;
  amount: string;
  type: "debit" | "credit";
  occurredAt?: string;
  note?: string | null;
  showChevron?: boolean;
};

function formatTime(iso: string): string {
  const d = new Date(iso);
  const hh = `${d.getHours()}`.padStart(2, "0");
  const mm = `${d.getMinutes()}`.padStart(2, "0");
  return `${hh}:${mm}`;
}

export default function TransactionRow({
  merchant,
  category,
  amount,
  type,
  occurredAt,
  note,
  showChevron = false,
}: Props) {
  const cat = getCategory(category);
  const isIncome = type === "credit";
  return (
    <View style={styles.row}>
      <CategoryIcon categoryKey={category} />
      <View style={styles.body}>
        <Text style={styles.merchant} numberOfLines={1}>
          {merchant ?? (isIncome ? "Ingreso" : "Movimiento")}
        </Text>
        <View style={styles.metaRow}>
          <View style={[styles.catPill, { backgroundColor: `${cat.color}22` }]}>
            <Text style={[styles.catPillText, { color: cat.color }]}>{cat.label}</Text>
          </View>
          {occurredAt ? <Text style={styles.time}>{formatTime(occurredAt)}</Text> : null}
        </View>
        {note ? (
          <Text style={styles.note} numberOfLines={1}>
            {note}
          </Text>
        ) : null}
      </View>
      {/* Income stands out in green; expenses stay neutral — red is reserved
          for alerts and debt so every purchase doesn't read as a warning. */}
      <MoneyText value={amount} signed={isIncome} positive={isIncome} size="md" />
      {showChevron ? (
        <Ionicons name="chevron-forward" size={14} color={colors.textSecondary} />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 12,
    marginBottom: 8,
    gap: 12,
  },
  body: { flex: 1, gap: 5 },
  merchant: { color: colors.textPrimary, fontSize: 15, fontWeight: "600" },
  metaRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  catPill: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 999,
  },
  catPillText: { fontSize: 11, fontWeight: "600" },
  time: { color: colors.textSecondary, fontSize: 11, fontVariant: ["tabular-nums"] },
  note: { color: colors.textSecondary, fontSize: 12, fontStyle: "italic" },
});
