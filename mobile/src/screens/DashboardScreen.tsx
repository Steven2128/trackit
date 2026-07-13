import { Ionicons } from "@expo/vector-icons";
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

import CategoryIcon from "../components/CategoryIcon";
import MoneyText from "../components/MoneyText";
import TrendChart from "../components/TrendChart";
import type { AppStackParamList } from "../navigation/AppStack";
import { useBudgetStatus, type BudgetAlertStatus } from "../services/queries/budgets";
import { useDashboard, type DashboardResponse } from "../services/queries/dashboard";
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
  const user = useAuthStore((s) => s.user);
  const firstName = user?.name?.split(" ")[0];
  const navigation = useNavigation<NativeStackNavigationProp<AppStackParamList>>();
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

  const trendMonths = monthly_trend.map((m) => m.month);
  const trendTotals = monthly_trend.map((m) => Number(m.total_spent));

  return (
    <ScrollView
      style={styles.root}
      contentContainerStyle={[styles.content, { paddingTop: insets.top + 12 }]}
      refreshControl={
        <RefreshControl
          refreshing={isRefetching}
          onRefresh={refetch}
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

      <Text style={styles.sectionLabel}>Por categoría</Text>
      {sortedCategories.length === 0 ? (
        <Text style={styles.emptyCat}>Sin gastos este mes</Text>
      ) : (
        sortedCategories.map((c, i) => {
          const cat = getCategory(c.category);
          const alert = c.category ? budgetAlertByCategory.get(c.category) : undefined;
          return (
            <View key={`${c.category ?? "null"}-${i}`} style={styles.catRow}>
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
            </View>
          );
        })
      )}
    </ScrollView>
  );
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
