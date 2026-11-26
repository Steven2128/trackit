import { Ionicons } from "@expo/vector-icons";
import { StyleSheet, Text, View } from "react-native";

import { colors } from "../theme/colors";
import { getCategory } from "../utils/categories";
import { formatCOP } from "../utils/currency";
import CategoryIcon from "./CategoryIcon";
import MoneyText from "./MoneyText";

type Props = {
  merchant: string | null;
  category: string | null;
  amount: string;
  type: "debit" | "credit";
  occurredAt?: string;
  /** Shown instead of the time (e.g. "ayer" in lists that span days). */
  whenLabel?: string;
  note?: string | null;
  /** Part someone else covers on a shared expense. */
  sharedAmount?: string | null;
  showChevron?: boolean;
  /** Full-page lists: bigger type and a category-colored accent edge. */
  prominent?: boolean;
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
  whenLabel,
  note,
  sharedAmount,
  showChevron = false,
  prominent = false,
}: Props) {
  const cat = getCategory(category, type);
  const isIncome = type === "credit";
  return (
    <View
      style={[
        styles.row,
        prominent && styles.rowProminent,
        prominent && { borderLeftColor: cat.color },
      ]}
    >
      <CategoryIcon categoryKey={category} type={type} size={prominent ? 42 : 36} />
      <View style={styles.body}>
        <Text
          style={[styles.merchant, prominent && styles.merchantProminent]}
          numberOfLines={1}
        >
          {merchant ?? (isIncome ? "Ingreso" : "Movimiento")}
        </Text>
        <View style={styles.metaRow}>
          <View style={[styles.catPill, { backgroundColor: `${cat.color}22` }]}>
            <Text style={[styles.catPillText, { color: cat.color }]}>{cat.label}</Text>
          </View>
          {whenLabel || occurredAt ? (
            <Text style={styles.time}>{whenLabel ?? formatTime(occurredAt!)}</Text>
          ) : null}
        </View>
        {sharedAmount ? (
          <Text style={styles.shared} numberOfLines={1}>
            Compartido · tu parte {formatCOP(Number(amount) - Number(sharedAmount))}
          </Text>
        ) : null}
        {note ? (
          <Text style={styles.note} numberOfLines={1}>
            {note}
          </Text>
        ) : null}
      </View>
      {/* Income stands out in green; expenses stay neutral — red is reserved
          for alerts and debt so every purchase doesn't read as a warning. */}
      <MoneyText value={amount} signed={isIncome} positive={isIncome}
        size={prominent ? "lg" : "md"}
      />
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
  rowProminent: {
    backgroundColor: colors.surfaceMuted,
    borderLeftWidth: 4,
    paddingVertical: 14,
    paddingHorizontal: 16,
    gap: 14,
  },
  body: { flex: 1, gap: 5 },
  merchant: { color: colors.textPrimary, fontSize: 15, fontWeight: "600" },
  merchantProminent: { fontSize: 16, fontWeight: "700" },
  metaRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  catPill: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 999,
  },
  catPillText: { fontSize: 11, fontWeight: "600" },
  time: { color: colors.textSecondary, fontSize: 11, fontVariant: ["tabular-nums"] },
  note: { color: colors.textSecondary, fontSize: 12, fontStyle: "italic" },
  shared: { color: colors.primary, fontSize: 12, fontWeight: "500" },
});
