import { Ionicons } from "@expo/vector-icons";
import { useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

import {
  parseRef,
  plainName,
  useCashPosition,
  type CashPosition,
  type PositionLine,
  type PositionStatus,
  type PositionWindow,
} from "../services/queries/cashPosition";
import { colors } from "../theme/colors";
import { formatIsoDay } from "../utils/dates";
import MoneyText from "./MoneyText";
import PayObligationSheet from "./PayObligationSheet";

const STATUS: Record<PositionStatus, { label: string; color: string; soft: string }> = {
  confirmed: { label: "Confirmado", color: colors.success, soft: colors.successSoft },
  provisional: { label: "Con estimados", color: colors.warning, soft: colors.warningSoft },
  indeterminate: { label: "Faltan datos", color: colors.danger, soft: colors.dangerSoft },
};

/** "Tu quincena": what is really free until the payday after next, and
 *  what's left to pay, window by window — the plan the user does by hand
 *  on payday (GET /cashflow/position). */
export default function FortnightCard() {
  const { data, isLoading, isError, refetch } = useCashPosition();
  const [paying, setPaying] = useState<PositionLine | null>(null);

  if (isLoading) {
    return (
      <View style={[styles.card, styles.centered]}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }
  if (isError || !data) {
    return (
      <Pressable style={[styles.card, styles.centered]} onPress={() => refetch()}>
        <Text style={styles.muted}>No pudimos calcular tu quincena. Tocá para reintentar.</Text>
      </Pressable>
    );
  }

  return (
    <View style={styles.card}>
      <Header data={data} />
      <Progress data={data} />
      {data.windows.map((w, i) =>
        i === 0 && w.obligations.length === 0 ? null : (
          <WindowBlock key={w.start} window={w} first={i === 0} onPay={setPaying} />
        ),
      )}
      <Warnings data={data} />
      <PayObligationSheet line={paying} onClose={() => setPaying(null)} />
    </View>
  );
}

function Header({ data }: { data: CashPosition }) {
  const status = STATUS[data.status];
  const free = Number(data.free);
  const until = data.windows.length > 1 ? data.windows[data.windows.length - 1].start : data.horizon_end;
  return (
    <>
      <View style={styles.headerRow}>
        <Text style={styles.kicker}>Tu quincena · hasta el {formatIsoDay(until)}</Text>
        <View style={[styles.badge, { backgroundColor: status.soft }]}>
          <Text style={[styles.badgeText, { color: status.color }]}>{status.label}</Text>
        </View>
      </View>
      <Text style={styles.freeLabel}>
        {data.status === "indeterminate" ? "Libre como mucho" : "Libre de verdad"}
      </Text>
      <MoneyText
        value={data.free}
        size="xl"
        style={free < 0 ? { color: colors.danger } : undefined}
      />
      <Text style={styles.breakdown}>
        Tenés <MoneyText value={data.balance} size="sm" style={styles.breakdownMoney} />
        {Number(data.held_for_others) > 0 ? (
          <>
            {" "}· no es tuyo{" "}
            <MoneyText value={data.held_for_others} size="sm" style={styles.breakdownMoney} />
          </>
        ) : null}
        {Number(data.reserve_for_later) > 0 ? (
          <>
            {" "}· apartado para después{" "}
            <MoneyText value={data.reserve_for_later} size="sm" style={styles.breakdownMoney} />
          </>
        ) : null}
      </Text>
      {data.deficit ? (
        <Text style={styles.deficit}>
          Te faltan <MoneyText value={data.deficit.amount} size="sm" style={{ color: colors.danger }} />{" "}
          desde el {formatIsoDay(data.deficit.window_start)}
          {data.deficit.obligations.length ? ` para ${data.deficit.obligations.join(", ")}` : ""}.
        </Text>
      ) : null}
    </>
  );
}

function Progress({ data }: { data: CashPosition }) {
  const lines = data.windows.flatMap((w) => w.obligations);
  if (lines.length === 0) return null;
  const total = lines.reduce((s, l) => s + Number(l.total), 0);
  const left = lines.reduce((s, l) => s + Number(l.amount), 0);
  const pct = total > 0 ? Math.min(100, ((total - left) / total) * 100) : 0;
  return (
    <View style={styles.progress}>
      <View style={styles.progressRow}>
        <Text style={styles.progressLabel}>Te queda por pagar</Text>
        <Text style={styles.progressValue}>
          <MoneyText value={left} size="md" /> <Text style={styles.muted}>de </Text>
          <MoneyText value={total} size="sm" style={styles.muted} />
        </Text>
      </View>
      <View style={styles.track}>
        <View style={[styles.fill, { width: `${pct}%` }]} />
      </View>
    </View>
  );
}

function WindowBlock({
  window: w,
  first,
  onPay,
}: {
  window: PositionWindow;
  first: boolean;
  onPay: (line: PositionLine) => void;
}) {
  const title = first
    ? "Antes de tu próxima nómina"
    : `Con ${w.income_names.map(plainName).join(" + ") || "lo que entra"} · ${formatIsoDay(w.start)}`;
  return (
    <View style={styles.window}>
      <View style={styles.windowHeader}>
        <Text style={styles.windowTitle}>{title}</Text>
        {Number(w.income) > 0 ? (
          <MoneyText value={w.income} size="sm" positive signed />
        ) : null}
      </View>
      {w.obligations.length === 0 ? (
        <Text style={styles.muted}>Nada que pagar acá.</Text>
      ) : (
        w.obligations.map((line, i) => (
          <LineRow key={(line.ref ?? line.name) + i} line={line} onPay={onPay} />
        ))
      )}
      <View style={styles.windowFooter}>
        <Text style={styles.muted}>Te queda</Text>
        <MoneyText
          value={w.balance_after}
          size="sm"
          style={Number(w.balance_after) < 0 ? { color: colors.danger } : undefined}
        />
      </View>
    </View>
  );
}

function LineRow({ line, onPay }: { line: PositionLine; onPay: (l: PositionLine) => void }) {
  const done = Number(line.amount) === 0;
  const paid = Number(line.total) - Number(line.amount);
  // Paid lines open the sheet too, to undo a payment marked by mistake.
  const payable = parseRef(line.ref) !== null;
  return (
    <View style={styles.line}>
      <Ionicons
        name={done ? "checkmark-circle" : "ellipse-outline"}
        size={18}
        color={done ? colors.success : colors.textSecondary}
      />
      <View style={styles.lineBody}>
        <Text style={[styles.lineName, done && styles.lineDone]} numberOfLines={1}>
          {plainName(line.name)}
          {line.estimated ? <Text style={styles.estimated}> · estimado</Text> : null}
        </Text>
        <Text style={styles.lineMeta}>
          {line.due ? `vence ${formatIsoDay(line.due)}` : "sin fecha"}
          {!done && paid > 0 ? (
            <>
              {" "}· pagaste <MoneyText value={paid} size="sm" style={styles.lineMetaMoney} />
            </>
          ) : null}
        </Text>
      </View>
      <MoneyText
        value={done ? line.total : line.amount}
        size="sm"
        style={done ? styles.lineDone : undefined}
      />
      {payable ? (
        <Pressable
          onPress={() => onPay(line)}
          style={({ pressed }) => [styles.payBtn, pressed && { opacity: 0.6 }]}
          accessibilityLabel={`${done ? "Ver pago de" : "Pagar"} ${plainName(line.name)}`}
        >
          <Text style={styles.payText}>{done ? "Ver" : "Pagar"}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

function Warnings({ data }: { data: CashPosition }) {
  const items = [
    ...data.missing.map((m) => `Falta: ${m}`),
    ...data.overdue.map((o) => `Vencido: ${o}`),
    ...data.late_incomes.map((i) => `No llegó todavía: ${i}`),
    ...data.notes,
  ];
  if (items.length === 0) return null;
  return (
    <View style={styles.warnings}>
      {items.map((t) => (
        <View key={t} style={styles.warningRow}>
          <Ionicons name="alert-circle-outline" size={14} color={colors.warning} />
          <Text style={styles.warningText}>{t}</Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
    gap: 4,
  },
  centered: { alignItems: "center", justifyContent: "center", minHeight: 120 },
  muted: { color: colors.textSecondary, fontSize: 12 },
  headerRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  kicker: {
    color: colors.textSecondary,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
  badge: { borderRadius: 999, paddingHorizontal: 8, paddingVertical: 3 },
  badgeText: { fontSize: 11, fontWeight: "700" },
  freeLabel: { color: colors.textSecondary, fontSize: 13, marginTop: 8 },
  breakdown: { color: colors.textSecondary, fontSize: 12, marginTop: 2 },
  breakdownMoney: { color: colors.textSecondary, fontWeight: "600" },
  deficit: { color: colors.danger, fontSize: 12, marginTop: 6 },
  progress: { marginTop: 12, gap: 6 },
  progressRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" },
  progressLabel: { color: colors.textPrimary, fontSize: 13, fontWeight: "600" },
  progressValue: { color: colors.textPrimary },
  track: { height: 6, borderRadius: 3, backgroundColor: colors.background, overflow: "hidden" },
  fill: { height: 6, borderRadius: 3, backgroundColor: colors.success },
  window: {
    marginTop: 12,
    backgroundColor: colors.background,
    borderRadius: 12,
    padding: 12,
    gap: 8,
  },
  windowHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  windowTitle: { color: colors.textPrimary, fontSize: 13, fontWeight: "600", flex: 1 },
  windowFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: 8,
  },
  line: { flexDirection: "row", alignItems: "center", gap: 10 },
  lineBody: { flex: 1, minWidth: 0 },
  lineName: { color: colors.textPrimary, fontSize: 14 },
  lineDone: { color: colors.textSecondary, textDecorationLine: "line-through" },
  lineMeta: { color: colors.textSecondary, fontSize: 11 },
  lineMetaMoney: { color: colors.textSecondary },
  estimated: { color: colors.warning, fontSize: 11 },
  payBtn: {
    borderWidth: 1,
    borderColor: colors.primary,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  payText: { color: colors.primary, fontSize: 12, fontWeight: "700" },
  warnings: { marginTop: 10, gap: 4 },
  warningRow: { flexDirection: "row", gap: 6, alignItems: "flex-start" },
  warningText: { color: colors.textSecondary, fontSize: 12, flex: 1 },
});
