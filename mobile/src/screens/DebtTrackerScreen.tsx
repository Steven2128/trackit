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
import { useDebts, type DebtOut } from "../services/queries/debts";
import { colors } from "../theme/colors";

export default function DebtTrackerScreen() {
  const { data, isLoading, isError, refetch, isRefetching } = useDebts();
  const [sheetOpen, setSheetOpen] = useState(false);
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
          <View style={styles.hero}>
            <Text style={styles.heroLabel}>DEUDA TOTAL</Text>
            <MoneyText value={totalDebt} size="xl" style={styles.heroMoney} />
            <Text style={styles.heroSub}>
              {count} {count === 1 ? "deuda" : "deudas"} · pago mínimo {" "}
              <MoneyText value={totalMin} size="sm" style={styles.heroSubMoney} />
              /mes
            </Text>
          </View>
        }
        ListEmptyComponent={
          <View style={styles.emptyBox}>
            <Text style={styles.emptyEmoji}>🎉</Text>
            <Text style={styles.emptyText}>Sin deudas registradas</Text>
            <Pressable style={styles.emptyBtn} onPress={openCreate}>
              <Text style={styles.emptyBtnText}>Agregar primera deuda</Text>
            </Pressable>
          </View>
        }
        renderItem={({ item }) => <DebtCard debt={item} onPress={openEdit} />}
      />

      {debts.length > 0 ? (
        <Pressable style={styles.fab} onPress={openCreate}>
          <Text style={styles.fabPlus}>+</Text>
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
  hero: {
    backgroundColor: colors.danger,
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
  },
  heroLabel: {
    color: "rgba(255,255,255,0.75)",
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  heroMoney: { color: "#fff", marginTop: 4 },
  heroSub: { color: "rgba(255,255,255,0.75)", fontSize: 11, marginTop: 6 },
  heroSubMoney: { color: "#fff", fontWeight: "600" },
  emptyBox: { alignItems: "center", paddingVertical: 40, gap: 12 },
  emptyEmoji: { fontSize: 40 },
  emptyText: { color: colors.textSecondary, fontSize: 14 },
  emptyBtn: {
    marginTop: 8,
    backgroundColor: colors.primary,
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 8,
  },
  emptyBtnText: { color: "#fff", fontWeight: "600", fontSize: 14 },
  fab: {
    position: "absolute",
    right: 16,
    bottom: 24,
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 6,
  },
  fabPlus: { color: "#fff", fontSize: 28, fontWeight: "300", marginTop: -2 },
});
