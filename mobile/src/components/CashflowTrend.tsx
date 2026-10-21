import { StyleSheet, Text, View } from "react-native";

import type { MonthTrendEntry } from "../services/queries/dashboard";
import { colors } from "../theme/colors";
import MoneyText from "./MoneyText";

const MES_ABREV = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const BAR_HEIGHT = 140;

// Bar labels: $3,4M / $630k — full figures don't fit under a bar.
function compactCOP(n: number): string {
  if (n >= 1_000_000) return `$${(Math.round(n / 100_000) / 10).toString().replace(".", ",")}M`;
  if (n >= 1_000) return `$${Math.round(n / 1_000)}k`;
  return n > 0 ? `$${Math.round(n)}` : "0";
}

/** Received vs spent, month by month: paired bars drawn with plain Views
 *  (chart-kit can't group bars) plus what was left over each month. */
export default function CashflowTrend({ months }: { months: MonthTrendEntry[] }) {
  const max = Math.max(
    1,
    ...months.flatMap((m) => [Number(m.total_spent), Number(m.total_received)]),
  );
  const withIncome = months.filter((m) => Number(m.total_received) > 0);
  const saved = withIncome.reduce(
    (s, m) => s + Number(m.total_received) - Number(m.total_spent),
    0,
  );
  const received = withIncome.reduce((s, m) => s + Number(m.total_received), 0);
  const rate = received > 0 ? Math.round((saved / received) * 100) : null;

  return (
    <View style={styles.card}>
      <View style={styles.legend}>
        <Legend color={colors.success} label="Recibido" />
        <Legend color={colors.primary} label="Gastado" />
        {rate !== null ? (
          <Text style={styles.rate}>
            Ahorro promedio{" "}
            <Text style={{ color: rate >= 0 ? colors.success : colors.danger, fontWeight: "700" }}>
              {rate}%
            </Text>
          </Text>
        ) : null}
      </View>
      <View style={styles.bars}>
        {months.map((m) => {
          const inc = Number(m.total_received);
          const out = Number(m.total_spent);
          const left = inc - out;
          return (
            <View key={m.month} style={styles.month}>
              <View style={styles.pair}>
                <Bar value={inc} max={max} color={colors.success} />
                <Bar value={out} max={max} color={colors.primary} />
              </View>
              <Text style={styles.monthLabel}>{MES_ABREV[Number(m.month.slice(5)) - 1]}</Text>
              <Text
                style={[
                  styles.left,
                  { color: inc === 0 ? colors.textSecondary : left >= 0 ? colors.success : colors.danger },
                ]}
                numberOfLines={1}
              >
                {inc === 0 ? "—" : `${left >= 0 ? "+" : "-"}${compactCOP(Math.abs(left))}`}
              </Text>
            </View>
          );
        })}
      </View>
      {withIncome.length > 0 ? (
        <Text style={styles.foot}>
          En {withIncome.length} {withIncome.length === 1 ? "mes" : "meses"} con ingresos te{" "}
          {saved >= 0 ? "sobraron" : "faltaron"}{" "}
          <MoneyText
            value={Math.abs(saved)}
            size="sm"
            style={{ color: saved >= 0 ? colors.success : colors.danger, fontWeight: "600" }}
          />
          .
        </Text>
      ) : null}
    </View>
  );
}

function Bar({ value, max, color }: { value: number; max: number; color: string }) {
  const h = value > 0 ? Math.max(3, (value / max) * BAR_HEIGHT) : 0;
  return (
    <View style={styles.barSlot}>
      {value > 0 ? <Text style={styles.barValue}>{compactCOP(value)}</Text> : null}
      <View style={[styles.bar, { height: h, backgroundColor: color }]} />
    </View>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <View style={styles.legendItem}>
      <View style={[styles.dot, { backgroundColor: color }]} />
      <Text style={styles.legendText}>{label}</Text>
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
  },
  legend: { flexDirection: "row", alignItems: "center", gap: 14, marginBottom: 12 },
  legendItem: { flexDirection: "row", alignItems: "center", gap: 6 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  legendText: { color: colors.textSecondary, fontSize: 12 },
  rate: { color: colors.textSecondary, fontSize: 12, marginLeft: "auto" },
  bars: { flexDirection: "row", alignItems: "flex-end" },
  month: { flex: 1, alignItems: "center", minWidth: 0 },
  pair: { flexDirection: "row", alignItems: "flex-end", gap: 3, height: BAR_HEIGHT + 16 },
  barSlot: { alignItems: "center", justifyContent: "flex-end" },
  barValue: { color: colors.textSecondary, fontSize: 9, marginBottom: 2 },
  bar: { width: 14, borderTopLeftRadius: 4, borderTopRightRadius: 4 },
  monthLabel: { color: colors.textSecondary, fontSize: 11, marginTop: 6 },
  left: { fontSize: 10, fontWeight: "600", marginTop: 2 },
  foot: { color: colors.textSecondary, fontSize: 12, marginTop: 12 },
});
