import { StyleSheet, Text, View } from "react-native";

import type { HealthScoreResponse } from "../services/queries/insights";
import { colors } from "../theme/colors";

type Key = "debt" | "budgets" | "savings" | "anomalies";

// Weights and tips mirror backend app/services/health_score.py.
const PARTS: { key: Key; label: string; max: number; tip: string }[] = [
  {
    key: "debt",
    label: "Deuda",
    max: 30,
    tip: "Los mínimos de tus deudas pesan sobre tu ingreso: abonar a capital es lo que más sube el puntaje.",
  },
  {
    key: "budgets",
    label: "Presupuestos",
    max: 25,
    tip: "Algún presupuesto pasó el 80%: frená ahí lo que queda del mes.",
  },
  {
    key: "savings",
    label: "Ahorro",
    max: 25,
    tip: "Tus metas de ahorro no avanzan: abonales aunque sea un poco cada quincena.",
  },
  {
    key: "anomalies",
    label: "Gasto inusual",
    max: 20,
    tip: "Este mes gastaste fuera de lo normal en alguna categoría.",
  },
];

export function scoreColor(total: number): string {
  if (total >= 75) return colors.success;
  if (total >= 50) return colors.warning;
  return colors.danger;
}

/** Health score with its four parts and a tip for the weakest one. */
export default function HealthScoreCard({ score }: { score: HealthScoreResponse }) {
  const weakest = PARTS.map((p) => ({ ...p, ratio: score[p.key] / p.max }))
    .filter((p) => p.ratio < 1)
    .sort((a, b) => a.ratio - b.ratio)[0];

  return (
    <View style={styles.card}>
      <View style={styles.head}>
        <Text style={styles.total}>
          <Text style={{ color: scoreColor(score.total) }}>{score.total}</Text>
          <Text style={styles.max}>/100</Text>
        </Text>
        <Text style={styles.title}>Salud financiera</Text>
      </View>
      {PARTS.map((p) => {
        const value = score[p.key];
        const ratio = value / p.max;
        const color = ratio >= 0.8 ? colors.success : ratio >= 0.4 ? colors.warning : colors.danger;
        return (
          <View key={p.key} style={styles.part}>
            <Text style={styles.partLabel}>{p.label}</Text>
            <View style={styles.track}>
              <View style={[styles.fill, { width: `${ratio * 100}%`, backgroundColor: color }]} />
            </View>
            <Text style={styles.partValue}>
              {value}/{p.max}
            </Text>
          </View>
        );
      })}
      {weakest ? <Text style={styles.tip}>💡 {weakest.tip}</Text> : null}
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
  head: { flexDirection: "row", alignItems: "baseline", gap: 10, marginBottom: 4 },
  total: { fontSize: 26, fontWeight: "700" },
  max: { color: colors.textSecondary, fontSize: 13, fontWeight: "600" },
  title: { color: colors.textSecondary, fontSize: 13 },
  part: { flexDirection: "row", alignItems: "center", gap: 10 },
  partLabel: { color: colors.textPrimary, fontSize: 13, width: 100 },
  track: {
    flex: 1,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.background,
    overflow: "hidden",
  },
  fill: { height: 6, borderRadius: 3 },
  partValue: { color: colors.textSecondary, fontSize: 12, width: 40, textAlign: "right" },
  tip: { color: colors.textSecondary, fontSize: 12, lineHeight: 17, marginTop: 4 },
});
