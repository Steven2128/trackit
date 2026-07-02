import { useMemo, useState } from "react";
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

import TransactionRow from "../components/TransactionRow";
import {
  useTransactions,
  type TransactionOut,
} from "../services/queries/transactions";
import { colors } from "../theme/colors";
import { CATEGORIES } from "../utils/categories";
import {
  currentMonthYYYYMM,
  dayKey,
  formatDayHeader,
  humanizeMonth,
  shiftMonth,
} from "../utils/dates";

type Section = { title: string; sortKey: string; data: TransactionOut[] };

const FILTERABLE = CATEGORIES.filter(
  (c) => !["transfer", "cash_withdrawal"].includes(c.key),
);

export default function TransactionsScreen() {
  const [month, setMonth] = useState<string>(currentMonthYYYYMM());
  const [category, setCategory] = useState<string | null>(null);

  const query = useTransactions({ month, category, limit: 200 });

  const sections: Section[] = useMemo(() => {
    const items = query.data?.items ?? [];
    const map = new Map<string, TransactionOut[]>();
    for (const tx of items) {
      const key = dayKey(tx.occurred_at);
      const bucket = map.get(key) ?? [];
      bucket.push(tx);
      map.set(key, bucket);
    }
    const result: Section[] = [];
    for (const [key, data] of map.entries()) {
      const first = data[0];
      result.push({ title: formatDayHeader(first.occurred_at), sortKey: key, data });
    }
    result.sort((a, b) => b.sortKey.localeCompare(a.sortKey));
    return result;
  }, [query.data]);

  return (
    <View style={styles.root}>
      <View style={styles.header}>
        <Pressable onPress={() => setMonth((m) => shiftMonth(m, -1))} hitSlop={12}>
          <Text style={styles.navArrow}>‹</Text>
        </Pressable>
        <Text style={styles.headerTitle}>{humanizeMonth(month)}</Text>
        <Pressable onPress={() => setMonth((m) => shiftMonth(m, +1))} hitSlop={12}>
          <Text style={styles.navArrow}>›</Text>
        </Pressable>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
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
          <Text style={styles.emptyText}>Sin transacciones en este período</Text>
        </View>
      ) : (
        <SectionList
          sections={sections}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl
              refreshing={query.isRefetching}
              onRefresh={query.refetch}
              tintColor={colors.primary}
            />
          }
          renderSectionHeader={({ section }) => (
            <Text style={styles.sectionHeader}>{section.title}</Text>
          )}
          renderItem={({ item }) => (
            <TransactionRow
              merchant={item.merchant}
              category={item.category}
              amount={item.amount}
              type={item.transaction_type}
            />
          )}
        />
      )}
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
      style={[styles.chip, active && styles.chipActive]}
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
    paddingHorizontal: 24,
    paddingTop: 12,
    paddingBottom: 8,
  },
  navArrow: { color: colors.primary, fontSize: 24, paddingHorizontal: 8 },
  headerTitle: { color: colors.textPrimary, fontSize: 15, fontWeight: "600" },
  chipsRow: { paddingHorizontal: 16, paddingBottom: 8, gap: 8 },
  chip: {
    backgroundColor: colors.surfaceMuted,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 14,
  },
  chipActive: { backgroundColor: colors.primary },
  chipText: { color: colors.textSecondary, fontSize: 11 },
  chipTextActive: { color: "#fff", fontWeight: "600" },
  centered: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
    gap: 12,
  },
  errorText: { color: colors.textSecondary, fontSize: 14 },
  emptyText: { color: colors.textSecondary, fontSize: 14 },
  retryBtn: {
    backgroundColor: colors.primary,
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
  },
  retryText: { color: "#fff", fontWeight: "600" },
  listContent: { padding: 16, paddingBottom: 32 },
  sectionHeader: {
    color: colors.textSecondary,
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginTop: 12,
    marginBottom: 6,
  },
});
