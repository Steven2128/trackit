import { Ionicons } from "@expo/vector-icons";
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
import ResponsiveGrid from "../components/ResponsiveGrid";
import {
  useBudgetStatus,
  useDeleteBudget,
  type BudgetAlertStatus,
  type BudgetStatusItem,
} from "../services/queries/budgets";
import { useCategoryRules, useDeleteCategoryRule } from "../services/queries/categoryRules";
import { colors } from "../theme/colors";
import { pageStyle } from "../theme/layout";
import { CATEGORIES, customCategoryKeys, getCategory } from "../utils/categories";
import { humanizeMonth } from "../utils/dates";
import { Alert } from "../utils/alert";

// Budgets make sense for spending categories only — internal movements
// (transfer, cash_withdrawal) are excluded from spending everywhere else.
const BUDGETABLE = CATEGORIES.filter(
  (c) => !["transfer", "cash_withdrawal", "debt_payment"].includes(c.key),
);

const STATUS_COLOR: Record<BudgetAlertStatus, string> = {
  ok: colors.success,
  warning: colors.warning,
  exceeded: colors.danger,
};

export default function BudgetsScreen() {
  const { data, isLoading, isError, refetch, isRefetching } = useBudgetStatus();
  const [editing, setEditing] = useState<{ category: string; limit: string | null } | null>(null);
  const [creatingCustom, setCreatingCustom] = useState(false);
  const deleteMut = useDeleteBudget();
  const rules = useCategoryRules();
  const deleteRule = useDeleteCategoryRule();

  function confirmDeleteRule(id: string, pattern: string) {
    Alert.alert(
      "Quitar regla",
      `¿Dejar de mandar "${pattern}" a una categoría fija? Los movimientos que ya están no cambian.`,
      [
        { text: "Cancelar", style: "cancel" },
        {
          text: "Quitar",
          style: "destructive",
          onPress: () =>
            deleteRule.mutate(id, {
              onError: (e) =>
                Alert.alert("Error", e instanceof Error ? e.message : "Error al quitar."),
            }),
        },
      ],
    );
  }

  function confirmDelete(category: string) {
    const isCustom = !CATEGORIES.some((c) => c.key === category);
    const label = getCategory(category).label;
    Alert.alert(
      isCustom ? "Eliminar categoría" : "Quitar presupuesto",
      isCustom
        ? `¿Eliminar "${label}"? Sus transacciones pasan a "Otros".`
        : `¿Quitar el límite de ${label}?`,
      [
        { text: "Cancelar", style: "cancel" },
        {
          text: isCustom ? "Eliminar" : "Quitar",
          style: "destructive",
          onPress: () =>
            deleteMut.mutate(category, {
              onError: (e) =>
                Alert.alert(
                  "Error",
                  e instanceof Error ? e.message : "Error al eliminar.",
                ),
            }),
        },
      ],
    );
  }

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
  // User-created budget categories, rendered after the built-in list.
  const customKeys = customCategoryKeys(data.items.map((i) => i.category));

  return (
    <View style={styles.root}>
      <ScrollView
        contentContainerStyle={[styles.content, pageStyle]}
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
              const exceeded = a.status === "exceeded";
              return (
                <View key={a.category} style={styles.alertRow}>
                  <Ionicons
                    name={exceeded ? "alert-circle" : "warning"}
                    size={16}
                    color={exceeded ? colors.danger : colors.warning}
                  />
                  <Text style={styles.alertText}>
                    {cat.label}:{" "}
                    {exceeded
                      ? `superaste el límite (${a.pct}%)`
                      : `vas en ${a.pct}% del límite`}
                  </Text>
                </View>
              );
            })}
          </View>
        ) : null}

        <ResponsiveGrid>
          {BUDGETABLE.map((cat) => {
            const item = byCategory.get(cat.key);
            return (
              <Pressable
                key={cat.key}
                style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
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
                {item ? (
                  <Pressable
                    onPress={() => confirmDelete(cat.key)}
                    hitSlop={10}
                    style={({ pressed }) => [styles.trashBtn, pressed && styles.rowPressed]}
                    accessibilityLabel={`Quitar presupuesto de ${cat.label}`}
                  >
                    <Ionicons name="trash-outline" size={18} color={colors.danger} />
                  </Pressable>
                ) : null}
              </Pressable>
            );
          })}

          {customKeys.map((key) => {
            const item = byCategory.get(key);
            const cat = getCategory(key);
            return (
              <Pressable
                key={key}
                style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
                onPress={() =>
                  setEditing({ category: key, limit: item?.monthly_limit ?? null })
                }
              >
                <CategoryIcon categoryKey={key} />
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
                <Pressable
                  onPress={() => confirmDelete(key)}
                  hitSlop={10}
                  style={({ pressed }) => [styles.trashBtn, pressed && styles.rowPressed]}
                  accessibilityLabel={`Eliminar categoría ${cat.label}`}
                >
                  <Ionicons name="trash-outline" size={18} color={colors.danger} />
                </Pressable>
              </Pressable>
            );
          })}
        </ResponsiveGrid>

        <Pressable
          style={({ pressed }) => [styles.addBtn, pressed && styles.rowPressed]}
          onPress={() => setCreatingCustom(true)}
        >
          <Ionicons name="add-circle-outline" size={18} color={colors.primary} />
          <Text style={styles.addText}>Agregar categoría de presupuesto</Text>
        </Pressable>

        <Text style={styles.hint}>
          Tocá una categoría para fijar, editar o quitar su límite.
        </Text>

        <Text style={styles.sectionTitle}>Reglas por comercio</Text>
        {(rules.data ?? []).length === 0 ? (
          <Text style={styles.rulesEmpty}>
            Todavía no tenés reglas. Al cambiarle la categoría a un movimiento, elegí
            "Este y los próximos" para que ese comercio vaya siempre ahí.
          </Text>
        ) : (
          <View style={styles.rulesBox}>
            {(rules.data ?? []).map((r) => (
              <View key={r.id} style={styles.ruleRow}>
                <CategoryIcon categoryKey={r.category} />
                <Text style={styles.ruleText}>
                  Contiene "<Text style={styles.rulePattern}>{r.pattern}</Text>" →{" "}
                  {getCategory(r.category).label}
                </Text>
                <Pressable
                  onPress={() => confirmDeleteRule(r.id, r.pattern)}
                  hitSlop={10}
                  style={({ pressed }) => [styles.trashBtn, pressed && styles.rowPressed]}
                  accessibilityLabel={`Quitar regla ${r.pattern}`}
                >
                  <Ionicons name="trash-outline" size={18} color={colors.danger} />
                </Pressable>
              </View>
            ))}
          </View>
        )}
      </ScrollView>

      <BudgetFormSheet
        isVisible={editing !== null || creatingCustom}
        category={editing?.category ?? null}
        currentLimit={editing?.limit ?? null}
        createCustom={creatingCustom}
        onClose={() => {
          setEditing(null);
          setCreatingCustom(false);
        }}
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
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.6,
    marginBottom: 12,
  },
  alertBox: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
    gap: 8,
  },
  alertRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  alertText: { color: colors.textPrimary, fontSize: 13, flex: 1 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 12,
    marginBottom: 6,
    gap: 12,
  },
  rowPressed: { opacity: 0.7 },
  rowBody: { flex: 1, gap: 8 },
  rowTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  rowLabel: { color: colors.textPrimary, fontSize: 15, fontWeight: "600" },
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
  addBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    borderWidth: 1,
    borderColor: colors.border,
    borderStyle: "dashed",
    borderRadius: 12,
    padding: 14,
    marginTop: 4,
  },
  addText: { color: colors.primary, fontSize: 14, fontWeight: "600" },
  trashBtn: { padding: 4 },
  sectionTitle: {
    color: colors.textSecondary,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.6,
    marginTop: 24,
    marginBottom: 8,
  },
  rulesEmpty: { color: colors.textSecondary, fontSize: 12, lineHeight: 17 },
  rulesBox: { backgroundColor: colors.surface, borderRadius: 12, paddingVertical: 4 },
  ruleRow: { flexDirection: "row", alignItems: "center", gap: 12, padding: 10 },
  ruleText: { color: colors.textPrimary, fontSize: 14, flex: 1 },
  rulePattern: { fontWeight: "700" },
});
