import { useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import BudgetFormSheet from "../components/BudgetFormSheet";
import CategoryIcon from "../components/CategoryIcon";
import MoneyText from "../components/MoneyText";
import {
  useBudgetStatus,
  type BudgetAlertStatus,
  type BudgetStatusItem,
} from "../services/queries/budgets";
import { colors } from "../theme/colors";
import { CATEGORIES, getCategory } from "../utils/categories";
import { humanizeMonth } from "../utils/dates";

// Budgets make sense for spending categories only — internal movements
// (transfer, cash_withdrawal) are excluded from spending everywhere else.
const BUDGETABLE = CATEGORIES.filter(
  (c) => !["transfer", "cash_withdrawal"].includes(c.key),
);

const STATUS_COLOR: Record<BudgetAlertStatus, string> = {
  ok: colors.success,
  warning: colors.warning,
  exceeded: colors.danger,
};

export default function BudgetsScreen() {
  const { data, isLoading, isError, refetch, isRefetching } = useBudgetStatus();
  const [editing, setEditing] = useState<{ category: string; limit: string | null } | null>(null);

  const byCategory = useMemo(() => {
    const map = new Map<string, BudgetStatusItem>();
    for (const item of data?.items ?? []) map.set(item.category, item);
    return map;
  }, [data]);

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
        <Text style={styles.errorText}>No pudimos cargar los presupuestos.</Text>
        <Pressable style={styles.retryBtn} onPress={() => refetch()}>
          <Text style={styles.retryText}>Reintentar</Text>
        </Pressable>
      </View>
    );
  }

  const alerts = data.items.filter((i) => i.status !== "ok");

  return (
    <View style={styles.root}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={isRefetching}
            onRefresh={refetch}
            tintColor={colors.primary}
          />
        }
      >
        <Text style={styles.monthLabel}>{humanizeMonth(data.month)}</Text>

        {alerts.length > 0 ? (
          <View style={styles.alertBox}>
            {alerts.map((a) => {
              const cat = getCategory(a.category);
              return (
                <Text key={a.category} style={styles.alertText}>
                  {a.status === "exceeded" ? "🔴" : "⚠️"} {cat.label}:{" "}
                  {a.status === "exceeded"
                    ? `superaste el límite (${a.pct}%)`
                    : `vas en ${a.pct}% del límite`}
                </Text>
              );
            })}
          </View>
        ) : null}

        {BUDGETABLE.map((cat) => {
          const item = byCategory.get(cat.key);
          return (
            <Pressable
              key={cat.key}
              style={styles.row}
              onPress={() =>
                setEditing({ category: cat.key, limit: item?.monthly_limit ?? null })
              }
            >
              <CategoryIcon categoryKey={cat.key} />
              <View style={styles.rowBody}>
                <View style={styles.rowTop}>
                  <Text style={styles.rowLabel}>{cat.label}</Text>
                  {item ? (
                    <Text style={styles.rowAmounts}>
                      <MoneyText value={item.spent} size="sm" /> /{" "}
                      <MoneyText
                        value={item.monthly_limit}
                        size="sm"
                        style={{ color: colors.textSecondary }}
                      />
                    </Text>
                  ) : (
                    <Text style={styles.noLimit}>Sin límite</Text>
                  )}
                </View>
                {item ? <ProgressBar pct={Number(item.pct)} status={item.status} /> : null}
              </View>
            </Pressable>
          );
        })}

        <Text style={styles.hint}>Tocá una categoría para fijar o editar su límite.</Text>
      </ScrollView>

      <BudgetFormSheet
        isVisible={editing !== null}
        category={editing?.category ?? null}
        currentLimit={editing?.limit ?? null}
        onClose={() => setEditing(null)}
      />
    </View>
  );
}

function ProgressBar({ pct, status }: { pct: number; status: BudgetAlertStatus }) {
  return (
    <View style={styles.barTrack}>
      <View
        style={[
          styles.barFill,
          { width: `${Math.min(pct, 100)}%`, backgroundColor: STATUS_COLOR[status] },
        ]}
      />
    </View>
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
    paddingVertical: 8,
    borderRadius: 8,
  },
  retryText: { color: "#fff", fontWeight: "600" },
  monthLabel: {
    color: colors.textSecondary,
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 12,
  },
  alertBox: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: 10,
    padding: 12,
    marginBottom: 12,
    gap: 6,
  },
  alertText: { color: colors.textPrimary, fontSize: 13 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 12,
    marginBottom: 6,
    gap: 12,
  },
  rowBody: { flex: 1, gap: 8 },
  rowTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  rowLabel: { color: colors.textPrimary, fontSize: 14, fontWeight: "600" },
  rowAmounts: { color: colors.textPrimary, fontSize: 13 },
  noLimit: { color: colors.textSecondary, fontSize: 12 },
  barTrack: {
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.background,
    overflow: "hidden",
  },
  barFill: { height: 6, borderRadius: 3 },
  hint: {
    color: colors.textSecondary,
    fontSize: 12,
    textAlign: "center",
    marginTop: 12,
  },
});
