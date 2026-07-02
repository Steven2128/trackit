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
};

export default function TransactionRow({ merchant, category, amount, type }: Props) {
  const cat = getCategory(category);
  const isIncome = type === "credit";
  return (
    <View style={styles.row}>
      <CategoryIcon categoryKey={category} />
      <View style={styles.body}>
        <Text style={styles.merchant} numberOfLines={1}>
          {merchant ?? "—"}
        </Text>
        <Text style={styles.cat}>{cat.label}</Text>
      </View>
      <MoneyText
        value={amount}
        signed={isIncome}
        positive={isIncome}
        size="md"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 12,
    marginBottom: 8,
    gap: 12,
  },
  body: { flex: 1 },
  merchant: { color: colors.textPrimary, fontSize: 14, fontWeight: "600" },
  cat: { color: colors.textSecondary, fontSize: 11, marginTop: 2 },
});
