import { Ionicons } from "@expo/vector-icons";
import type { ComponentProps, ReactNode } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import type { DashboardResponse } from "../services/queries/dashboard";
import type { NetWorthOut } from "../services/queries/accounts";
import { colors } from "../theme/colors";
import { useIsWide } from "../theme/layout";
import MoneyText from "./MoneyText";

type Props = {
  data: DashboardResponse;
  netWorth: NetWorthOut | undefined;
  onSpent: () => void;
  onReceived: () => void;
  onNetWorth: () => void;
  onDebts: () => void;
};

/** The month at a glance: spent (vs last month), received, net worth, debt.
 *  Four across on wide screens, a 2×2 grid on phones. */
export default function DashboardKpis({
  data,
  netWorth,
  onSpent,
  onReceived,
  onNetWorth,
  onDebts,
}: Props) {
  const isWide = useIsWide();
  const { current_month, debts, monthly_trend } = data;
  const spent = Number(current_month.total_spent);
  const received = Number(current_month.total_received);
  const prev = monthly_trend.length > 1 ? Number(monthly_trend[monthly_trend.length - 2].total_spent) : 0;
  const delta = prev > 0 ? Math.round(((spent - prev) / prev) * 100) : null;
  const net = received - spent;

  return (
    <View style={[styles.grid, isWide && styles.gridWide]}>
      <Tile
        label="Gastado este mes"
        icon="arrow-up-circle-outline"
        onPress={onSpent}
        value={<MoneyText value={spent} size="lg" />}
        meta={
          delta === null ? (
            `${current_month.transaction_count} movimientos`
          ) : (
            <Text style={{ color: delta > 0 ? colors.warning : colors.success }}>
              {delta > 0 ? "▲" : "▼"} {Math.abs(delta)}% vs. mes pasado
            </Text>
          )
        }
      />
      <Tile
        label="Recibido este mes"
        icon="arrow-down-circle-outline"
        onPress={onReceived}
        value={<MoneyText value={received} size="lg" positive={received > 0} />}
        meta={
          received > 0 ? (
            <Text style={{ color: net >= 0 ? colors.success : colors.danger }}>
              {net >= 0 ? "Te sobran " : "Gastaste de más "}
              <MoneyText
                value={Math.abs(net)}
                size="sm"
                style={{ color: net >= 0 ? colors.success : colors.danger, fontWeight: "600" }}
              />
            </Text>
          ) : (
            "Sin ingresos todavía"
          )
        }
      />
      <Tile
        label="Patrimonio neto"
        icon="wallet-outline"
        onPress={onNetWorth}
        value={
          netWorth?.accounts.length ? (
            <MoneyText
              value={netWorth.net_worth}
              size="lg"
              style={Number(netWorth.net_worth) < 0 ? { color: colors.danger } : undefined}
            />
          ) : (
            <Text style={styles.empty}>Cargá tus cuentas</Text>
          )
        }
        meta={
          netWorth?.accounts.length ? (
            <>
              Cuentas{" "}
              <MoneyText value={netWorth.total_assets} size="sm" style={styles.metaMoney} />
            </>
          ) : null
        }
      />
      <Tile
        label="Deuda total"
        icon="card-outline"
        onPress={onDebts}
        accent={debts.debt_count === 0 ? colors.success : colors.danger}
        value={
          debts.debt_count === 0 ? (
            <Text style={[styles.empty, { color: colors.success }]}>Sin deudas</Text>
          ) : (
            <MoneyText value={debts.total_debt} size="lg" />
          )
        }
        meta={
          debts.debt_count === 0 ? null : (
            <>
              {debts.debt_count} · mín{" "}
              <MoneyText value={debts.total_minimum_payment} size="sm" style={styles.metaMoney} />
              /mes
            </>
          )
        }
      />
    </View>
  );
}

function Tile({
  label,
  icon,
  value,
  meta,
  accent,
  onPress,
}: {
  label: string;
  icon: ComponentProps<typeof Ionicons>["name"];
  value: ReactNode;
  meta: ReactNode;
  accent?: string;
  onPress: () => void;
}) {
  const isWide = useIsWide();
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.tile,
        isWide && styles.tileWide,
        accent ? { borderLeftWidth: 3, borderLeftColor: accent } : null,
        pressed && { opacity: 0.7 },
      ]}
    >
      <View style={styles.labelRow}>
        <Ionicons name={icon} size={14} color={colors.textSecondary} />
        <Text style={styles.label} numberOfLines={1}>
          {label}
        </Text>
      </View>
      {value}
      {meta ? (
        <Text style={styles.meta} numberOfLines={1}>
          {meta}
        </Text>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 16 },
  gridWide: { flexWrap: "nowrap", gap: 12 },
  tileWide: { flexBasis: 0 },
  tile: {
    flexGrow: 1,
    flexBasis: "45%",
    minWidth: 0,
    backgroundColor: colors.surface,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 14,
    gap: 4,
  },
  labelRow: { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 2 },
  label: {
    color: colors.textSecondary,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.6,
    flexShrink: 1,
  },
  meta: { color: colors.textSecondary, fontSize: 12 },
  metaMoney: { color: colors.textSecondary, fontWeight: "600" },
  empty: { color: colors.textSecondary, fontSize: 15, fontWeight: "600", marginVertical: 2 },
});
