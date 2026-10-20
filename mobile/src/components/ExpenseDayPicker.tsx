import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { useNetWorth } from "../services/queries/accounts";
import { colors } from "../theme/colors";
import { expenseInstant, formatShortDay } from "../utils/dates";

// How far back the stepper goes; older spending isn't worth typing in.
const MAX_DAYS_AGO = 90;

const QUICK = [
  { ago: 0, label: "Hoy" },
  { ago: 1, label: "Ayer" },
  { ago: 2, label: "Anteayer" },
];

type Props = {
  /** Local days back: 0 = today, 1 = yesterday… */
  daysAgo: number;
  onChange: (daysAgo: number) => void;
};

/** Day a cash expense happened. Warns when the day is before the last cash
 *  count: that money was already inside the count, so the backend keeps the
 *  Efectivo balance where it was and only the spending moves. */
export default function ExpenseDayPicker({ daysAgo, onChange }: Props) {
  // Past the quick chips, the day is picked with the stepper.
  const other = daysAgo > 2;
  const { data } = useNetWorth();
  const countedAt = data?.accounts.find((a) => a.kind === "cash")?.last_reconciled_at ?? null;

  const instant = expenseInstant(daysAgo);
  const beforeCount =
    countedAt !== null && new Date(instant).getTime() < new Date(countedAt).getTime();

  return (
    <View>
      <View style={styles.chips}>
        {QUICK.map((q) => {
          const active = !other && daysAgo === q.ago;
          return (
            <Pressable
              key={q.ago}
              onPress={() => onChange(q.ago)}
              style={[styles.chip, active && styles.chipActive]}
            >
              <Text style={[styles.chipText, active && styles.chipTextActive]}>{q.label}</Text>
            </Pressable>
          );
        })}
        <Pressable
          onPress={() => {
            if (daysAgo < 3) onChange(3);
          }}
          style={[styles.chip, other && styles.chipActive]}
        >
          <Text style={[styles.chipText, other && styles.chipTextActive]}>Otro día</Text>
        </Pressable>
      </View>

      {other ? (
        <View style={styles.stepper}>
          <Pressable
            onPress={() => onChange(Math.min(daysAgo + 1, MAX_DAYS_AGO))}
            disabled={daysAgo >= MAX_DAYS_AGO}
            hitSlop={8}
            accessibilityLabel="Día anterior"
            style={daysAgo >= MAX_DAYS_AGO && styles.disabled}
          >
            <Ionicons name="chevron-back" size={22} color={colors.textPrimary} />
          </Pressable>
          <Text style={styles.stepperDay}>{formatShortDay(instant)}</Text>
          <Pressable
            // No future days: spending is logged after it happens.
            onPress={() => onChange(Math.max(daysAgo - 1, 0))}
            disabled={daysAgo <= 0}
            hitSlop={8}
            accessibilityLabel="Día siguiente"
            style={daysAgo <= 0 && styles.disabled}
          >
            <Ionicons name="chevron-forward" size={22} color={colors.textPrimary} />
          </Pressable>
        </View>
      ) : null}

      {beforeCount ? (
        <Text style={styles.notice}>
          Contaste el efectivo el {formatShortDay(countedAt!)}: este gasto ya estaba en ese
          conteo. Se registra como gasto, pero tu efectivo no cambia.
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 10 },
  chip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { color: colors.textSecondary, fontSize: 13, fontWeight: "600" },
  chipTextActive: { color: "#fff" },
  stepper: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginBottom: 10,
  },
  stepperDay: { color: colors.textPrimary, fontSize: 14, fontWeight: "600" },
  disabled: { opacity: 0.3 },
  notice: {
    color: colors.warning,
    backgroundColor: colors.warningSoft,
    borderRadius: 8,
    padding: 10,
    fontSize: 12,
    lineHeight: 17,
    marginBottom: 10,
  },
});
