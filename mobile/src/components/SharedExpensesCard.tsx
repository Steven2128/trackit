import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { useSharedSummary, type TransactionOut } from "../services/queries/transactions";
import { colors } from "../theme/colors";
import { daysAgo, formatShortDay } from "../utils/dates";
import CategoryPickerSheet from "./CategoryPickerSheet";
import MoneyText from "./MoneyText";
import PersonMovementSheet, { type PersonMovementPreset } from "./PersonMovementSheet";
import TransactionRow from "./TransactionRow";

const COLLAPSED = 3;

/** Who owes whom with each person the user shares expenses or lends money
 * with, plus the movements behind it. Hidden until there's someone or
 * something shared. */
export default function SharedExpensesCard() {
  const { data } = useSharedSummary();
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState<TransactionOut | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [preset, setPreset] = useState<PersonMovementPreset | null>(null);

  const people = data?.people ?? [];
  const legacyPending = Number(data?.pending ?? 0);
  const hasLegacy = Number(data?.covered_for_others ?? 0) > 0 || Number(data?.reimbursed ?? 0) > 0;
  if (!data || (people.length === 0 && !hasLegacy)) return null;

  const person = people.find((p) => p.contact_id === selected) ?? null;
  const filtered = person ? data.items.filter((t) => t.contact_id === person.contact_id) : data.items;
  const items = expanded ? filtered : filtered.slice(0, COLLAPSED);

  function settle(balance: number, contactId: string) {
    setPreset(
      balance > 0
        ? { kind: "received", contactId, amount: balance }
        : { kind: "sent", contactId, amount: -balance },
    );
  }

  return (
    <View>
      <View style={styles.header}>
        <Text style={styles.label}>Compartido</Text>
        <Pressable
          onPress={() => setPreset({ kind: "received", contactId: selected })}
          hitSlop={8}
        >
          <Text style={styles.link}>+ Registrar</Text>
        </Pressable>
      </View>

      <View style={styles.summary}>
        {people.map((p) => {
          const balance = Number(p.balance);
          const isSel = selected === p.contact_id;
          return (
            <View key={p.contact_id}>
              <Pressable
                style={({ pressed }) => [styles.person, isSel && styles.personSel, pressed && styles.pressed]}
                onPress={() => setSelected(isSel ? null : p.contact_id)}
              >
                <Text style={styles.personName}>{p.name}</Text>
                {balance === 0 ? (
                  <Text style={styles.even}>Están al día</Text>
                ) : (
                  <Text style={styles.balanceText}>
                    {balance > 0 ? "te debe " : "le debés "}
                    <MoneyText
                      value={Math.abs(balance)}
                      size="md"
                      positive={balance > 0}
                      negative={balance < 0}
                    />
                  </Text>
                )}
              </Pressable>
              {isSel ? (
                <View style={styles.actions}>
                  {balance !== 0 ? (
                    <Pressable style={styles.actionBtn} onPress={() => settle(balance, p.contact_id)}>
                      <Text style={styles.actionText}>
                        {balance > 0 ? "Me pagó todo" : "Le pagué todo"}
                      </Text>
                    </Pressable>
                  ) : null}
                  <Pressable
                    style={[styles.actionBtn, styles.actionGhost]}
                    onPress={() => setPreset({ kind: "theyPaid", contactId: p.contact_id })}
                  >
                    <Text style={[styles.actionText, styles.actionGhostText]}>Pagó un gasto</Text>
                  </Pressable>
                  <Pressable
                    style={[styles.actionBtn, styles.actionGhost]}
                    onPress={() => setPreset({ kind: "received", contactId: p.contact_id })}
                  >
                    <Text style={[styles.actionText, styles.actionGhostText]}>Otro movimiento</Text>
                  </Pressable>
                </View>
              ) : null}
            </View>
          );
        })}
        {hasLegacy ? (
          <View style={styles.person}>
            <Text style={styles.personName}>Sin persona asignada</Text>
            {legacyPending > 0 ? (
              <Text style={styles.balanceText}>
                te deben <MoneyText value={legacyPending} size="md" positive />
              </Text>
            ) : (
              <Text style={styles.even}>Están al día</Text>
            )}
          </View>
        ) : null}
        <Text style={styles.hint}>
          {people.length === 0
            ? "Tocá + Registrar para agregar a alguien (Jesús, un amigo) y llevar la cuenta con cada uno."
            : "Tocá a una persona para ver sus movimientos y saldar. Para asignar un movimiento, abrilo y elegí la persona."}
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
      {filtered.length > COLLAPSED ? (
        <Pressable onPress={() => setExpanded((e) => !e)} hitSlop={8} style={styles.more}>
          <Text style={styles.link}>{expanded ? "Ver menos" : `Ver todo (${filtered.length})`}</Text>
        </Pressable>
      ) : null}

      <CategoryPickerSheet
        isVisible={editing !== null}
        transaction={editing}
        onClose={() => setEditing(null)}
      />
      <PersonMovementSheet preset={preset} onClose={() => setPreset(null)} />
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
  more: { paddingVertical: 8, alignItems: "center" },
  summary: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 10,
    marginBottom: 8,
    gap: 2,
  },
  person: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 8,
    paddingHorizontal: 6,
    borderRadius: 8,
    gap: 8,
  },
  personSel: { backgroundColor: colors.primarySoft },
  pressed: { opacity: 0.6 },
  personName: { color: colors.textPrimary, fontSize: 14, fontWeight: "600", flexShrink: 1 },
  balanceText: { color: colors.textSecondary, fontSize: 13 },
  even: { color: colors.textSecondary, fontSize: 13 },
  actions: { flexDirection: "row", flexWrap: "wrap", gap: 8, paddingHorizontal: 6, paddingBottom: 8 },
  actionBtn: {
    backgroundColor: colors.primary,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 7,
  },
  actionGhost: { backgroundColor: "transparent", borderWidth: 1, borderColor: colors.border },
  actionText: { color: "#fff", fontSize: 12, fontWeight: "600" },
  actionGhostText: { color: colors.textPrimary },
  hint: { color: colors.textSecondary, fontSize: 11, fontStyle: "italic", marginTop: 6, paddingHorizontal: 6 },
});
