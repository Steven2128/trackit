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

import CategoryIcon from "../components/CategoryIcon";
import MoneyText from "../components/MoneyText";
import {
  useCardStatement,
  useCards,
  type CardOut,
  type InstallmentPlan,
  type StatementLine,
  type StatementSummary,
} from "../services/queries/cards";
import { colors, radius, spacing, type } from "../theme/colors";
import { pageStyle, useIsWide } from "../theme/layout";
import { formatCOP } from "../utils/currency";

const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const MESES_LARGOS = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

// "2026-11-20" is a calendar day, not an instant: noon keeps it on that day
// in any timezone.
function asDate(ymd: string): Date {
  return new Date(`${ymd.slice(0, 10)}T12:00:00`);
}

function shortDay(ymd: string | null | undefined): string {
  if (!ymd) return "—";
  const d = asDate(ymd);
  return `${d.getDate()} ${MESES[d.getMonth()]}`;
}

function daysUntil(ymd: string): number {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 12);
  return Math.round((asDate(ymd).getTime() - today.getTime()) / 86_400_000);
}

function statementLabel(s: StatementSummary): string {
  const d = asDate(s.period_end);
  return `${MESES_LARGOS[d.getMonth()]} ${d.getFullYear()}`;
}

/** Month of the last installment: `remaining` statements after `from`. */
function endsOn(from: string | null, remaining: number): string | null {
  if (!from) return null;
  const d = asDate(from);
  const end = new Date(d.getFullYear(), d.getMonth() + remaining, 1);
  return `${MESES[end.getMonth()]} ${end.getFullYear()}`;
}

function Bar({ ratio, color }: { ratio: number; color: string }) {
  const pct = Math.max(0, Math.min(1, Number.isFinite(ratio) ? ratio : 0));
  return (
    <View style={styles.barTrack}>
      <View style={[styles.barFill, { width: `${pct * 100}%`, backgroundColor: color }]} />
    </View>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      {children}
    </View>
  );
}

function CardVisual({ card }: { card: CardOut }) {
  const balance = Number(card.balance);
  const limit = card.credit_limit ? Number(card.credit_limit) : null;
  const used = limit ? balance / limit : 0;
  const usedColor = used >= 0.8 ? colors.danger : used >= 0.5 ? colors.warning : colors.success;
  return (
    <View style={styles.plastic}>
      {/* Soft shapes instead of a gradient: no extra native dependency. */}
      <View style={[styles.blob, styles.blobA]} />
      <View style={[styles.blob, styles.blobB]} />
      <View style={styles.plasticTop}>
        <Text style={styles.plasticName} numberOfLines={1}>{card.name}</Text>
        <View style={styles.plasticChip}>
          <Ionicons name="card" size={12} color="#fff" />
          <Text style={styles.plasticChipText}>Crédito</Text>
        </View>
      </View>
      <Text style={styles.plasticLabel}>Saldo usado</Text>
      <MoneyText value={balance} style={styles.plasticMoney} />
      {limit ? (
        <View style={{ marginTop: spacing.md }}>
          <View style={styles.plasticTrack}>
            <View
              style={[
                styles.plasticFill,
                { width: `${Math.min(used, 1) * 100}%`, backgroundColor: usedColor },
              ]}
            />
          </View>
          <View style={styles.plasticFoot}>
            <Text style={styles.plasticFootText}>
              {Math.round(used * 100)}% del cupo de {formatCOP(limit)}
            </Text>
            <Text style={styles.plasticFootText}>
              Disponible <Text style={styles.plasticFootStrong}>{formatCOP(card.available)}</Text>
            </Text>
          </View>
        </View>
      ) : null}
    </View>
  );
}

function ToPay({ card }: { card: CardOut }) {
  const minimum = Number(card.minimum_payment ?? 0);
  const paid = Number(card.paid_since_cutoff);
  const left = Math.max(minimum - paid, 0);
  const done = minimum > 0 && left < 1;
  const days = card.payment_due_date ? daysUntil(card.payment_due_date) : null;
  const latest = card.statements[0];

  let chip: { text: string; color: string; soft: string } | null = null;
  if (done) chip = { text: "Pagado", color: colors.success, soft: colors.successSoft };
  else if (days !== null && minimum > 0) {
    if (days < 0) chip = { text: `Venció hace ${-days} d`, color: colors.danger, soft: colors.dangerSoft };
    else if (days === 0) chip = { text: "Vence hoy", color: colors.danger, soft: colors.dangerSoft };
    else if (days <= 5) chip = { text: `Faltan ${days} d`, color: colors.warning, soft: colors.warningSoft };
    else chip = { text: `Faltan ${days} d`, color: colors.primary, soft: colors.primarySoft };
  }

  return (
    <View style={styles.panel}>
      <View style={styles.panelHead}>
        <Text style={styles.panelTitle}>Extracto a pagar</Text>
        {chip ? (
          <View style={[styles.chip, { backgroundColor: chip.soft }]}>
            <Text style={[styles.chipText, { color: chip.color }]}>{chip.text}</Text>
          </View>
        ) : null}
      </View>
      {minimum > 0 ? (
        <>
          <Text style={styles.kicker}>Pago mínimo</Text>
          <MoneyText value={done ? minimum : left} style={styles.bigMoney} />
          <Text style={styles.sub}>
            {done ? "Listo por este mes" : `Hasta el ${shortDay(card.payment_due_date)}`}
          </Text>
          <View style={{ marginTop: spacing.md }}>
            <Bar ratio={minimum ? paid / minimum : 0} color={done ? colors.success : colors.primary} />
            <Text style={styles.barCaption}>
              Pagado {formatCOP(Math.min(paid, minimum))} de {formatCOP(minimum)}
            </Text>
          </View>
          <View style={styles.divider} />
          <Row label="Corte">
            <Text style={styles.rowValue}>{shortDay(card.cutoff_date)}</Text>
          </Row>
          <Row label="Fecha límite">
            <Text style={styles.rowValue}>{shortDay(card.payment_due_date)}</Text>
          </Row>
          {latest?.total_payment ? (
            <Row label="Pago total del extracto">
              <MoneyText value={latest.total_payment} size="md" />
            </Row>
          ) : null}
        </>
      ) : (
        <Text style={styles.empty}>Todavía no llegó un extracto de esta tarjeta.</Text>
      )}
    </View>
  );
}

function NextStatement({ card }: { card: CardOut }) {
  const n = card.purchases_since_cutoff.length;
  // Which purchases the installments line is made of (tap to see them).
  const [open, setOpen] = useState(false);
  const running = card.installment_plans.filter((p) => p.remaining > 0);
  return (
    <View style={styles.panel}>
      <View style={styles.panelHead}>
        <Text style={styles.panelTitle}>Próximo extracto</Text>
        <View style={[styles.chip, { backgroundColor: colors.surfaceMuted }]}>
          <Text style={[styles.chipText, { color: colors.textSecondary }]}>Estimado</Text>
        </View>
      </View>
      <MoneyText value={card.next_statement_estimate} style={styles.bigMoney} />
      <Text style={styles.sub}>
        Corte hacia el {shortDay(card.next_cutoff_date)} · se paga el {shortDay(card.next_due_date)}
      </Text>
      <View style={styles.divider} />
      <Row label={`Compras desde el corte${n ? ` (${n})` : ""}`}>
        <MoneyText value={card.purchases_since_cutoff_total} size="md" />
      </Row>
      {running.length ? (
        <>
          <Pressable
            onPress={() => setOpen((v) => !v)}
            accessibilityRole="button"
            accessibilityState={{ expanded: open }}
            style={({ pressed }) => [styles.row, pressed && { opacity: 0.7 }]}
          >
            <Text style={styles.rowLabel}>
              Cuotas de {running.length === 1 ? "1 compra diferida" : `${running.length} compras diferidas`}
            </Text>
            <MoneyText value={card.next_installments} size="md" />
            <Ionicons
              name={open ? "chevron-up" : "chevron-down"}
              size={16}
              color={colors.textSecondary}
            />
          </Pressable>
          {open
            ? running.map((p) => (
                <View key={`${p.description}-${p.purchased_on}-${p.amount}`} style={styles.subRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.subRowTitle} numberOfLines={1}>{p.description}</Text>
                    <Text style={styles.meta}>
                      Compra de {formatCOP(p.amount)} del {shortDay(p.purchased_on)} · cuota{" "}
                      {p.installment + 1} de {p.installments}
                    </Text>
                  </View>
                  <MoneyText value={p.next_amount} size="sm" style={{ color: colors.textSecondary }} />
                </View>
              ))
            : null}
        </>
      ) : (
        <Row label="Cuotas de compras diferidas">
          <MoneyText value={card.next_installments} size="md" />
        </Row>
      )}
    </View>
  );
}

function PlanRow({ plan, from }: { plan: InstallmentPlan; from: string | null }) {
  const finished = plan.remaining === 0;
  const end = endsOn(from, plan.remaining);
  return (
    <View style={styles.plan}>
      <View style={styles.planHead}>
        <View style={{ flex: 1 }}>
          <Text style={styles.planTitle} numberOfLines={1}>{plan.description}</Text>
          <Text style={styles.meta}>
            {shortDay(plan.purchased_on)} · compra de {formatCOP(plan.amount)}
          </Text>
        </View>
        <View style={{ alignItems: "flex-end" }}>
          {finished ? (
            <Text style={[styles.meta, { color: colors.success }]}>Terminada</Text>
          ) : (
            <>
              <MoneyText value={plan.next_amount} size="md" />
              <Text style={styles.meta}>por mes</Text>
            </>
          )}
        </View>
      </View>
      {/* One segment per installment: filled = already billed. */}
      <View style={styles.segments}>
        {Array.from({ length: plan.installments }, (_, i) => (
          <View
            key={i}
            style={[
              styles.segment,
              i < plan.installment && {
                backgroundColor: finished ? colors.success : colors.primary,
              },
            ]}
          />
        ))}
      </View>
      <View style={styles.planFoot}>
        <Text style={styles.planStep}>
          Cuota {plan.installment} de {plan.installments}
        </Text>
        {finished ? null : (
          <Text style={styles.meta}>
            Faltan {formatCOP(plan.pending)}
            {end ? ` · termina ${end}` : ""}
          </Text>
        )}
      </View>
    </View>
  );
}

function Installments({ card }: { card: CardOut }) {
  const plans = card.installment_plans;
  const pending = plans.reduce((s, p) => s + Number(p.pending), 0);
  return (
    <View style={styles.panel}>
      <View style={styles.panelHead}>
        <Text style={styles.panelTitle}>Compras a cuotas</Text>
        {plans.length ? (
          <Text style={styles.meta}>Por facturar {formatCOP(pending)}</Text>
        ) : null}
      </View>
      {plans.length ? (
        plans.map((p, i) => (
          <View key={`${p.description}-${p.purchased_on}-${p.amount}`}>
            {i > 0 ? <View style={styles.divider} /> : null}
            <PlanRow plan={p} from={card.statements[0]?.due_date ?? null} />
          </View>
        ))
      ) : (
        <Text style={styles.empty}>No tenés compras diferidas a cuotas.</Text>
      )}
    </View>
  );
}

function LineRow({ line }: { line: StatementLine }) {
  const amount = Number(line.amount);
  const payment = amount < 0;
  const split = (line.installments ?? 1) > 1;
  return (
    <View style={styles.line}>
      <View style={[styles.lineIcon, payment && { backgroundColor: colors.successSoft }]}>
        <Ionicons
          name={payment ? "arrow-down" : split ? "layers" : "bag-handle"}
          size={16}
          color={payment ? colors.success : colors.textSecondary}
        />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={styles.lineTitle} numberOfLines={1}>
          {payment ? "Pago a la tarjeta" : line.description}
        </Text>
        <View style={styles.lineMeta}>
          <Text style={styles.meta}>{shortDay(line.posted_on)}</Text>
          {split ? (
            <View style={styles.badge}>
              <Text style={styles.badgeText}>
                Cuota {line.installment}/{line.installments}
              </Text>
            </View>
          ) : null}
        </View>
      </View>
      <View style={{ alignItems: "flex-end" }}>
        <MoneyText value={Math.abs(amount)} size="md" positive={payment} signed={payment} />
        {split && line.billed ? (
          <Text style={styles.meta}>este mes {formatCOP(line.billed)}</Text>
        ) : null}
      </View>
    </View>
  );
}

function Movements({ card }: { card: CardOut }) {
  // null = the cycle being built (since the cut-off).
  const [statementId, setStatementId] = useState<string | null>(null);
  const selected = card.statements.find((s) => s.id === statementId) ?? null;
  const detail = useCardStatement(card.debt_id, selected ? selected.id : null);

  return (
    <View style={styles.panel}>
      <Text style={styles.panelTitle}>Movimientos</Text>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.tabs}
        contentContainerStyle={{ gap: spacing.sm }}
      >
        {[null, ...card.statements].map((s) => {
          const active = (s?.id ?? null) === (selected?.id ?? null);
          return (
            <Pressable
              key={s?.id ?? "now"}
              onPress={() => setStatementId(s?.id ?? null)}
              style={[styles.tab, active && styles.tabActive]}
            >
              <Text style={[styles.tabText, active && styles.tabTextActive]}>
                {s ? statementLabel(s) : "Desde el corte"}
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>

      {selected ? (
        <>
          <View style={styles.statementBox}>
            <Text style={styles.meta}>
              Periodo {shortDay(selected.period_start)} – {shortDay(selected.period_end)}
              {selected.due_date ? ` · pago hasta el ${shortDay(selected.due_date)}` : ""}
            </Text>
            <View style={styles.statGrid}>
              <View style={styles.stat}>
                <Text style={styles.kicker}>Compras</Text>
                <MoneyText value={selected.purchases_total} size="md" />
              </View>
              <View style={styles.stat}>
                <Text style={styles.kicker}>Pagos</Text>
                <MoneyText value={selected.payments_total} size="md" positive />
              </View>
              <View style={styles.stat}>
                <Text style={styles.kicker}>Mínimo</Text>
                <MoneyText value={selected.minimum_payment} size="md" />
              </View>
              <View style={styles.stat}>
                <Text style={styles.kicker}>Total</Text>
                <MoneyText value={selected.total_payment} size="md" />
              </View>
            </View>
          </View>
          {detail.isLoading ? (
            <ActivityIndicator color={colors.primary} style={{ marginVertical: spacing.xl }} />
          ) : detail.isError ? (
            <Text style={styles.empty}>No pudimos cargar este extracto.</Text>
          ) : (
            (detail.data?.lines ?? []).map((line) => <LineRow key={line.position} line={line} />)
          )}
        </>
      ) : card.purchases_since_cutoff.length ? (
        card.purchases_since_cutoff.map((p) => (
          <View key={p.id} style={styles.line}>
            <CategoryIcon categoryKey={p.category} size={32} />
            <View style={{ flex: 1 }}>
              <Text style={styles.lineTitle} numberOfLines={1}>{p.merchant ?? "Compra"}</Text>
              <Text style={styles.meta}>{shortDay(p.occurred_at.slice(0, 10))}</Text>
            </View>
            <MoneyText value={p.amount} size="md" />
          </View>
        ))
      ) : (
        <Text style={styles.empty}>
          Sin compras desde el corte del {shortDay(card.cutoff_date)}. Lo que compres con la tarjeta
          aparece acá y se suma al próximo extracto.
        </Text>
      )}
    </View>
  );
}

export default function CardsScreen() {
  const { data, isLoading, isError, refetch, isRefetching } = useCards();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const isWide = useIsWide();
  const cards = data ?? [];
  const card = useMemo(
    () => cards.find((c) => c.debt_id === selectedId) ?? cards[0],
    [cards, selectedId],
  );

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
        <Text style={styles.empty}>No pudimos cargar tus tarjetas.</Text>
        <Pressable style={styles.retryBtn} onPress={() => refetch()}>
          <Text style={styles.retryText}>Reintentar</Text>
        </Pressable>
      </View>
    );
  }
  if (!card) {
    return (
      <View style={styles.centered}>
        <Ionicons name="card-outline" size={44} color={colors.textSecondary} />
        <Text style={styles.emptyTitle}>Sin tarjetas vinculadas</Text>
        <Text style={[styles.empty, { textAlign: "center" }]}>
          En Deudas, abrí tu tarjeta y conectala con los correos del banco. Desde ahí se leen las
          compras, los pagos y el extracto.
        </Text>
      </View>
    );
  }

  const summary = (
    <>
      <CardVisual card={card} />
      <ToPay card={card} />
      <NextStatement card={card} />
    </>
  );
  const detail = (
    <>
      <Installments card={card} />
      {/* key: a different card starts back on "Desde el corte". */}
      <Movements key={card.debt_id} card={card} />
    </>
  );

  return (
    <ScrollView
      style={styles.root}
      contentContainerStyle={[styles.content, pageStyle]}
      refreshControl={
        <RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={colors.primary} />
      }
    >
      {cards.length > 1 ? (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={{ marginBottom: spacing.md }}
          contentContainerStyle={{ gap: spacing.sm }}
        >
          {cards.map((c) => {
            const active = c.debt_id === card.debt_id;
            return (
              <Pressable
                key={c.debt_id}
                onPress={() => setSelectedId(c.debt_id)}
                style={[styles.tab, active && styles.tabActive]}
              >
                <Text style={[styles.tabText, active && styles.tabTextActive]}>{c.name}</Text>
              </Pressable>
            );
          })}
        </ScrollView>
      ) : null}

      {isWide ? (
        <View style={styles.columns}>
          <View style={styles.colLeft}>{summary}</View>
          <View style={styles.colRight}>{detail}</View>
        </View>
      ) : (
        <>
          {summary}
          {detail}
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, paddingBottom: 48 },
  centered: {
    flex: 1,
    backgroundColor: colors.background,
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.xl,
    gap: spacing.md,
  },
  retryBtn: {
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderRadius: radius.sm,
  },
  retryText: { color: "#fff", fontWeight: "600" },
  emptyTitle: { color: colors.textPrimary, fontSize: type.title, fontWeight: "700" },
  empty: { color: colors.textSecondary, fontSize: 14, lineHeight: 20 },

  columns: { flexDirection: "row", gap: spacing.lg, alignItems: "flex-start" },
  colLeft: { flex: 5 },
  colRight: { flex: 7 },

  // The card itself.
  plastic: {
    backgroundColor: "#1B2B55",
    borderRadius: 20,
    padding: spacing.xl,
    marginBottom: spacing.lg,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.08)",
  },
  blob: { position: "absolute", borderRadius: 999 },
  blobA: { width: 260, height: 260, right: -90, top: -120, backgroundColor: "rgba(91,141,239,0.38)" },
  blobB: { width: 200, height: 200, left: -70, bottom: -110, backgroundColor: "rgba(185,140,240,0.22)" },
  plasticTop: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md,
    marginBottom: spacing.xl,
  },
  plasticName: { color: "#fff", fontSize: 18, fontWeight: "800", flex: 1 },
  plasticChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    backgroundColor: "rgba(255,255,255,0.14)",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: radius.pill,
  },
  plasticChipText: { color: "#fff", fontSize: type.label, fontWeight: "700" },
  plasticLabel: {
    color: "rgba(255,255,255,0.7)",
    fontSize: type.label,
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
  plasticMoney: { color: "#fff", fontSize: 32, marginTop: 2 },
  plasticTrack: {
    height: 6,
    borderRadius: 3,
    backgroundColor: "rgba(255,255,255,0.16)",
    overflow: "hidden",
  },
  plasticFill: { height: 6, borderRadius: 3 },
  plasticFoot: {
    flexDirection: "row",
    justifyContent: "space-between",
    flexWrap: "wrap",
    gap: spacing.xs,
    marginTop: spacing.sm,
  },
  plasticFootText: { color: "rgba(255,255,255,0.72)", fontSize: type.meta },
  plasticFootStrong: { color: "#fff", fontWeight: "700" },

  panel: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
    marginBottom: spacing.lg,
  },
  panelHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  panelTitle: { color: colors.textPrimary, fontSize: type.title, fontWeight: "700" },
  kicker: {
    color: colors.textSecondary,
    fontSize: type.label,
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
  bigMoney: { fontSize: type.hero, marginTop: 2 },
  sub: { color: colors.textSecondary, fontSize: 13, marginTop: 2 },
  meta: { color: colors.textSecondary, fontSize: type.meta },
  chip: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.pill },
  chipText: { fontSize: type.meta, fontWeight: "700" },
  divider: { height: 1, backgroundColor: colors.border, marginVertical: spacing.md },
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md,
    paddingVertical: 5,
  },
  rowLabel: { color: colors.textSecondary, fontSize: 14, flex: 1 },
  subRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingVertical: 6,
    paddingLeft: spacing.md,
    marginLeft: 2,
    borderLeftWidth: 2,
    borderLeftColor: colors.border,
  },
  subRowTitle: { color: colors.textPrimary, fontSize: 13, fontWeight: "600" },
  rowValue: { color: colors.textPrimary, fontSize: 14, fontWeight: "600" },

  barTrack: { height: 8, borderRadius: 4, backgroundColor: colors.surfaceMuted, overflow: "hidden" },
  barFill: { height: 8, borderRadius: 4 },
  barCaption: { color: colors.textSecondary, fontSize: type.meta, marginTop: 6 },

  plan: { gap: spacing.sm },
  planHead: { flexDirection: "row", alignItems: "flex-start", gap: spacing.md },
  planTitle: { color: colors.textPrimary, fontSize: type.body, fontWeight: "600" },
  segments: { flexDirection: "row", gap: 4 },
  segment: { flex: 1, height: 8, borderRadius: 4, backgroundColor: colors.surfaceMuted },
  planFoot: {
    flexDirection: "row",
    justifyContent: "space-between",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  planStep: { color: colors.textPrimary, fontSize: type.meta, fontWeight: "700" },

  tabs: { marginTop: spacing.md, marginBottom: spacing.md, flexGrow: 0 },
  tab: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceMuted,
  },
  tabActive: { backgroundColor: colors.primary },
  tabText: { color: colors.textSecondary, fontSize: 13, fontWeight: "600" },
  tabTextActive: { color: "#fff" },

  statementBox: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  statGrid: { flexDirection: "row", flexWrap: "wrap", marginTop: spacing.sm, rowGap: spacing.md },
  stat: { width: "50%", gap: 2 },

  line: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  lineIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.surfaceMuted,
    alignItems: "center",
    justifyContent: "center",
  },
  lineTitle: { color: colors.textPrimary, fontSize: type.body, fontWeight: "500" },
  lineMeta: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: 2 },
  badge: {
    backgroundColor: colors.primarySoft,
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: 6,
  },
  badgeText: { color: colors.primary, fontSize: type.label, fontWeight: "700" },
});
