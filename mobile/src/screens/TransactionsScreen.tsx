import { Ionicons } from "@expo/vector-icons";
import { useRoute, type RouteProp } from "@react-navigation/native";
import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  SectionList,
  StyleSheet,
  Text,
  View,
} from "react-native";

import CategoryPickerSheet from "../components/CategoryPickerSheet";
import MoneyText from "../components/MoneyText";
import TransactionRow from "../components/TransactionRow";
import type { AppTabParamList } from "../navigation/AppStack";
import { useBudgetStatus } from "../services/queries/budgets";
import {
  useTransactions,
  type TransactionOut,
} from "../services/queries/transactions";
import { colors } from "../theme/colors";
import { CATEGORIES, customCategoryKeys, getCategory } from "../utils/categories";
import {
  currentMonthYYYYMM,
  dayKey,
  formatDayHeader,
  humanizeMonth,
  shiftMonth,
} from "../utils/dates";

type Section = { title: string; sortKey: string; total: number; data: TransactionOut[] };

const FILTERABLE = CATEGORIES.filter(
  (c) => !["transfer", "cash_withdrawal"].includes(c.key),
);

// Mirror of the backend's spending semantics (transactions.py) so the
// header tiles match /transactions/summary for the same rows.
const EXCLUDED_FROM_SPENT = ["transfer", "cash_withdrawal"];
const EXCLUDED_FROM_RECEIVED = ["transfer"];

export default function TransactionsScreen() {
  const [month, setMonth] = useState<string>(currentMonthYYYYMM());
  const [category, setCategory] = useState<string | null>(null);
  // Client-side debit/credit filter — the query already holds the whole
  // month, and keeping it local means the summary tiles stay complete.
  const [typeFilter, setTypeFilter] = useState<"debit" | "credit" | null>(null);
  const [recategorizing, setRecategorizing] = useState<TransactionOut | null>(null);
  const isCurrentMonth = month === currentMonthYYYYMM();

  // Dashboard's category rows navigate here with a preselected category.
  const route = useRoute<RouteProp<AppTabParamList, "Transactions">>();
  useEffect(() => {
    if (route.params && "category" in route.params) {
      setCategory(route.params.category ?? null);
    }
  }, [route.params]);

  const query = useTransactions({ month, category, limit: 200 });
  const items = query.data?.items ?? [];
  const visibleItems = typeFilter
    ? items.filter((tx) => tx.transaction_type === typeFilter)
    : items;
  const { data: budgetStatus } = useBudgetStatus();
  const customKeys = useMemo(
    () =>
      customCategoryKeys([
        ...(budgetStatus?.items ?? []).map((i) => i.category),
        ...items.map((tx) => tx.category),
      ]),
    [budgetStatus, items],
  );

  const totals = useMemo(() => {
    let spent = 0;
    let received = 0;
    for (const tx of items) {
      const amount = Number(tx.amount);
      if (
        tx.transaction_type === "debit" &&
        !EXCLUDED_FROM_SPENT.includes(tx.category ?? "")
      ) {
        spent += amount;
      } else if (
        tx.transaction_type === "credit" &&
        !EXCLUDED_FROM_RECEIVED.includes(tx.category ?? "")
      ) {
        received += amount;
      }
    }
    return { spent, received };
  }, [items]);

  const sections: Section[] = useMemo(() => {
    const map = new Map<string, TransactionOut[]>();
    for (const tx of visibleItems) {
      const key = dayKey(tx.occurred_at);
      const bucket = map.get(key) ?? [];
      bucket.push(tx);
      map.set(key, bucket);
    }
    const result: Section[] = [];
    for (const [key, data] of map.entries()) {
      const first = data[0];
      const total = data.reduce(
        (sum, tx) =>
          tx.transaction_type === "debit" &&
          !EXCLUDED_FROM_SPENT.includes(tx.category ?? "")
            ? sum + Number(tx.amount)
            : sum,
        0,
      );
      result.push({ title: formatDayHeader(first.occurred_at), sortKey: key, total, data });
    }
    result.sort((a, b) => b.sortKey.localeCompare(a.sortKey));
    return result;
  }, [visibleItems]);

  return (
    <View style={styles.root}>
      <View style={styles.header}>
        <Pressable
          onPress={() => setMonth((m) => shiftMonth(m, -1))}
          hitSlop={8}
          style={({ pressed }) => [styles.navBtn, pressed && styles.pressed]}
          accessibilityLabel="Mes anterior"
        >
          <Ionicons name="chevron-back" size={18} color={colors.textPrimary} />
        </Pressable>
        <Text style={styles.headerTitle}>{humanizeMonth(month)}</Text>
        <Pressable
          onPress={() => setMonth((m) => shiftMonth(m, +1))}
          hitSlop={8}
          disabled={isCurrentMonth}
          style={({ pressed }) => [
            styles.navBtn,
            pressed && styles.pressed,
            isCurrentMonth && styles.navBtnDisabled,
          ]}
          accessibilityLabel="Mes siguiente"
        >
          <Ionicons name="chevron-forward" size={18} color={colors.textPrimary} />
        </Pressable>
      </View>

      <View style={styles.summaryRow}>
        <Pressable
          style={({ pressed }) => [
            styles.summaryTile,
            typeFilter === "debit" && styles.summaryTileActive,
            pressed && styles.pressed,
          ]}
          onPress={() => setTypeFilter((t) => (t === "debit" ? null : "debit"))}
          accessibilityLabel="Filtrar gastos"
        >
          <View style={styles.summaryLabelRow}>
            <Text style={styles.summaryLabel}>Gastado</Text>
            {typeFilter === "debit" ? (
              <Ionicons name="funnel" size={12} color={colors.primary} />
            ) : null}
          </View>
          <MoneyText value={totals.spent} size="lg" />
        </Pressable>
        <Pressable
          style={({ pressed }) => [
            styles.summaryTile,
            styles.summaryTileIncome,
            typeFilter === "credit" && styles.summaryTileActive,
            pressed && styles.pressed,
          ]}
          onPress={() => setTypeFilter((t) => (t === "credit" ? null : "credit"))}
          accessibilityLabel="Filtrar ingresos"
        >
          <View style={styles.summaryLabelRow}>
            <Text style={styles.summaryLabel}>Recibido</Text>
            {typeFilter === "credit" ? (
              <Ionicons name="funnel" size={12} color={colors.primary} />
            ) : null}
          </View>
          <MoneyText value={totals.received} size="lg" positive />
        </Pressable>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.chipsScroll}
        contentContainerStyle={styles.chipsRow}
      >
        <Chip label="Todas" active={category === null} onPress={() => setCategory(null)} />
        {FILTERABLE.map((c) => (
          <Chip
            key={c.key}
            label={c.label}
            active={category === c.key}
            onPress={() => setCategory(c.key)}
          />
        ))}
        {customKeys.map((key) => (
          <Chip
            key={key}
            label={getCategory(key).label}
            active={category === key}
            onPress={() => setCategory(key)}
          />
        ))}
      </ScrollView>

      {query.isLoading ? (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      ) : query.isError ? (
        <View style={styles.centered}>
          <Text style={styles.errorText}>No pudimos cargar las transacciones.</Text>
          <Pressable style={styles.retryBtn} onPress={() => query.refetch()}>
            <Text style={styles.retryText}>Reintentar</Text>
          </Pressable>
        </View>
      ) : sections.length === 0 ? (
        <View style={styles.centered}>
          <Ionicons name="receipt-outline" size={40} color={colors.textSecondary} />
          <Text style={styles.emptyTitle}>Sin movimientos</Text>
          <Text style={styles.emptyText}>
            {typeFilter === "debit"
              ? "No hay gastos con estos filtros en el período."
              : typeFilter === "credit"
                ? "No hay ingresos con estos filtros en el período."
                : category
                  ? "No hay transacciones de esta categoría en el período."
                  : "No hay transacciones en este período."}
          </Text>
        </View>
      ) : (
        <SectionList
          sections={sections}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.listContent}
          stickySectionHeadersEnabled={false}
          refreshControl={
            <RefreshControl
              refreshing={query.isRefetching}
              onRefresh={query.refetch}
              tintColor={colors.primary}
            />
          }
          renderSectionHeader={({ section }) => (
            <View style={styles.sectionHeaderRow}>
              <Text style={styles.sectionHeader}>{section.title}</Text>
              {section.total > 0 ? (
                <MoneyText
                  value={section.total}
                  size="sm"
                  style={{ color: colors.textSecondary }}
                />
              ) : null}
            </View>
          )}
          renderItem={({ item }) => (
            <Pressable
              onPress={() => setRecategorizing(item)}
              style={({ pressed }) => pressed && styles.pressed}
              accessibilityLabel="Cambiar categoría"
            >
              <TransactionRow
                merchant={item.merchant}
                category={item.category}
                amount={item.amount}
                type={item.transaction_type}
                occurredAt={item.occurred_at}
                note={item.note}
                showChevron
              />
            </Pressable>
          )}
        />
      )}

      <CategoryPickerSheet
        isVisible={recategorizing !== null}
        transaction={recategorizing}
        onClose={() => setRecategorizing(null)}
      />
    </View>
  );
}

function Chip({
  label,
  active,
  onPress,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.chip,
        active && styles.chipActive,
        pressed && styles.pressed,
      ]}
    >
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 12,
  },
  navBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  navBtnDisabled: { opacity: 0.35 },
  pressed: { opacity: 0.6 },
  headerTitle: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: "700",
    textTransform: "capitalize",
  },
  summaryRow: {
    flexDirection: "row",
    gap: 8,
    paddingHorizontal: 16,
    marginBottom: 12,
  },
  summaryTile: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 12,
    gap: 4,
  },
  summaryTileIncome: { borderLeftWidth: 3, borderLeftColor: colors.success },
  summaryTileActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primarySoft,
  },
  summaryLabelRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  summaryLabel: {
    color: colors.textSecondary,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
  // flexGrow: 0 keeps the horizontal ScrollView at its content height —
  // without it the chips get squeezed/clipped by the SectionList below.
  chipsScroll: { flexGrow: 0 },
  chipsRow: {
    paddingHorizontal: 16,
    paddingVertical: 2,
    gap: 8,
    alignItems: "center",
  },
  chip: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: 14,
    height: 34,
    justifyContent: "center",
    borderRadius: 999,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { color: colors.textSecondary, fontSize: 13, fontWeight: "500" },
  chipTextActive: { color: "#fff", fontWeight: "600" },
  centered: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
    gap: 10,
  },
  errorText: { color: colors.textSecondary, fontSize: 14 },
  emptyTitle: { color: colors.textPrimary, fontSize: 15, fontWeight: "600" },
  emptyText: { color: colors.textSecondary, fontSize: 13, textAlign: "center" },
  retryBtn: {
    backgroundColor: colors.primary,
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
  },
  retryText: { color: "#fff", fontWeight: "600" },
  listContent: { padding: 16, paddingTop: 8, paddingBottom: 32 },
  sectionHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 12,
    marginBottom: 6,
  },
  sectionHeader: {
    color: colors.textSecondary,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
});
