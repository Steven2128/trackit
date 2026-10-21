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
import CashflowTrend from "../components/CashflowTrend";
import DashboardKpis from "../components/DashboardKpis";
import FortnightCard from "../components/FortnightCard";
import GoalsSummary from "../components/GoalsSummary";
import HealthScoreCard from "../components/HealthScoreCard";
import MoneyText from "../components/MoneyText";
import RecentMovements from "../components/RecentMovements";
import type { AppStackParamList, AppTabParamList } from "../navigation/AppStack";
import { useBudgetStatus, type BudgetAlertStatus } from "../services/queries/budgets";
import { useDashboard, type DashboardResponse } from "../services/queries/dashboard";
import { useHealthScore, useUnusualSpending } from "../services/queries/insights";
import { useNetWorth } from "../services/queries/accounts";
import { useCashPosition } from "../services/queries/cashPosition";
import { useGoals } from "../services/queries/goals";
import { useAuthStore } from "../store/auth";
import { colors } from "../theme/colors";
import { pageStyle, useIsWide } from "../theme/layout";
import { getCategory } from "../utils/categories";
import { humanizeMonth } from "../utils/dates";

const TOP_CATEGORIES = 5;

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
  const { current_month, monthly_trend } = data;
  const spent = Number(current_month.total_spent);
  const { data: budgetStatus } = useBudgetStatus();
  const { data: healthScore } = useHealthScore();
  const { data: unusual } = useUnusualSpending();
  const { data: goals } = useGoals();
  const position = useCashPosition();
  const { data: netWorth, refetch: refetchNetWorth } = useNetWorth();
  const user = useAuthStore((s) => s.user);
  const firstName = user?.name?.split(" ")[0];
  const navigation = useNavigation<NativeStackNavigationProp<AppStackParamList>>();
  // Closest navigator is the tab bar — used to jump to the Budgets tab.
  const tabNavigation = useNavigation<BottomTabNavigationProp<AppTabParamList>>();
  // Screen hides the navigator header, so it must clear the notch itself.
  const insets = useSafeAreaInsets();
  // Wide screens: overview on the left, budget + categories on the right.
  const isWide = useIsWide();

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
  const topCategories = sortedCategories.slice(0, TOP_CATEGORIES);

  const kpis = (
    <DashboardKpis
      data={data}
      netWorth={netWorth}
      onSpent={() => tabNavigation.navigate("Transactions", undefined)}
      onReceived={() => tabNavigation.navigate("Transactions", undefined)}
      onNetWorth={() => navigation.navigate("NetWorth")}
      onDebts={() => tabNavigation.navigate("DebtTracker")}
    />
  );

  const unusualBanner =
    unusual && unusual.items.length > 0 ? (
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
    ) : null;

  const trend = (
    <>
      <Text style={styles.sectionLabel}>Ingresos vs. gastos · 6 meses</Text>
      <CashflowTrend months={monthly_trend} />
    </>
  );

  const budget =
    budgetStatus && budgetStatus.items.length > 0 ? (
      <>
        <Text style={styles.sectionLabel}>Presupuesto del mes</Text>
        <BudgetOverview
          items={budgetStatus.items}
          onPress={() => tabNavigation.navigate("Budgets")}
        />
      </>
    ) : null;

  const categories = (
    <>
      <View style={styles.sectionHeader}>
        <Text style={[styles.sectionLabel, styles.sectionLabelInline]}>Por categoría</Text>
        {sortedCategories.length > TOP_CATEGORIES ? (
          <Pressable
            onPress={() => tabNavigation.navigate("Transactions", undefined)}
            hitSlop={8}
          >
            <Text style={styles.link}>Ver las {sortedCategories.length}</Text>
          </Pressable>
        ) : null}
      </View>
      {topCategories.length === 0 ? (
        <Text style={styles.emptyCat}>Sin gastos este mes</Text>
      ) : (
        topCategories.map((c, i) => {
          const cat = getCategory(c.category);
          const alert = c.category ? budgetAlertByCategory.get(c.category) : undefined;
          const share = spent > 0 ? Math.round((Number(c.total) / spent) * 100) : 0;
          return (
            <Pressable
              key={`${c.category ?? "null"}-${i}`}
              style={({ pressed }) => [styles.catRow, pressed && styles.pressed]}
              onPress={() => tabNavigation.navigate("Transactions", { category: c.category })}
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
                <View style={styles.shareTrack}>
                  <View
                    style={[styles.shareFill, { width: `${share}%`, backgroundColor: cat.color }]}
                  />
                </View>
                <Text style={styles.catCount}>
                  {share}% · {c.count} {c.count === 1 ? "movimiento" : "movimientos"}
                </Text>
              </View>
              <MoneyText value={c.total} size="md" />
              <Ionicons name="chevron-forward" size={14} color={colors.textSecondary} />
            </Pressable>
          );
        })
      )}
    </>
  );

  const recent = (
    <RecentMovements
      month={current_month.month}
      onSeeAll={() => tabNavigation.navigate("Transactions", undefined)}
    />
  );

  const goalsSection = goals ? (
    <>
      <Text style={styles.sectionLabel}>Metas de ahorro</Text>
      <GoalsSummary goals={goals} onPress={() => navigation.navigate("Goals")} />
    </>
  ) : null;

  const health = healthScore ? (
    <>
      <Text style={styles.sectionLabel}>Salud financiera</Text>
      <HealthScoreCard score={healthScore} />
    </>
  ) : null;

  // Phones have no sidebar: Plan is only reachable from here.
  const planLink = (
    <Pressable
      style={({ pressed }) => [styles.quickBtn, pressed && styles.pressed]}
      onPress={() => navigation.navigate("Plan")}
    >
      <Ionicons name="map-outline" size={16} color={colors.primary} />
      <Text style={styles.quickText}>Plan del mes</Text>
      <Ionicons name="chevron-forward" size={14} color={colors.textSecondary} />
    </Pressable>
  );

  return (
    <ScrollView
      style={styles.root}
      contentContainerStyle={[
        styles.content,
        pageStyle,
        isWide && styles.contentWide,
        { paddingTop: insets.top + (isWide ? 24 : 12) },
      ]}
      refreshControl={
        <RefreshControl
          refreshing={isRefetching}
          onRefresh={() => {
            refetch();
            position.refetch();
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
        {/* Wide screens reach Perfil from the sidebar. */}
        {isWide ? null : (
          <Pressable
            onPress={() => navigation.navigate("Profile")}
            hitSlop={8}
            accessibilityLabel="Perfil"
            style={({ pressed }) => pressed && styles.pressed}
          >
            <Ionicons name="person-circle-outline" size={32} color={colors.textPrimary} />
          </Pressable>
        )}
      </View>

      {isWide ? (
        <>
          {kpis}
          {unusualBanner}
          <View style={styles.columns}>
            <View style={styles.column}>
              <FortnightCard />
              {trend}
              {health}
            </View>
            <View style={styles.column}>
              {budget}
              {categories}
              {recent}
              {goalsSection}
            </View>
          </View>
        </>
      ) : (
        <>
          <FortnightCard />
          {kpis}
          {unusualBanner}
          {planLink}
          {budget}
          {categories}
          {recent}
          {goalsSection}
          {health}
          {trend}
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  content: { padding: 16, paddingBottom: 32 },
  contentWide: { paddingHorizontal: 32 },
  columns: { flexDirection: "row", gap: 24, alignItems: "flex-start" },
  column: { flex: 1, minWidth: 0 },
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
  quickBtn: {
    marginBottom: 4,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    paddingHorizontal: 12,
    // Without a floor the three links shrink to the score card's height
    // (~20px each) — too tight to read and to tap.
    minHeight: 36,
    flex: 1,
  },
  quickText: { color: colors.textPrimary, fontSize: 13, fontWeight: "600", flex: 1 },
  unusualBox: {
    backgroundColor: colors.warningSoft,
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
    gap: 8,
  },
  unusualRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  unusualText: { color: colors.textPrimary, fontSize: 13, flex: 1 },
  sectionLabel: {
    color: colors.textSecondary,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.6,
    marginTop: 20,
    marginBottom: 8,
  },
  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "baseline",
    marginTop: 20,
    marginBottom: 8,
  },
  sectionLabelInline: { marginTop: 0, marginBottom: 0 },
  link: { color: colors.primary, fontSize: 12, fontWeight: "600" },
  shareTrack: {
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.background,
    overflow: "hidden",
    marginTop: 6,
  },
  shareFill: { height: 4, borderRadius: 2 },
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
