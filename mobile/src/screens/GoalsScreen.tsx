import { Ionicons } from "@expo/vector-icons";
import { useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";

import GoalFormSheet from "../components/GoalFormSheet";
import MoneyText from "../components/MoneyText";
import { useGoals, type SavingsGoalOut } from "../services/queries/goals";
import { colors } from "../theme/colors";

function formatTargetDate(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(`${iso}T12:00:00`);
  return d.toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" });
}

export default function GoalsScreen() {
  const { data, isLoading, isError, refetch, isRefetching } = useGoals();
  const [sheetOpen, setSheetOpen] = useState(false);
  const [editing, setEditing] = useState<SavingsGoalOut | undefined>(undefined);

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
        <Text style={styles.errorText}>No pudimos cargar tus metas.</Text>
        <Pressable
          style={({ pressed }) => [styles.retryBtn, pressed && styles.pressed]}
          onPress={() => refetch()}
        >
          <Text style={styles.retryText}>Reintentar</Text>
        </Pressable>
      </View>
    );
  }

  const goals = data ?? [];

  return (
    <View style={styles.root}>
      <FlatList
        data={goals}
        keyExtractor={(g) => g.id}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={colors.primary} />
        }
        ListEmptyComponent={
          <View style={styles.emptyBox}>
            <Ionicons name="flag-outline" size={44} color={colors.textSecondary} />
            <Text style={styles.emptyText}>
              Definí una meta con monto y fecha, y registrá tu avance a medida que ahorrás.
            </Text>
            <Pressable
              style={({ pressed }) => [styles.emptyBtn, pressed && styles.pressed]}
              onPress={() => setSheetOpen(true)}
            >
              <Text style={styles.emptyBtnText}>Crear primera meta</Text>
            </Pressable>
          </View>
        }
        renderItem={({ item }) => {
          const dateLabel = formatTargetDate(item.target_date);
          return (
            <Pressable
              style={({ pressed }) => [styles.card, pressed && styles.pressed]}
              onPress={() => {
                setEditing(item);
                setSheetOpen(true);
              }}
            >
              <View style={styles.cardTop}>
                <Text style={styles.goalName} numberOfLines={1}>
                  {item.name}
                </Text>
                <Text style={styles.pct}>{item.pct}%</Text>
              </View>
              <View style={styles.barTrack}>
                <View
                  style={[
                    styles.barFill,
                    {
                      width: `${Math.min(item.pct, 100)}%`,
                      backgroundColor: item.pct >= 100 ? colors.success : colors.primary,
                    },
                  ]}
                />
              </View>
              <View style={styles.cardBottom}>
                <Text style={styles.amounts}>
                  <MoneyText value={item.current_amount} size="sm" /> de{" "}
                  <MoneyText
                    value={item.target_amount}
                    size="sm"
                    style={{ color: colors.textSecondary }}
                  />
                </Text>
                {dateLabel ? <Text style={styles.date}>{dateLabel}</Text> : null}
              </View>
            </Pressable>
          );
        }}
      />

      {goals.length > 0 ? (
        <Pressable
          style={({ pressed }) => [styles.fab, pressed && styles.fabPressed]}
          onPress={() => {
            setEditing(undefined);
            setSheetOpen(true);
          }}
          accessibilityLabel="Agregar meta"
        >
          <Ionicons name="add" size={28} color="#fff" />
        </Pressable>
      ) : null}

      <GoalFormSheet
        isVisible={sheetOpen}
        goal={editing}
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
    paddingVertical: 10,
    borderRadius: 10,
  },
  retryText: { color: "#fff", fontWeight: "600" },
  pressed: { opacity: 0.7 },
  list: { padding: 16, paddingBottom: 96 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 14,
    marginBottom: 8,
    gap: 10,
  },
  cardTop: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 8 },
  goalName: { color: colors.textPrimary, fontSize: 15, fontWeight: "600", flexShrink: 1 },
  pct: { color: colors.primary, fontSize: 14, fontWeight: "700" },
  barTrack: {
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.background,
    overflow: "hidden",
  },
  barFill: { height: 8, borderRadius: 4 },
  cardBottom: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  amounts: { color: colors.textPrimary, fontSize: 13 },
  date: { color: colors.textSecondary, fontSize: 12 },
  emptyBox: { alignItems: "center", paddingVertical: 40, gap: 12, paddingHorizontal: 24 },
  emptyText: { color: colors.textSecondary, fontSize: 14, textAlign: "center" },
  emptyBtn: {
    marginTop: 8,
    backgroundColor: colors.primary,
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 10,
  },
  emptyBtnText: { color: "#fff", fontWeight: "600", fontSize: 14 },
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
