import { ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";

import CategoryIcon from "../components/CategoryIcon";
import MoneyText from "../components/MoneyText";
import { useSubscriptions, type SubscriptionFrequency, type SubscriptionOut } from "../services/queries/subscriptions";
import { colors } from "../theme/colors";
import { formatDayHeader } from "../utils/dates";

const FREQUENCY_LABEL: Record<SubscriptionFrequency, string> = {
  weekly: "Semanal",
  biweekly: "Quincenal",
  monthly: "Mensual",
  yearly: "Anual",
};

// Occurrences per month for each cadence, used to normalize the header total.
const MONTHLY_FACTOR: Record<SubscriptionFrequency, number> = {
  weekly: 30 / 7,
  biweekly: 30 / 14,
  monthly: 1,
  yearly: 1 / 12,
};

function monthlyEquivalent(sub: SubscriptionOut): number {
  return Number(sub.average_amount) * MONTHLY_FACTOR[sub.frequency];
}

export default function SubscriptionsScreen() {
  const { data, isLoading, isError, refetch, isRefetching } = useSubscriptions();

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
        <Text style={styles.errorText}>No pudimos cargar las suscripciones.</Text>
        <Pressable style={styles.retryBtn} onPress={() => refetch()}>
          <Text style={styles.retryText}>Reintentar</Text>
        </Pressable>
      </View>
    );
  }

  const monthlyTotal = data.reduce((sum, sub) => sum + monthlyEquivalent(sub), 0);

  return (
    <ScrollView
      style={styles.root}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={colors.primary} />
      }
    >
      {data.length > 0 ? (
        <View style={styles.totalBox}>
          <Text style={styles.totalLabel}>Estimado mensual en recurrentes</Text>
          <MoneyText value={monthlyTotal} size="xl" />
        </View>
      ) : null}

      {data.length === 0 ? (
        <View style={styles.emptyBox}>
          <Text style={styles.emptyText}>
            Todavía no detectamos cargos recurrentes. Necesitamos al menos 2 cobros del mismo
            comercio con un intervalo regular.
          </Text>
        </View>
      ) : (
        data.map((sub) => (
          <View key={`${sub.merchant}-${sub.frequency}`} style={styles.row}>
            <CategoryIcon categoryKey={sub.category} />
            <View style={styles.rowBody}>
              <View style={styles.rowTop}>
                <Text style={styles.merchant} numberOfLines={1}>
                  {sub.merchant}
                </Text>
                <MoneyText value={sub.average_amount} size="sm" />
              </View>
              <View style={styles.rowBottom}>
                <View style={styles.badge}>
                  <Text style={styles.badgeText}>{FREQUENCY_LABEL[sub.frequency]}</Text>
                </View>
                <Text style={styles.nextCharge}>
                  Próximo: {formatDayHeader(sub.next_expected_at)}
                </Text>
              </View>
            </View>
          </View>
        ))
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
    paddingVertical: 8,
    borderRadius: 8,
  },
  retryText: { color: "#fff", fontWeight: "600" },
  totalBox: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 16,
    marginBottom: 16,
    gap: 4,
  },
  totalLabel: {
    color: colors.textSecondary,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
  emptyBox: { padding: 24 },
  emptyText: { color: colors.textSecondary, fontSize: 14, textAlign: "center" },
  row: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 12,
    marginBottom: 6,
    gap: 12,
  },
  rowBody: { flex: 1, gap: 6 },
  rowTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 8,
  },
  merchant: { color: colors.textPrimary, fontSize: 15, fontWeight: "600", flexShrink: 1 },
  rowBottom: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  badge: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  badgeText: { color: colors.textSecondary, fontSize: 11, fontWeight: "600" },
  nextCharge: { color: colors.textSecondary, fontSize: 12 },
});
