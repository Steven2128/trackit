import BottomSheet, { BottomSheetScrollView, BottomSheetTextInput } from "@gorhom/bottom-sheet";
import { Ionicons } from "@expo/vector-icons";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Keyboard,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import {
  useDebtStrategy,
  type StrategyResultOut,
} from "../services/queries/debts";
import { colors } from "../theme/colors";
import { formatCOP, parseCOP } from "../utils/currency";
import MoneyText from "./MoneyText";

type Props = {
  isVisible: boolean;
  onClose: () => void;
};

const STRATEGY_LABEL: Record<string, string> = {
  avalanche: "Avalancha",
  snowball: "Bola de nieve",
};

function formatMonths(months: number | null): string {
  if (months === null) return "No alcanza";
  if (months === 0) return "Ya estás libre";
  const years = Math.floor(months / 12);
  const rest = months % 12;
  if (years === 0) return `${months} ${months === 1 ? "mes" : "meses"}`;
  if (rest === 0) return `${years} ${years === 1 ? "año" : "años"}`;
  return `${years} ${years === 1 ? "año" : "años"} ${rest} m`;
}

export default function StrategySheet({ isVisible, onClose }: Props) {
  const sheetRef = useRef<BottomSheet>(null);
  const snapPoints = useMemo(() => ["85%"], []);
  const [extraInput, setExtraInput] = useState("");
  // The query only fires when the user taps "Calcular" — extra is frozen then.
  const [extra, setExtra] = useState<number | null>(null);

  useEffect(() => {
    if (isVisible) sheetRef.current?.expand();
    else sheetRef.current?.close();
  }, [isVisible]);

  const query = useDebtStrategy(extra ?? 0, extra !== null);

  function handleCalculate() {
    Keyboard.dismiss();
    setExtra(parseCOP(extraInput) || 0);
  }

  const data = query.data;

  return (
    <BottomSheet
      ref={sheetRef}
      index={-1}
      snapPoints={snapPoints}
      enablePanDownToClose
      onClose={onClose}
      backgroundStyle={styles.bg}
      handleIndicatorStyle={styles.handle}
    >
      <BottomSheetScrollView contentContainerStyle={styles.body}>
        <Text style={styles.title}>Estrategia de pago</Text>
        <Text style={styles.subtitle}>
          ¿Cuánto podés abonar por mes además de los pagos mínimos?
        </Text>

        <View style={styles.inputRow}>
          <BottomSheetTextInput
            style={styles.input}
            placeholder="0"
            placeholderTextColor={colors.textSecondary}
            value={extraInput}
            onChangeText={setExtraInput}
            keyboardType="numeric"
          />
          <Pressable
            style={({ pressed }) => [styles.calcBtn, pressed && styles.pressed]}
            onPress={handleCalculate}
          >
            <Text style={styles.calcText}>Calcular</Text>
          </Pressable>
        </View>

        {extra === null ? null : query.isLoading ? (
          <ActivityIndicator size="large" color={colors.primary} style={styles.loading} />
        ) : query.isError || !data ? (
          <Text style={styles.errorText}>No pudimos calcular la estrategia.</Text>
        ) : (
          <>
            {!data.avalanche.converges ? (
              <View style={styles.warnBox}>
                <Ionicons name="warning" size={16} color={colors.warning} />
                <Text style={styles.warnText}>
                  Con ese abono la deuda no baja — los intereses crecen más rápido que
                  el pago. Subí el monto mensual.
                </Text>
              </View>
            ) : (
              <View style={styles.recommendBox}>
                <Ionicons name="trophy" size={16} color={colors.success} />
                <Text style={styles.recommendText}>
                  Recomendado: {STRATEGY_LABEL[data.recommended]}
                  {data.recommended === "avalanche" &&
                  Number(data.interest_saved_by_avalanche) > 0
                    ? ` — ahorrás ${formatCOP(data.interest_saved_by_avalanche)} en intereses`
                    : " — mismos intereses, victorias más rápidas"}
                </Text>
              </View>
            )}

            <StrategyCard
              result={data.avalanche}
              recommended={data.recommended === "avalanche"}
              description="Primero la tasa de interés más alta"
            />
            <StrategyCard
              result={data.snowball}
              recommended={data.recommended === "snowball"}
              description="Primero la deuda más chica"
            />
          </>
        )}
      </BottomSheetScrollView>
    </BottomSheet>
  );
}

function StrategyCard({
  result,
  recommended,
  description,
}: {
  result: StrategyResultOut;
  recommended: boolean;
  description: string;
}) {
  return (
    <View style={[styles.card, recommended && styles.cardRecommended]}>
      <View style={styles.cardHeader}>
        <Text style={styles.cardTitle}>{STRATEGY_LABEL[result.strategy]}</Text>
        {recommended ? (
          <View style={styles.badge}>
            <Text style={styles.badgeText}>Recomendada</Text>
          </View>
        ) : null}
      </View>
      <Text style={styles.cardDesc}>{description}</Text>

      <View style={styles.statsRow}>
        <View style={styles.stat}>
          <Text style={styles.statLabel}>Libre de deudas en</Text>
          <Text style={styles.statValue}>{formatMonths(result.months_to_free)}</Text>
        </View>
        <View style={styles.stat}>
          <Text style={styles.statLabel}>Intereses totales</Text>
          <MoneyText value={result.total_interest} size="md" />
        </View>
      </View>

      <Text style={styles.orderLabel}>Orden de pago</Text>
      {result.per_debt.map((d, i) => (
        <View key={d.name + i} style={styles.orderRow}>
          <Text style={styles.orderIndex}>{i + 1}</Text>
          <Text style={styles.orderName} numberOfLines={1}>
            {d.name}
          </Text>
          <Text style={styles.orderMonth}>
            {d.payoff_month !== null ? `mes ${d.payoff_month}` : "—"}
          </Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  bg: { backgroundColor: colors.surface },
  handle: { backgroundColor: colors.border },
  body: { padding: 16, paddingBottom: 40 },
  title: { color: colors.textPrimary, fontSize: 17, fontWeight: "700" },
  subtitle: { color: colors.textSecondary, fontSize: 13, marginTop: 4, marginBottom: 12 },
  inputRow: { flexDirection: "row", gap: 8, marginBottom: 16 },
  input: {
    flex: 1,
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    padding: 12,
    fontSize: 15,
    color: colors.textPrimary,
  },
  calcBtn: {
    backgroundColor: colors.primary,
    paddingHorizontal: 18,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
  },
  calcText: { color: "#fff", fontWeight: "600", fontSize: 14 },
  pressed: { opacity: 0.7 },
  loading: { marginTop: 24 },
  errorText: { color: colors.textSecondary, fontSize: 14, textAlign: "center", marginTop: 16 },
  warnBox: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: colors.warningSoft,
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
  },
  warnText: { color: colors.textPrimary, fontSize: 13, flex: 1 },
  recommendBox: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: colors.successSoft,
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
  },
  recommendText: { color: colors.textPrimary, fontSize: 13, flex: 1, fontWeight: "600" },
  card: {
    backgroundColor: colors.background,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 14,
    marginBottom: 12,
  },
  cardRecommended: { borderColor: colors.success },
  cardHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  cardTitle: { color: colors.textPrimary, fontSize: 15, fontWeight: "700" },
  badge: {
    backgroundColor: colors.successSoft,
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 3,
  },
  badgeText: { color: colors.success, fontSize: 11, fontWeight: "600" },
  cardDesc: { color: colors.textSecondary, fontSize: 12, marginTop: 2, marginBottom: 12 },
  statsRow: { flexDirection: "row", gap: 16, marginBottom: 12 },
  stat: { flex: 1 },
  statLabel: {
    color: colors.textSecondary,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.6,
    marginBottom: 4,
  },
  statValue: { color: colors.textPrimary, fontSize: 15, fontWeight: "700" },
  orderLabel: {
    color: colors.textSecondary,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.6,
    marginBottom: 6,
  },
  orderRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingVertical: 6,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  orderIndex: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: "700",
    width: 18,
    textAlign: "center",
  },
  orderName: { color: colors.textPrimary, fontSize: 14, flex: 1 },
  orderMonth: { color: colors.textSecondary, fontSize: 12 },
});
