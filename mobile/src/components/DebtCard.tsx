import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors } from "../theme/colors";
import type { DebtOut } from "../services/queries/debts";
import MoneyText from "./MoneyText";

type Props = {
  debt: DebtOut;
  onPress: (debt: DebtOut) => void;
};

export default function DebtCard({ debt, onPress }: Props) {
  const rate = debt.interest_rate ? `${Number(debt.interest_rate)}% EA` : null;
  const min = debt.minimum_payment ? `Pago mín ${Number(debt.minimum_payment).toLocaleString("es-CO")}` : null;
  return (
    <Pressable style={styles.card} onPress={() => onPress(debt)}>
      <View style={styles.left}>
        <View style={styles.titleRow}>
          <Text style={styles.bank} numberOfLines={1}>{debt.bank_name}</Text>
          {rate ? (
            <View style={styles.pill}>
              <Text style={styles.pillText}>{rate}</Text>
            </View>
          ) : null}
        </View>
        {min ? <Text style={styles.meta}>{min}</Text> : null}
      </View>
      <MoneyText value={debt.total_amount} size="md" />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 12,
    marginBottom: 8,
    borderLeftWidth: 3,
    borderLeftColor: colors.danger,
    gap: 12,
  },
  left: { flex: 1 },
  titleRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  bank: { color: colors.textPrimary, fontSize: 14, fontWeight: "600" },
  pill: {
    backgroundColor: colors.surfaceMuted,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
  },
  pillText: { color: colors.textSecondary, fontSize: 10 },
  meta: { color: colors.textSecondary, fontSize: 11, marginTop: 3 },
});
