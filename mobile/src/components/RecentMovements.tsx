import { Pressable, StyleSheet, Text, View } from "react-native";

import { useTransactions } from "../services/queries/transactions";
import { colors } from "../theme/colors";
import { daysAgo, formatShortDay } from "../utils/dates";
import TransactionRow from "./TransactionRow";

/** Last five movements of the month; the whole list lives in Movimientos. */
export default function RecentMovements({
  month,
  onSeeAll,
}: {
  month: string;
  onSeeAll: () => void;
}) {
  const { data } = useTransactions({ month, limit: 5 });
  const items = data?.items ?? [];

  return (
    <View>
      <View style={styles.header}>
        <Text style={styles.label}>Últimos movimientos</Text>
        <Pressable onPress={onSeeAll} hitSlop={8}>
          <Text style={styles.link}>Ver todos</Text>
        </Pressable>
      </View>
      {items.length === 0 ? (
        <Text style={styles.empty}>{data ? "Sin movimientos este mes" : "Cargando..."}</Text>
      ) : (
        items.map((t) => (
          <Pressable key={t.id} onPress={onSeeAll}>
            <TransactionRow
              merchant={t.merchant}
              category={t.category}
              amount={t.amount}
              type={t.transaction_type}
              whenLabel={whenLabel(t.occurred_at)}
              note={t.note}
            />
          </Pressable>
        ))
      )}
    </View>
  );
}

function whenLabel(iso: string): string {
  const ago = daysAgo(iso);
  if (ago === 0) return "hoy";
  if (ago === 1) return "ayer";
  return formatShortDay(iso);
}

const styles = StyleSheet.create({
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "baseline",
    marginTop: 20,
    marginBottom: 8,
  },
  label: {
    color: colors.textSecondary,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
  link: { color: colors.primary, fontSize: 12, fontWeight: "600" },
  empty: { color: colors.textSecondary, fontSize: 13, padding: 16, textAlign: "center" },
});
