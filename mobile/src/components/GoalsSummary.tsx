import { Pressable, StyleSheet, Text, View } from "react-native";

import type { SavingsGoalOut } from "../services/queries/goals";
import { colors } from "../theme/colors";
import { formatIsoDay } from "../utils/dates";
import MoneyText from "./MoneyText";

/** Paydays (5th and 20th) from tomorrow through `targetIso`, inclusive. */
export function paydaysUntil(targetIso: string, today = new Date()): number {
  const end = new Date(`${targetIso}T12:00:00`);
  let count = 0;
  const d = new Date(today.getFullYear(), today.getMonth(), 1, 12);
  while (d <= end) {
    for (const day of [5, 20]) {
      const pay = new Date(d.getFullYear(), d.getMonth(), day, 12);
      if (pay > today && pay <= end) count += 1;
    }
    d.setMonth(d.getMonth() + 1);
  }
  return count;
}

/** Savings goals with progress and how much to set aside each payday to
 *  get there on time. */
export default function GoalsSummary({
  goals,
  onPress,
}: {
  goals: SavingsGoalOut[];
  onPress: () => void;
}) {
  return (
    <Pressable style={({ pressed }) => [styles.card, pressed && { opacity: 0.7 }]} onPress={onPress}>
      {goals.length === 0 ? (
        <Text style={styles.empty}>Todavía no tenés metas. Tocá para crear una.</Text>
      ) : (
        goals.map((g) => {
          const left = Math.max(0, Number(g.target_amount) - Number(g.current_amount));
          const paydays = g.target_date ? paydaysUntil(g.target_date) : 0;
          const perPayday = paydays > 0 ? Math.ceil(left / paydays / 1000) * 1000 : left;
          return (
            <View key={g.id} style={styles.goal}>
              <View style={styles.row}>
                <Text style={styles.name} numberOfLines={1}>
                  {g.name}
                </Text>
                <Text style={styles.amounts}>
                  <MoneyText value={g.current_amount} size="sm" />
                  <Text style={styles.muted}> / </Text>
                  <MoneyText value={g.target_amount} size="sm" style={styles.muted} />
                </Text>
              </View>
              <View style={styles.track}>
                <View style={[styles.fill, { width: `${Math.min(100, g.pct)}%` }]} />
              </View>
              <Text style={styles.meta}>
                {left === 0 ? (
                  "¡Meta cumplida!"
                ) : g.target_date ? (
                  paydays > 0 ? (
                    <>
                      Apartá <MoneyText value={perPayday} size="sm" style={styles.strong} /> por
                      quincena ({paydays}) para llegar el {formatIsoDay(g.target_date)}
                    </>
                  ) : (
                    <>Venció el {formatIsoDay(g.target_date)}: te faltan <MoneyText value={left} size="sm" style={styles.strong} /></>
                  )
                ) : (
                  <>
                    Te faltan <MoneyText value={left} size="sm" style={styles.strong} />
                  </>
                )}
              </Text>
            </View>
          );
        })
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 14,
    gap: 14,
  },
  goal: { gap: 6 },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "baseline", gap: 8 },
  name: { color: colors.textPrimary, fontSize: 15, fontWeight: "600", flexShrink: 1 },
  amounts: { color: colors.textPrimary },
  muted: { color: colors.textSecondary },
  track: { height: 6, borderRadius: 3, backgroundColor: colors.background, overflow: "hidden" },
  fill: { height: 6, borderRadius: 3, backgroundColor: colors.success },
  meta: { color: colors.textSecondary, fontSize: 12 },
  strong: { color: colors.textPrimary, fontWeight: "600" },
  empty: { color: colors.textSecondary, fontSize: 13, textAlign: "center" },
});
