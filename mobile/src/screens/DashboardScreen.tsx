import { Ionicons } from "@expo/vector-icons";
import type { BottomTabNavigationProp } from "@react-navigation/bottom-tabs";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useMemo } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { useSafeAreaInsets } from "react-native-safe-area-context";

import BudgetOverview from "../components/BudgetOverview";
import CategoryIcon from "../components/CategoryIcon";
import MoneyText from "../components/MoneyText";
import PaymentChecklistRow from "../components/PaymentChecklistRow";
import TrendChart from "../components/TrendChart";
import type { AppStackParamList, AppTabParamList } from "../navigation/AppStack";
import { useBudgetStatus, type BudgetAlertStatus } from "../services/queries/budgets";
import { useDashboard, type DashboardResponse } from "../services/queries/dashboard";
import { useHealthScore, useUnusualSpending } from "../services/queries/insights";
import { useNetWorth } from "../services/queries/accounts";
import { useCashFlow } from "../services/queries/plan";
import { useAuthStore } from "../store/auth";
import { colors } from "../theme/colors";
import { getCategory } from "../utils/categories";
import { humanizeMonth } from "../utils/dates";

export default function DashboardScreen() {
  const { data, isLoading, isError, refetch, isRefetching } = useDashboard();

  if (isLoading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  if (isError || !data) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>No pudimos cargar el dashboard.</Text>
        <Pressable
          style={({ pressed }) => [styles.retryBtn, pressed && styles.pressed]}
          onPress={() => refetch()}
        >
          <Text style={styles.retryText}>Reintentar</Text>
        </Pressable>
      </View>
    );
  }

  return <DashboardContent data={data} refetch={refetch} isRefetching={isRefetching} />;
}

function DashboardContent({
  data,
  refetch,
  isRefetching,
}: {
  data: DashboardResponse;
  refetch: () => void;
  isRefetching: boolean;
}) {
  const { current_month, debts, monthly_trend } = data;
  const { data: budgetStatus } = useBudgetStatus();
  const { data: healthScore } = useHealthScore();
  const { data: unusual } = useUnusualSpending();
  const cashflow = useCashFlow();
  const { data: netWorth, refetch: refetchNetWorth } = useNetWorth();
  const user = useAuthStore((s) => s.user);
  const firstName = user?.name?.split(" ")[0];
  const navigation = useNavigation<NativeStackNavigationProp<AppStackParamList>>();
  // Closest navigator is the tab bar — used to jump to the Budgets tab.
  const tabNavigation = useNavigation<BottomTabNavigationProp<AppTabParamList>>();
  // Screen hides the navigator header, so it must clear the notch itself.
  const insets = useSafeAreaInsets();

  const budgetAlertByCategory = useMemo(() => {
    const map = new Map<string, BudgetAlertStatus>();
    for (const item of budgetStatus?.items ?? []) {
      if (item.status !== "ok") map.set(item.category, item.status);
    }
    return map;
  }, [budgetStatus]);

  const sortedCategories = useMemo(() => {
    return [...current_month.by_category].sort(
      (a, b) => Number(b.total) - Number(a.total),
    );
  }, [current_month.by_category]);

  // Fixed payments still due this month; checking one here drops it off the list.
  const checklist = cashflow.data?.checklist ?? [];
  const pendingPayments = checklist.filter((p) => !p.is_paid);

  const trendMonths = monthly_trend.map((m) => m.month);
  const trendTotals = monthly_trend.map((m) => Number(m.total_spent));

  return (
    <ScrollView
      style={styles.root}
      contentContainerStyle={[styles.content, { paddingTop: insets.top + 12 }]}
      refreshControl={
        <RefreshControl
          refreshing={isRefetching}
          onRefresh={() => {
            refetch();
            cashflow.refetch();
            refetchNetWorth();
          }}
          tintColor={colors.primary}
        />
      }
    >
      <View style={styles.greeting}>
        <View style={styles.greetingBody}>
          <Text style={styles.greetingName}>
            {firstName ? `Hola, ${firstName}` : "Hola"}
          </Text>
          <Text style={styles.greetingSub}>
            Así van tus finanzas en {humanizeMonth(current_month.month)}
          </Text>
        </View>
        <Pressable
          onPress={() => navigation.navigate("Profile")}
          hitSlop={8}
          accessibilityLabel="Perfil"
          style={({ pressed }) => pressed && styles.pressed}
        >
          <Ionicons name="person-circle-outline" size={32} color={colors.textPrimary} />
        </Pressable>
      </View>

      <View style={styles.quickRow}>
        {healthScore ? (
          <View style={styles.scoreCard}>
            <Text style={styles.scoreValue}>
              <Text style={{ color: scoreColor(healthScore.total) }}>{healthScore.total}</Text>
              <Text style={styles.scoreMax}>/100</Text>
            </Text>
            <Text style={styles.scoreLabel}>Salud financiera</Text>
          </View>
        ) : null}
        <View style={styles.quickCol}>
          <Pressable
            style={({ pressed }) => [styles.quickBtn, pressed && styles.pressed]}
            onPress={() => navigation.navigate("Plan")}
          >
            <Ionicons name="map-outline" size={16} color={colors.primary} />
            <Text style={styles.quickText}>Plan del mes</Text>
            <Ionicons name="chevron-forward" size={14} color={colors.textSecondary} />
          </Pressable>
          <Pressable
            style={({ pressed }) => [styles.quickBtn, pressed && styles.pressed]}
            onPress={() => navigation.navigate("Goals")}
          >
            <Ionicons name="flag-outline" size={16} color={colors.primary} />
            <Text style={styles.quickText}>Metas de ahorro</Text>
            <Ionicons name="chevron-forward" size={14} color={colors.textSecondary} />
          </Pressable>
          <Pressable
            style={({ pressed }) => [styles.quickBtn, pressed && styles.pressed]}
            onPress={() => navigation.navigate("NetWorth")}
          >
            <Ionicons name="wallet-outline" size={16} color={colors.primary} />
            <Text style={styles.quickText}>Patrimonio</Text>
            {netWorth?.accounts.length ? (
              <MoneyText value={netWorth.net_worth} size="sm" style={styles.quickMoney} />
            ) : null}
            <Ionicons name="chevron-forward" size={14} color={colors.textSecondary} />
          </Pressable>
        </View>
      </View>

      {unusual && unusual.items.length > 0 ? (
        <View style={styles.unusualBox}>
          {unusual.items.map((a) => {
            const cat = getCategory(a.category);
            return (
              <View key={a.category} style={styles.unusualRow}>
                <Ionicons name="trending-up" size={16} color={colors.warning} />
                <Text style={styles.unusualText}>
                  Gasto inusual en {cat.label}: vas {a.ratio}× tu promedio (
                  <MoneyText value={a.current} size="sm" style={{ color: colors.warning }} />
                  )
                </Text>
              </View>
            );
          })}
        </View>
      ) : null}

      {checklist.length > 0 ? (
        <>
          <Pressable
            style={({ pressed }) => [styles.pendingHeader, pressed && styles.pressed]}
            onPress={() => navigation.navigate("Plan")}
            accessibilityLabel="Ver plan del mes"
          >
            <Text style={styles.pendingTitle}>Pagos fijos pendientes</Text>
            <Text style={styles.pendingProgress}>
              {checklist.length - pendingPayments.length}/{checklist.length} pagados
            </Text>
            <Ionicons name="chevron-forward" size={14} color={colors.textSecondary} />
          </Pressable>
          <View style={styles.pendingBox}>
            {pendingPayments.length === 0 ? (
              <View style={styles.allPaidRow}>
                <Ionicons name="checkmark-circle" size={20} color={colors.success} />
                <Text style={styles.allPaidText}>Todo pagado este mes</Text>
              </View>
            ) : (
              pendingPayments.map((item, i) => (
                <PaymentChecklistRow key={item.id ?? item.name + i} item={item} index={i} />
              ))
            )}
          </View>
        </>
      ) : null}

      <View style={styles.heroRow}>
        <View style={styles.hero}>
          <Text style={styles.heroLabel}>Gastado este mes</Text>
          <MoneyText value={current_month.total_spent} size="lg" />
          <Text style={styles.heroMeta}>
            {current_month.transaction_count} transacciones
          </Text>
        </View>
        <View style={[styles.hero, styles.heroDebt]}>
          <Text style={styles.heroLabel}>Deuda total</Text>
          {debts.debt_count === 0 ? (
            <Text style={styles.noDebt}>Sin deudas</Text>
          ) : (
            <>
              <MoneyText value={debts.total_debt} size="lg" />
              <Text style={styles.heroMeta}>
                {debts.debt_count} · mín <MoneyText value={debts.total_minimum_payment} size="sm" style={{ color: colors.textSecondary, fontWeight: "600" }} />/mes
              </Text>
            </>
          )}
        </View>
      </View>

      <Text style={styles.sectionLabel}>Tendencia 6 meses</Text>
      <TrendChart months={trendMonths} totals={trendTotals} />

      {budgetStatus && budgetStatus.items.length > 0 ? (
        <>
          <Text style={styles.sectionLabel}>Presupuesto del mes</Text>
          <BudgetOverview
            items={budgetStatus.items}
            onPress={() => tabNavigation.navigate("Budgets")}
          />
        </>
      ) : null}

      <Text style={styles.sectionLabel}>Por categoría</Text>
      {sortedCategories.length === 0 ? (
        <Text style={styles.emptyCat}>Sin gastos este mes</Text>
      ) : (
        sortedCategories.map((c, i) => {
          const cat = getCategory(c.category);
          const alert = c.category ? budgetAlertByCategory.get(c.category) : undefined;
          return (
            <Pressable
              key={`${c.category ?? "null"}-${i}`}
              style={({ pressed }) => [styles.catRow, pressed && styles.pressed]}
              onPress={() =>
                tabNavigation.navigate("Transactions", { category: c.category })
              }
              accessibilityLabel={`Ver movimientos de ${cat.label}`}
            >
              <CategoryIcon categoryKey={c.category} />
              <View style={styles.catBody}>
                <View style={styles.catLabelRow}>
                  <Text style={styles.catLabel}>{cat.label}</Text>
                  {alert ? (
                    <Ionicons
                      name={alert === "exceeded" ? "alert-circle" : "warning"}
                      size={14}
                      color={alert === "exceeded" ? colors.danger : colors.warning}
                    />
                  ) : null}
                </View>
                <Text style={styles.catCount}>{c.count} {c.count === 1 ? "tx" : "txs"}</Text>
              </View>
              <MoneyText value={c.total} size="md" />
              <Ionicons name="chevron-forward" size={14} color={colors.textSecondary} />
            </Pressable>
          );
        })
      )}
    </ScrollView>
  );
}

function scoreColor(total: number): string {
  if (total >= 75) return colors.success;
  if (total >= 50) return colors.warning;
  return colors.danger;
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  content: { padding: 16, paddingBottom: 32 },
  centered: {
    flex: 1,
    backgroundColor: colors.background,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
    gap: 12,
  },
  errorText: { color: colors.textSecondary, fontSize: 14 },
  retryBtn: {
    backgroundColor: colors.primary,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 10,
  },
  retryText: { color: "#fff", fontWeight: "600" },
  pressed: { opacity: 0.7 },
  greeting: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 16,
    gap: 12,
  },
  greetingBody: { flex: 1 },
  greetingName: { color: colors.textPrimary, fontSize: 24, fontWeight: "700" },
  greetingSub: { color: colors.textSecondary, fontSize: 13, marginTop: 2 },
  quickRow: { flexDirection: "row", gap: 8, marginBottom: 12 },
  scoreCard: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 14,
    alignItems: "center",
    justifyContent: "center",
    minWidth: 110,
    gap: 2,
  },
  scoreValue: { fontSize: 24, fontWeight: "700" },
  scoreMax: { color: colors.textSecondary, fontSize: 13, fontWeight: "600" },
  scoreLabel: { color: colors.textSecondary, fontSize: 11 },
  quickCol: { flex: 1, gap: 8 },
  quickBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    paddingHorizontal: 12,
    flex: 1,
  },
  quickText: { color: colors.textPrimary, fontSize: 13, fontWeight: "600", flex: 1 },
  quickMoney: { color: colors.textSecondary, fontWeight: "600" },
  unusualBox: {
    backgroundColor: colors.warningSoft,
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
    gap: 8,
  },
  unusualRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  unusualText: { color: colors.textPrimary, fontSize: 13, flex: 1 },
  pendingHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginBottom: 8,
  },
  pendingTitle: {
    color: colors.textSecondary,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.6,
    flex: 1,
  },
  pendingProgress: { color: colors.textSecondary, fontSize: 11, fontWeight: "600" },
  pendingBox: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    paddingHorizontal: 12,
    marginBottom: 16,
  },
  allPaidRow: { flexDirection: "row", alignItems: "center", gap: 8, paddingVertical: 12 },
  allPaidText: { color: colors.success, fontSize: 14, fontWeight: "600" },
  heroRow: { flexDirection: "row", gap: 8, marginBottom: 16 },
  hero: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 14,
  },
  heroDebt: { borderLeftWidth: 3, borderLeftColor: colors.danger },
  heroLabel: {
    color: colors.textSecondary,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.6,
    marginBottom: 6,
  },
  heroMeta: { color: colors.textSecondary, fontSize: 12, marginTop: 4 },
  noDebt: { color: colors.success, fontSize: 16, fontWeight: "700", marginTop: 4 },
  sectionLabel: {
    color: colors.textSecondary,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.6,
    marginTop: 20,
    marginBottom: 8,
  },
  catRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 12,
    marginBottom: 6,
    gap: 12,
  },
  catBody: { flex: 1 },
  catLabelRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  catLabel: { color: colors.textPrimary, fontSize: 15, fontWeight: "600" },
  catCount: { color: colors.textSecondary, fontSize: 12, marginTop: 2 },
  emptyCat: { color: colors.textSecondary, fontSize: 13, padding: 16, textAlign: "center" },
});
