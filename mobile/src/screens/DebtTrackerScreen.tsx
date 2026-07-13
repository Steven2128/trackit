import { Ionicons } from "@expo/vector-icons";
import { useMemo, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";

import DebtCard from "../components/DebtCard";
import DebtFormSheet from "../components/DebtFormSheet";
import MoneyText from "../components/MoneyText";
import StrategySheet from "../components/StrategySheet";
import { useDebts, type DebtOut } from "../services/queries/debts";
import { colors } from "../theme/colors";

export default function DebtTrackerScreen() {
  const { data, isLoading, isError, refetch, isRefetching } = useDebts();
  const [sheetOpen, setSheetOpen] = useState(false);
  const [strategyOpen, setStrategyOpen] = useState(false);
  const [editing, setEditing] = useState<DebtOut | undefined>(undefined);

  const { totalDebt, totalMin, count } = useMemo(() => {
    const list = data ?? [];
    return {
      totalDebt: list.reduce((s, d) => s + Number(d.total_amount || 0), 0),
      totalMin: list.reduce((s, d) => s + Number(d.minimum_payment || 0), 0),
      count: list.length,
    };
  }, [data]);

  function openCreate() {
    setEditing(undefined);
    setSheetOpen(true);
  }

  function openEdit(debt: DebtOut) {
    setEditing(debt);
    setSheetOpen(true);
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
        <Text style={styles.errorText}>No pudimos cargar tus deudas.</Text>
        <Pressable style={styles.retryBtn} onPress={() => refetch()}>
          <Text style={styles.retryText}>Reintentar</Text>
        </Pressable>
      </View>
    );
  }

  const debts = data ?? [];

  return (
    <View style={styles.root}>
      <FlatList
        data={debts}
        keyExtractor={(d) => d.id}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={isRefetching}
            onRefresh={refetch}
            tintColor={colors.primary}
          />
        }
        ListHeaderComponent={
          <View>
            <View style={styles.hero}>
              <Text style={styles.heroLabel}>Deuda total</Text>
              <MoneyText value={totalDebt} size="xl" style={styles.heroMoney} />
              <Text style={styles.heroSub}>
                {count} {count === 1 ? "deuda" : "deudas"} · pago mínimo {" "}
                <MoneyText value={totalMin} size="sm" style={styles.heroSubMoney} />
                /mes
              </Text>
            </View>
            {debts.length > 0 ? (
              <Pressable
                style={({ pressed }) => [styles.strategyBtn, pressed && styles.pressed]}
                onPress={() => setStrategyOpen(true)}
              >
                <Ionicons name="trending-down" size={18} color={colors.primary} />
                <Text style={styles.strategyText}>Estrategia de pago</Text>
                <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
              </Pressable>
            ) : null}
          </View>
        }
        ListEmptyComponent={
          <View style={styles.emptyBox}>
            <Ionicons name="checkmark-done-circle" size={44} color={colors.success} />
            <Text style={styles.emptyText}>Sin deudas registradas</Text>
            <Pressable
              style={({ pressed }) => [styles.emptyBtn, pressed && styles.pressed]}
              onPress={openCreate}
            >
              <Text style={styles.emptyBtnText}>Agregar primera deuda</Text>
            </Pressable>
          </View>
        }
        renderItem={({ item }) => <DebtCard debt={item} onPress={openEdit} />}
      />

      {debts.length > 0 ? (
        <Pressable
          style={({ pressed }) => [styles.fab, pressed && styles.fabPressed]}
          onPress={openCreate}
          accessibilityLabel="Agregar deuda"
        >
          <Ionicons name="add" size={28} color="#fff" />
        </Pressable>
      ) : null}

      <DebtFormSheet
        isVisible={sheetOpen}
        debt={editing}
        onClose={() => {
          setSheetOpen(false);
          setEditing(undefined);
        }}
      />

      <StrategySheet isVisible={strategyOpen} onClose={() => setStrategyOpen(false)} />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
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
  list: { padding: 16, paddingBottom: 96 },
  // Surface card with a red accent instead of a solid red block — the
  // number carries the weight; a full red panel reads as a permanent alarm.
  hero: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    borderLeftWidth: 3,
    borderLeftColor: colors.danger,
    padding: 16,
    marginBottom: 16,
  },
  heroLabel: {
    color: colors.textSecondary,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
  heroMoney: { color: colors.danger, marginTop: 4 },
  heroSub: { color: colors.textSecondary, fontSize: 12, marginTop: 6 },
  heroSubMoney: { color: colors.textPrimary, fontWeight: "600" },
  strategyBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: 14,
    marginBottom: 16,
  },
  strategyText: { color: colors.textPrimary, fontSize: 14, fontWeight: "600", flex: 1 },
  emptyBox: { alignItems: "center", paddingVertical: 40, gap: 12 },
  emptyText: { color: colors.textSecondary, fontSize: 14 },
  emptyBtn: {
    marginTop: 8,
    backgroundColor: colors.primary,
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 10,
  },
  emptyBtnText: { color: "#fff", fontWeight: "600", fontSize: 14 },
  pressed: { opacity: 0.7 },
  fab: {
    position: "absolute",
    right: 16,
    bottom: 24,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 6,
  },
  fabPressed: { opacity: 0.85, transform: [{ scale: 0.96 }] },
});
