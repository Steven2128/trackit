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

import AccountSheet, { type AccountSheetMode } from "../components/AccountSheet";
import MoneyText from "../components/MoneyText";
import { useNetWorth, type AccountKind, type AccountOut } from "../services/queries/accounts";
import { colors } from "../theme/colors";

type IconName = keyof typeof Ionicons.glyphMap;

// Accounts the app can track, in display order.
const KINDS: { kind: AccountKind; name: string; icon: IconName; hint: string }[] = [
  { kind: "davivienda", name: "Davivienda", icon: "business", hint: "Se actualiza con los emails de Davivienda" },
  { kind: "nequi", name: "Nequi", icon: "phone-portrait", hint: "Se actualiza con los emails de Nequi" },
  { kind: "cash", name: "Efectivo", icon: "cash", hint: "Suben los retiros, bajan los gastos que cargás" },
];

function sinceLabel(iso: string | null): string {
  if (!iso) return "sin conciliar";
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days === 0) return "conciliada hoy";
  if (days === 1) return "conciliada ayer";
  return `conciliada hace ${days} días`;
}

export default function NetWorthScreen() {
  const { data, isLoading, isError, refetch, isRefetching } = useNetWorth();
  const [editing, setEditing] = useState<AccountSheetMode | null>(null);

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
        <Text style={styles.errorText}>No pudimos cargar tu patrimonio.</Text>
        <Pressable style={styles.retryBtn} onPress={() => refetch()}>
          <Text style={styles.retryText}>Reintentar</Text>
        </Pressable>
      </View>
    );
  }

  const byKind = new Map<AccountKind, AccountOut>(data.accounts.map((a) => [a.kind, a]));
  const netWorth = Number(data.net_worth);
  const unexplained = Number(data.unexplained_this_month);
  const hasCash = byKind.has("cash");

  return (
    <View style={styles.root}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={colors.primary} />
        }
      >
        <View style={styles.hero}>
          <Text style={styles.heroLabel}>Patrimonio neto</Text>
          <MoneyText
            value={data.net_worth}
            size="xl"
            style={netWorth < 0 ? { color: colors.danger } : undefined}
          />
          <Text style={styles.heroSub}>
            Cuentas <MoneyText value={data.total_assets} size="sm" style={styles.heroStrong} /> −
            deudas <MoneyText value={data.total_debt} size="sm" style={styles.heroStrong} />
          </Text>
        </View>

        {unexplained !== 0 ? (
          <View style={styles.unexplained}>
            <Ionicons name="help-circle" size={18} color={colors.warning} />
            <Text style={styles.unexplainedText}>
              Este mes {unexplained < 0 ? "se fueron" : "aparecieron"}{" "}
              <MoneyText value={Math.abs(unexplained)} size="sm" style={{ color: colors.warning }} />{" "}
              sin email que lo explique (efectivo, intereses o cobros).
            </Text>
          </View>
        ) : null}

        <Text style={styles.sectionLabel}>Cuentas</Text>
        {KINDS.map(({ kind, name, icon, hint }) => {
          const account = byKind.get(kind);
          if (!account) {
            return (
              <Pressable
                key={kind}
                style={({ pressed }) => [styles.row, styles.rowEmpty, pressed && styles.pressed]}
                onPress={() => setEditing({ mode: "setup", kind, name })}
              >
                <Ionicons name={icon} size={20} color={colors.textSecondary} />
                <View style={styles.rowBody}>
                  <Text style={styles.rowName}>{name}</Text>
                  <Text style={styles.rowMeta}>Tocá para cargar el saldo de hoy</Text>
                </View>
                <Ionicons name="add-circle" size={22} color={colors.primary} />
              </Pressable>
            );
          }
          return (
            <View key={kind} style={styles.row}>
              <Ionicons name={icon} size={20} color={colors.primary} />
              <Pressable
                style={styles.rowBody}
                onLongPress={() => setEditing({ mode: "setup", kind, name: account.name })}
                accessibilityHint="Mantené presionado para reiniciar el saldo"
              >
                <Text style={styles.rowName}>{account.name}</Text>
                <Text style={styles.rowMeta}>
                  {hint} · {sinceLabel(account.last_reconciled_at)}
                </Text>
              </Pressable>
              <View style={styles.rowRight}>
                <MoneyText value={account.balance} size="md" />
                <Pressable
                  hitSlop={8}
                  onPress={() =>
                    setEditing({
                      mode: "reconcile",
                      kind,
                      name: account.name,
                      computed: account.balance,
                    })
                  }
                >
                  <Text style={styles.reconcile}>Conciliar</Text>
                </Pressable>
              </View>
            </View>
          );
        })}

        {hasCash ? (
          <Pressable
            style={({ pressed }) => [styles.cashBtn, pressed && styles.pressed]}
            onPress={() => setEditing({ mode: "cash" })}
          >
            <Ionicons name="remove-circle-outline" size={18} color={colors.primary} />
            <Text style={styles.cashText}>Registrar gasto en efectivo</Text>
          </Pressable>
        ) : null}

        <Text style={styles.footnote}>
          Los bancos no mandan el saldo por email: la app parte del saldo que cargás y le suma o
          resta cada movimiento. Conciliá cada tanto para ver si se escapó algo. Mantené presionada
          una cuenta para reiniciar su saldo.
        </Text>
      </ScrollView>

      <AccountSheet editing={editing} onClose={() => setEditing(null)} />
    </View>
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
    gap: 4,
  },
  heroLabel: {
    color: colors.textSecondary,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
  heroSub: { color: colors.textSecondary, fontSize: 12, marginTop: 4 },
  heroStrong: { color: colors.textPrimary },
  unexplained: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: colors.warningSoft,
    borderRadius: 12,
    padding: 12,
    marginTop: 12,
  },
  unexplainedText: { color: colors.textPrimary, fontSize: 13, flex: 1 },
  sectionLabel: {
    color: colors.textSecondary,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.6,
    marginTop: 20,
    marginBottom: 8,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 12,
    marginBottom: 6,
    gap: 12,
  },
  rowEmpty: { borderWidth: 1, borderColor: colors.border, borderStyle: "dashed" },
  rowBody: { flex: 1 },
  rowName: { color: colors.textPrimary, fontSize: 15, fontWeight: "600" },
  rowMeta: { color: colors.textSecondary, fontSize: 11, marginTop: 2 },
  rowRight: { alignItems: "flex-end", gap: 4 },
  reconcile: { color: colors.primary, fontSize: 12, fontWeight: "600" },
  cashBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: colors.primarySoft,
    borderRadius: 12,
    padding: 12,
    marginTop: 8,
  },
  cashText: { color: colors.primary, fontSize: 14, fontWeight: "600" },
  footnote: { color: colors.textSecondary, fontSize: 11, lineHeight: 16, marginTop: 20 },
});
