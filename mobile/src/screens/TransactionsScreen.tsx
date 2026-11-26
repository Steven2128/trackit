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
  TextInput,
  View,
} from "react-native";

import CategoryPickerSheet from "../components/CategoryPickerSheet";
import IncomeSheet from "../components/IncomeSheet";
import MoneyText from "../components/MoneyText";
import TransactionRow from "../components/TransactionRow";
import type { AppTabParamList } from "../navigation/AppStack";
import { useBudgetStatus } from "../services/queries/budgets";
import {
  useTransactions,
  type TransactionOut,
} from "../services/queries/transactions";
import { colors } from "../theme/colors";
import { pageStyle, useIsWide } from "../theme/layout";
import {
  CATEGORIES,
  EXCLUDED_FROM_RECEIVED,
  EXCLUDED_FROM_SPENT,
  INTERNAL_CATEGORIES,
  customCategoryKeys,
  getCategory,
  ownAmount,
} from "../utils/categories";
import {
  currentMonthYYYYMM,
  dayKey,
  formatDayHeader,
  humanizeMonth,
  shiftMonth,
} from "../utils/dates";

type Section = { title: string; sortKey: string; total: number; data: TransactionOut[] };

const FILTERABLE = CATEGORIES.filter(
  (c) => !INTERNAL_CATEGORIES.includes(c.key),
);


export default function TransactionsScreen() {
  const [month, setMonth] = useState<string>(currentMonthYYYYMM());
  const [category, setCategory] = useState<string | null>(null);
  // Client-side debit/credit filter — the query already holds the whole
  // month, and keeping it local means the summary tiles stay complete.
  const [typeFilter, setTypeFilter] = useState<"debit" | "credit" | null>(null);
  const [search, setSearch] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [addingIncome, setAddingIncome] = useState(false);
  const [recategorizing, setRecategorizing] = useState<TransactionOut | null>(null);
  const isCurrentMonth = month === currentMonthYYYYMM();
  const isWide = useIsWide();

  // Dashboard's category rows navigate here with a preselected category.
  const route = useRoute<RouteProp<AppTabParamList, "Transactions">>();
  useEffect(() => {
    if (route.params && "category" in route.params) {
      setCategory(route.params.category ?? null);
    }
  }, [route.params]);

  const query = useTransactions({ month, category, limit: 200 });
  const items = query.data?.items ?? [];
  // Search is client-side too: the month is already loaded, and it matches
  // what the user sees (merchant, note, category label, amount).
  const needle = normalize(search.trim());
  const visibleItems = items.filter((tx) => {
    if (typeFilter && tx.transaction_type !== typeFilter) return false;
    if (!needle) return true;
    const haystack = normalize(
      [
        tx.merchant,
        tx.note,
        getCategory(tx.category, tx.transaction_type).label,
        String(Math.round(Number(tx.amount))),
      ]
        .filter(Boolean)
        .join(" "),
    );
    return haystack.includes(needle.replace(/[.$\s]/g, "")) || haystack.includes(needle);
  });
  const activeFilters = (category ? 1 : 0) + (typeFilter ? 1 : 0);
  const filtersLit = showFilters || activeFilters > 0;
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
      const amount = ownAmount(tx);
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
            ? sum + ownAmount(tx)
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
      <View style={[pageStyle, styles.page]}>
        {/* Month switcher + totals share one compact band so the list starts
            high; on wide screens it's a single row. */}
        <View style={[styles.topBand, isWide && styles.topBandWide]}>
          <View style={[styles.header, isWide && styles.headerWide]}>
            <Pressable
              onPress={() => setMonth((m) => shiftMonth(m, -1))}
              hitSlop={8}
              style={({ pressed }) => [styles.navBtn, pressed && styles.pressed]}
              accessibilityLabel="Mes anterior"
            >
              <Ionicons name="chevron-back" size={16} color={colors.textPrimary} />
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
              <Ionicons name="chevron-forward" size={16} color={colors.textPrimary} />
            </Pressable>
          </View>

          <View style={[styles.summaryRow, isWide && styles.summaryRowWide]}>
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
                {needle
                ? `Nada coincide con "${search.trim()}".`
                : typeFilter === "debit" ? (
                  <Ionicons name="funnel" size={11} color={colors.primary} />
                ) : null}
              </View>
              <MoneyText value={totals.spent} size="md" style={styles.summaryValue} />
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
                  <Ionicons name="funnel" size={11} color={colors.primary} />
                ) : null}
              </View>
              <MoneyText
                value={totals.received}
                size="md"
                positive
                style={styles.summaryValue}
              />
            </Pressable>
          </View>
        </View>

        <View style={styles.toolbar}>
          <View style={styles.searchBox}>
            <Ionicons name="search" size={16} color={colors.textSecondary} />
            <TextInput
              value={search}
              onChangeText={setSearch}
              placeholder="Buscar comercio, nota, categoría o monto"
              placeholderTextColor={colors.textSecondary}
              style={styles.searchInput}
              autoCorrect={false}
              returnKeyType="search"
            />
            {search ? (
              <Pressable
                onPress={() => setSearch("")}
                hitSlop={8}
                accessibilityLabel="Limpiar búsqueda"
              >
                <Ionicons name="close-circle" size={16} color={colors.textSecondary} />
              </Pressable>
            ) : null}
          </View>
          <Pressable
            onPress={() => setShowFilters((v) => !v)}
            style={({ pressed }) => [
              styles.toolBtn,
              filtersLit && styles.toolBtnActive,
              pressed && styles.pressed,
            ]}
            accessibilityLabel={showFilters ? "Ocultar filtros" : "Mostrar filtros"}
          >
            <Ionicons
              name="options-outline"
              size={16}
              color={filtersLit ? colors.primary : colors.textPrimary}
            />
            {isWide ? (
              <Text style={[styles.toolBtnText, filtersLit && { color: colors.primary }]}>
                Filtros
              </Text>
            ) : null}
            {activeFilters > 0 ? (
              <View style={styles.badge}>
                <Text style={styles.badgeText}>{activeFilters}</Text>
              </View>
            ) : null}
            <Ionicons
              name={showFilters ? "chevron-up" : "chevron-down"}
              size={14}
              color={filtersLit ? colors.primary : colors.textSecondary}
            />
          </Pressable>
          <Pressable
            onPress={() => setAddingIncome(true)}
            style={({ pressed }) => [styles.toolBtn, styles.incomeBtn, pressed && styles.pressed]}
            accessibilityLabel="Registrar ingreso"
          >
            <Ionicons name="add" size={18} color={colors.success} />
            {isWide ? (
              <Text style={[styles.toolBtnText, { color: colors.success }]}>Ingreso</Text>
            ) : null}
          </Pressable>
        </View>

        {showFilters ? (
          <View style={styles.filtersPanel}>
            <Text style={styles.filterGroupLabel}>Tipo</Text>
            <View style={styles.chipsWrap}>
              <Chip label="Todos" active={typeFilter === null} onPress={() => setTypeFilter(null)} />
              <Chip
                label="Gastos"
                active={typeFilter === "debit"}
                onPress={() => setTypeFilter("debit")}
              />
              <Chip
                label="Ingresos"
                active={typeFilter === "credit"}
                onPress={() => setTypeFilter("credit")}
              />
            </View>
            <Text style={styles.filterGroupLabel}>Categoría</Text>
            <View style={styles.chipsWrap}>
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
            </View>
            {activeFilters > 0 ? (
              <Pressable
                onPress={() => {
                  setCategory(null);
                  setTypeFilter(null);
                }}
                style={({ pressed }) => [styles.clearFilters, pressed && styles.pressed]}
              >
                <Text style={styles.clearFiltersText}>Limpiar filtros</Text>
              </Pressable>
            ) : null}
          </View>
        ) : null}

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
                  sharedAmount={item.shared_amount}
                  showChevron
                  prominent
                />
              </Pressable>
            )}
          />
        )}
      </View>

      <IncomeSheet isVisible={addingIncome} onClose={() => setAddingIncome(false)} />

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
  // A list of rows reads best narrower than the other pages on desktop.
  page: { flex: 1, maxWidth: 960 },
  topBand: { paddingHorizontal: 16, paddingTop: 6, paddingBottom: 10, gap: 8 },
  topBandWide: { flexDirection: "row", alignItems: "center", gap: 16 },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  headerWide: { gap: 12, justifyContent: "flex-start" },
  navBtn: {
    width: 30,
    height: 30,
    borderRadius: 15,
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
    fontSize: 15,
    fontWeight: "700",
    textTransform: "capitalize",
    minWidth: 130,
    textAlign: "center",
  },
  summaryRow: { flexDirection: "row", gap: 8 },
  summaryRowWide: { flex: 1 },
  // Compact: label and amount on one line so the tiles stay ~36px tall.
  summaryTile: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: colors.surface,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: 10,
    paddingVertical: 8,
    gap: 6,
  },
  summaryTileIncome: { borderLeftWidth: 3, borderLeftColor: colors.success },
  summaryTileActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primarySoft,
  },
  summaryLabelRow: { flexDirection: "row", alignItems: "center", gap: 4 },
  summaryLabel: {
    color: colors.textSecondary,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
  summaryValue: { fontWeight: "700" },
  toolbar: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: 16,
    marginBottom: 4,
  },
  searchBox: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    paddingHorizontal: 10,
    height: 38,
  },
  searchInput: {
    flex: 1,
    minWidth: 0,
    color: colors.textPrimary,
    fontSize: 14,
    height: "100%",
    // RN web draws a focus outline on inputs; the box border is enough.
    outlineStyle: "none",
  } as object,
  toolBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    height: 38,
    paddingHorizontal: 10,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  toolBtnActive: { borderColor: colors.primary, backgroundColor: colors.primarySoft },
  toolBtnText: { color: colors.textPrimary, fontSize: 13, fontWeight: "600" },
  incomeBtn: { borderColor: colors.success, backgroundColor: colors.successSoft },
  badge: {
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    paddingHorizontal: 5,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  badgeText: { color: "#fff", fontSize: 11, fontWeight: "700" },
  filtersPanel: {
    marginHorizontal: 16,
    marginTop: 6,
    padding: 12,
    gap: 8,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  filterGroupLabel: {
    color: colors.textSecondary,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
  chipsWrap: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  clearFilters: { alignSelf: "flex-start", paddingVertical: 4 },
  clearFiltersText: { color: colors.primary, fontSize: 13, fontWeight: "600" },
  chip: {
    backgroundColor: colors.surfaceMuted,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: 12,
    height: 30,
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
    marginTop: 14,
    marginBottom: 8,
  },
  sectionHeader: {
    color: colors.textPrimary,
    fontSize: 12,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
});

function normalize(text: string): string {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}
