import { Pressable, StyleSheet, Text, View } from "react-native";

import type { BudgetAlertStatus, BudgetStatusItem } from "../services/queries/budgets";
import { colors } from "../theme/colors";
import { getCategory } from "../utils/categories";
import MoneyText from "./MoneyText";

const STATUS_COLOR: Record<BudgetAlertStatus, string> = {
  ok: colors.success,
  warning: colors.warning,
  exceeded: colors.danger,
};

type Props = {
  items: BudgetStatusItem[];
  onPress?: () => void;
};

export default function BudgetOverview({ items, onPress }: Props) {
  const sorted = [...items].sort((a, b) => Number(b.pct) - Number(a.pct));
  const totalSpent = items.reduce((sum, i) => sum + Number(i.spent), 0);
  const totalLimit = items.reduce((sum, i) => sum + Number(i.monthly_limit), 0);
  const totalPct = totalLimit > 0 ? (totalSpent / totalLimit) * 100 : 0;
  const totalColor =
    totalPct >= 100 ? colors.danger : totalPct >= 80 ? colors.warning : colors.primary;

  return (
    <Pressable
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
      onPress={onPress}
      accessibilityLabel="Presupuesto del mes, tocá para editar límites"
    >
      <View style={styles.rowTop}>
        <Text style={styles.totalLabel}>Total</Text>
        <Text>
          <MoneyText value={totalSpent} size="sm" /> <Text style={styles.slash}>/</Text>{" "}
          <MoneyText
            value={totalLimit}
            size="sm"
            style={{ color: colors.textSecondary }}
          />
        </Text>
      </View>
      <BarWithPct pct={totalPct} color={totalColor} />

      <View style={styles.divider} />

      {sorted.map((item) => {
        const cat = getCategory(item.category);
        const pct = Number(item.pct);
        return (
          <View key={item.category} style={styles.row}>
            <View style={styles.rowTop}>
              <Text style={styles.rowLabel}>{cat.label}</Text>
              <Text>
                <MoneyText value={item.spent} size="sm" />{" "}
                <Text style={styles.slash}>/</Text>{" "}
                <MoneyText
                  value={item.monthly_limit}
                  size="sm"
                  style={{ color: colors.textSecondary }}
                />
              </Text>
            </View>
            <BarWithPct pct={pct} color={STATUS_COLOR[item.status]} />
          </View>
        );
      })}

      <Text style={styles.hint}>Tocá para fijar o editar límites</Text>
    </Pressable>
  );
}

function BarWithPct({ pct, color }: { pct: number; color: string }) {
  return (
    <View style={styles.barRow}>
      <View style={styles.barTrack}>
        <View
          style={[
            styles.barFill,
            { width: `${Math.min(Math.max(pct, 0), 100)}%`, backgroundColor: color },
          ]}
        />
      </View>
      <Text style={[styles.pctLabel, { color }]}>{Math.round(pct)}%</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 14,
    gap: 8,
  },
  pressed: { opacity: 0.7 },
  row: { gap: 8 },
  rowTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  totalLabel: { color: colors.textPrimary, fontSize: 15, fontWeight: "700" },
  rowLabel: { color: colors.textPrimary, fontSize: 14, fontWeight: "600" },
  slash: { color: colors.textSecondary },
  divider: { height: 1, backgroundColor: colors.border, marginVertical: 4 },
  barRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  barTrack: {
    flex: 1,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.background,
    overflow: "hidden",
  },
  barFill: { height: 8, borderRadius: 4 },
  // Fixed width keeps every bar the same length regardless of "7%" vs "120%".
  pctLabel: {
    width: 40,
    textAlign: "right",
    fontSize: 12,
    fontWeight: "700",
    fontVariant: ["tabular-nums"],
  },
  hint: { color: colors.textSecondary, fontSize: 11, textAlign: "center", marginTop: 2 },
});
