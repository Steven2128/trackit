import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { useSharedSummary, type TransactionOut } from "../services/queries/transactions";
import { colors } from "../theme/colors";
import { daysAgo, formatShortDay } from "../utils/dates";
import CategoryPickerSheet from "./CategoryPickerSheet";
import MoneyText from "./MoneyText";
import TransactionRow from "./TransactionRow";

const COLLAPSED = 3;

/** The tab with whoever shares expenses with the user: their parts of
 * shared bills, what they paid back, what's still owed. Hidden until the
 * first shared expense. */
export default function SharedExpensesCard() {
  const { data } = useSharedSummary();
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState<TransactionOut | null>(null);

  if (!data || (Number(data.covered_for_others) === 0 && Number(data.reimbursed) === 0)) {
    return null;
  }
  const items = expanded ? data.items : data.items.slice(0, COLLAPSED);
  const pending = Number(data.pending);

  return (
    <View>
      <View style={styles.header}>
        <Text style={styles.label}>Compartido</Text>
        {data.items.length > COLLAPSED ? (
          <Pressable onPress={() => setExpanded((e) => !e)} hitSlop={8}>
            <Text style={styles.link}>{expanded ? "Ver menos" : "Ver todo"}</Text>
          </Pressable>
        ) : null}
      </View>

      <View style={styles.summary}>
        <Text style={styles.summaryLabel}>{pending > 0 ? "Te deben" : "Están al día"}</Text>
        <MoneyText value={pending} size="lg" positive={pending > 0} />
        <Text style={styles.summaryMeta}>
          Pusiste por otros <MoneyText value={data.covered_for_others} size="sm" /> · te
          devolvieron <MoneyText value={data.reimbursed} size="sm" />
        </Text>
        <Text style={styles.hint}>
          Cuando te devuelvan, marcá esa entrada como Reembolso para descontarla.
        </Text>
      </View>

      {items.map((t) => (
        <Pressable key={t.id} onPress={() => setEditing(t)}>
          <TransactionRow
            merchant={t.merchant}
            category={t.category}
            amount={t.amount}
            type={t.transaction_type}
            whenLabel={whenLabel(t.occurred_at)}
            note={t.note}
            sharedAmount={t.shared_amount}
          />
        </Pressable>
      ))}

      <CategoryPickerSheet
        isVisible={editing !== null}
        transaction={editing}
        onClose={() => setEditing(null)}
      />
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
  summary: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 14,
    marginBottom: 8,
    gap: 4,
  },
  summaryLabel: { color: colors.textSecondary, fontSize: 12 },
  summaryMeta: { color: colors.textSecondary, fontSize: 12, marginTop: 2 },
  hint: { color: colors.textSecondary, fontSize: 11, fontStyle: "italic", marginTop: 4 },
});
