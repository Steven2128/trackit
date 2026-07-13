import { Ionicons } from "@expo/vector-icons";
import { useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import MoneyText from "../components/MoneyText";
import PlanItemSheet, { type PlanItemEditing } from "../components/PlanItemSheet";
import {
  useCashFlow,
  useIncomeSources,
  usePlannedPayments,
  type UpcomingPaymentOut,
} from "../services/queries/plan";
import { colors } from "../theme/colors";

function formatDeadline(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(`${iso}T12:00:00`);
  return d.toLocaleDateString("es-CO", { day: "numeric", month: "short" });
}

function deadlineColor(daysLeft: number | null): string {
  if (daysLeft === null) return colors.textSecondary;
  if (daysLeft <= 3) return colors.danger;
  if (daysLeft <= 7) return colors.warning;
  return colors.textSecondary;
}

export default function PlanScreen() {
  const cashflow = useCashFlow();
  const incomes = useIncomeSources();
  const payments = usePlannedPayments();
  const [editing, setEditing] = useState<PlanItemEditing | null>(null);

  const isLoading = cashflow.isLoading || incomes.isLoading || payments.isLoading;
  const isError = cashflow.isError || incomes.isError || payments.isError;

  function refetchAll() {
    cashflow.refetch();
    incomes.refetch();
    payments.refetch();
  }

  if (isLoading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  if (isError) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>No pudimos cargar tu plan.</Text>
        <Pressable
          style={({ pressed }) => [styles.retryBtn, pressed && styles.pressed]}
          onPress={refetchAll}
        >
          <Text style={styles.retryText}>Reintentar</Text>
        </Pressable>
      </View>
    );
  }

  const flow = cashflow.data;
  const incomeList = incomes.data ?? [];
  const paymentList = payments.data ?? [];
  const hasSetup = incomeList.length > 0 || paymentList.length > 0;
  const available = Number(flow?.available ?? 0);

  return (
    <View style={styles.root}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={cashflow.isRefetching}
            onRefresh={refetchAll}
            tintColor={colors.primary}
          />
        }
      >
        {hasSetup && flow ? (
          <>
            <View style={styles.hero}>
              <Text style={styles.heroLabel}>Disponible mensual proyectado</Text>
              <MoneyText
                value={flow.available}
                size="xl"
                style={available < 0 ? { color: colors.danger } : undefined}
              />
              <Text style={styles.heroSub}>
                Ingresos <MoneyText value={flow.monthly_income} size="sm" style={styles.heroSubStrong} />{" "}
                − compromisos{" "}
                <MoneyText value={flow.monthly_committed} size="sm" style={styles.heroSubStrong} />
              </Text>
            </View>

            {flow.next_income_date ? (
              <View style={styles.nextIncome}>
                <Ionicons name="calendar-outline" size={18} color={colors.success} />
                <Text style={styles.nextIncomeText}>
                  Próximo ingreso: {flow.next_income_name} —{" "}
                  {formatDeadline(flow.next_income_date)} (
                  <MoneyText value={flow.next_income_amount} size="sm" style={{ color: colors.success }} />
                  )
                </Text>
              </View>
            ) : null}

            {flow.checklist.length > 0 ? (
              <>
                <Text style={styles.sectionLabel}>Al cobrar, pagá en este orden</Text>
                <View style={styles.checklistBox}>
                  {flow.checklist.map((item, i) => (
                    <ChecklistRow key={item.name + i} item={item} index={i} />
                  ))}
                </View>
              </>
            ) : null}
          </>
        ) : (
          <View style={styles.emptyBox}>
            <Ionicons name="map-outline" size={44} color={colors.textSecondary} />
            <Text style={styles.emptyText}>
              Registrá tus ingresos fijos (quincenas, bonificaciones) y tus pagos fijos
              (arriendo, cuotas) para ver cuánto te queda libre cada mes y en qué orden pagar.
            </Text>
          </View>
        )}

        <View style={styles.sectionHeader}>
          <Text style={styles.sectionLabel}>Ingresos fijos</Text>
          <AddButton onPress={() => setEditing({ kind: "income" })} label="Agregar ingreso" />
        </View>
        {incomeList.length === 0 ? (
          <Text style={styles.emptyRow}>Sin ingresos registrados</Text>
        ) : (
          incomeList.map((i) => (
            <Pressable
              key={i.id}
              style={({ pressed }) => [styles.row, pressed && styles.pressed]}
              onPress={() => setEditing({ kind: "income", item: i })}
            >
              <View style={[styles.dayBadge, { backgroundColor: colors.successSoft }]}>
                <Text style={[styles.dayBadgeText, { color: colors.success }]}>{i.expected_day}</Text>
              </View>
              <Text style={styles.rowName} numberOfLines={1}>
                {i.name}
              </Text>
              <MoneyText value={i.amount} size="sm" positive signed />
            </Pressable>
          ))
        )}

        <View style={styles.sectionHeader}>
          <Text style={styles.sectionLabel}>Pagos fijos y apartados</Text>
          <AddButton onPress={() => setEditing({ kind: "payment" })} label="Agregar pago" />
        </View>
        {paymentList.length === 0 ? (
          <Text style={styles.emptyRow}>Sin pagos registrados</Text>
        ) : (
          paymentList.map((p) => (
            <Pressable
              key={p.id}
              style={({ pressed }) => [styles.row, pressed && styles.pressed]}
              onPress={() => setEditing({ kind: "payment", item: p })}
            >
              <View
                style={[
                  styles.dayBadge,
                  { backgroundColor: p.is_debt_payment ? colors.dangerSoft : colors.primarySoft },
                ]}
              >
                <Text
                  style={[
                    styles.dayBadgeText,
                    { color: p.is_debt_payment ? colors.danger : colors.primary },
                  ]}
                >
                  {p.due_day ?? "—"}
                </Text>
              </View>
              <View style={styles.rowBody}>
                <Text style={styles.rowName} numberOfLines={1}>
                  {p.name}
                </Text>
                {p.grace_days > 0 ? (
                  <Text style={styles.rowMeta}>+{p.grace_days} días de plazo</Text>
                ) : null}
              </View>
              <MoneyText value={p.amount} size="sm" />
            </Pressable>
          ))
        )}
      </ScrollView>

      <PlanItemSheet editing={editing} onClose={() => setEditing(null)} />
    </View>
  );
}

function ChecklistRow({ item, index }: { item: UpcomingPaymentOut; index: number }) {
  const dateLabel = formatDeadline(item.deadline);
  return (
    <View style={[styles.checkRow, index > 0 && styles.checkRowBorder]}>
      <Text style={styles.checkIndex}>{index + 1}</Text>
      <View style={styles.rowBody}>
        <View style={styles.checkNameRow}>
          <Text style={styles.rowName} numberOfLines={1}>
            {item.name}
          </Text>
          {item.is_debt_payment ? (
            <Ionicons name="card" size={13} color={colors.danger} />
          ) : null}
        </View>
        {dateLabel ? (
          <Text style={[styles.rowMeta, { color: deadlineColor(item.days_left) }]}>
            vence {dateLabel}
            {item.days_left !== null ? ` · ${item.days_left} días` : ""}
          </Text>
        ) : (
          <Text style={styles.rowMeta}>sin fecha límite</Text>
        )}
      </View>
      <MoneyText value={item.amount} size="sm" />
    </View>
  );
}

function AddButton({ onPress, label }: { onPress: () => void; label: string }) {
  return (
    <Pressable
      onPress={onPress}
      hitSlop={8}
      accessibilityLabel={label}
      style={({ pressed }) => [styles.addBtn, pressed && styles.pressed]}
    >
      <Ionicons name="add" size={18} color={colors.primary} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  content: { padding: 16, paddingBottom: 48 },
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
  hero: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 16,
    marginBottom: 12,
    gap: 4,
  },
  heroLabel: {
    color: colors.textSecondary,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
  heroSub: { color: colors.textSecondary, fontSize: 12, marginTop: 4 },
  heroSubStrong: { color: colors.textPrimary },
  nextIncome: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: colors.successSoft,
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
  },
  nextIncomeText: { color: colors.textPrimary, fontSize: 13, flex: 1 },
  sectionLabel: {
    color: colors.textSecondary,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 20,
    marginBottom: 8,
  },
  addBtn: {
    backgroundColor: colors.primarySoft,
    borderRadius: 999,
    padding: 6,
  },
  checklistBox: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    paddingHorizontal: 12,
    marginTop: 8,
  },
  checkRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingVertical: 12,
  },
  checkRowBorder: { borderTopWidth: 1, borderTopColor: colors.border },
  checkIndex: {
    color: colors.primary,
    fontSize: 14,
    fontWeight: "700",
    width: 20,
    textAlign: "center",
  },
  checkNameRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 12,
    marginBottom: 6,
    gap: 12,
  },
  rowBody: { flex: 1 },
  rowName: { color: colors.textPrimary, fontSize: 14, fontWeight: "600" },
  rowMeta: { color: colors.textSecondary, fontSize: 12, marginTop: 2 },
  dayBadge: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
  },
  dayBadgeText: { fontSize: 13, fontWeight: "700" },
  emptyBox: { alignItems: "center", paddingVertical: 24, gap: 12, paddingHorizontal: 16 },
  emptyText: { color: colors.textSecondary, fontSize: 14, textAlign: "center" },
  emptyRow: { color: colors.textSecondary, fontSize: 13, paddingVertical: 8 },
});
