import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { useTogglePaymentPaid, type UpcomingPaymentOut } from "../services/queries/plan";
import { colors } from "../theme/colors";
import { currentMonthYYYYMM } from "../utils/dates";
import MoneyText from "./MoneyText";

export function formatDeadline(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(`${iso}T12:00:00`);
  return d.toLocaleDateString("es-CO", { day: "numeric", month: "short" });
}

function deadlineColor(daysLeft: number | null): string {
  if (daysLeft === null) return colors.textSecondary;
  if (daysLeft <= 3) return colors.danger;
  if (daysLeft <= 7) return colors.warning;
  return colors.textSecondary;
}

// One commitment from /cashflow.checklist; tap toggles paid for the current
// month. Shared by the Plan screen and the Dashboard's pending-payments card.
export default function PaymentChecklistRow({
  item,
  index,
}: {
  item: UpcomingPaymentOut;
  index: number;
}) {
  const dateLabel = formatDeadline(item.deadline);
  const toggleMut = useTogglePaymentPaid();
  const paid = item.is_paid;

  function toggle() {
    if (!item.id || toggleMut.isPending) return;
    toggleMut.mutate({ id: item.id, paidMonth: paid ? null : currentMonthYYYYMM() });
  }

  return (
    <Pressable
      style={({ pressed }) => [
        styles.checkRow,
        index > 0 && styles.checkRowBorder,
        pressed && styles.pressed,
      ]}
      onPress={toggle}
      accessibilityLabel={paid ? `Desmarcar ${item.name}` : `Marcar ${item.name} como pagado`}
    >
      <Ionicons
        name={paid ? "checkmark-circle" : "ellipse-outline"}
        size={22}
        color={paid ? colors.success : colors.textSecondary}
      />
      <View style={styles.rowBody}>
        <View style={styles.checkNameRow}>
          <Text style={[styles.rowName, paid && styles.rowNamePaid]} numberOfLines={1}>
            {item.name}
          </Text>
          {item.is_debt_payment ? (
            <Ionicons name="card" size={13} color={colors.danger} />
          ) : null}
        </View>
        {paid ? (
          <Text style={[styles.rowMeta, { color: colors.success }]}>pagado este mes</Text>
        ) : dateLabel ? (
          <Text style={[styles.rowMeta, { color: deadlineColor(item.days_left) }]}>
            vence {dateLabel}
            {item.days_left !== null ? ` · ${item.days_left} días` : ""}
          </Text>
        ) : (
          <Text style={styles.rowMeta}>sin fecha límite</Text>
        )}
      </View>
      <MoneyText value={item.amount} size="sm" style={paid ? styles.amountPaid : undefined} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  pressed: { opacity: 0.7 },
  checkRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingVertical: 12,
  },
  checkRowBorder: { borderTopWidth: 1, borderTopColor: colors.border },
  checkNameRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  rowBody: { flex: 1 },
  rowName: { color: colors.textPrimary, fontSize: 14, fontWeight: "600" },
  rowMeta: { color: colors.textSecondary, fontSize: 12, marginTop: 2 },
  rowNamePaid: { color: colors.textSecondary, textDecorationLine: "line-through" },
  amountPaid: { color: colors.textSecondary, textDecorationLine: "line-through" },
});
