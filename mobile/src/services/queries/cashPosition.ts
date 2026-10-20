import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api";
import { accountsQueryKey } from "./accounts";
import { budgetsQueryKey } from "./budgets";
import { dashboardQueryKey } from "./dashboard";

/** GET /cashflow/position — how much of today's money is really free,
 *  window by window until the payday after next (backend
 *  services/cash_position.py). */
export type PositionStatus = "confirmed" | "provisional" | "indeterminate";

export type PositionLine = {
  name: string;
  amount: string; // still owed
  estimated: boolean;
  due: string | null; // YYYY-MM-DD
  total: string; // what the due date asks for; paid = total − amount
  ref: string | null; // "planned:<id>:<due>" | "debt:<id>:<due>"
};

export type PositionWindow = {
  start: string;
  end: string | null;
  income: string;
  income_names: string[];
  obligations: PositionLine[];
  essentials: string;
  balance_after: string;
};

export type CashPosition = {
  status: PositionStatus;
  today: string;
  horizon_end: string;
  pay_due_on_payday: boolean;
  balance: string;
  held_for_others: string;
  own: string;
  due_before_next_income: string;
  essentials_until_next_income: string;
  reserve_for_later: string;
  free: string;
  spendable_now: string;
  windows: PositionWindow[];
  deficit: { window_start: string; amount: string; obligations: string[] } | null;
  missing: string[];
  estimated: string[];
  late_incomes: string[];
  overdue: string[];
  no_plan: string[];
  notes: string[];
};

export const cashPositionQueryKey = ["cash-position"] as const;

export function useCashPosition() {
  return useQuery({
    queryKey: cashPositionQueryKey,
    queryFn: async () => (await api.get<CashPosition>("/cashflow/position")).data,
  });
}

/** What a line's ref points at, or null when it can't be paid from here
 *  (no due date yet). */
export function parseRef(
  ref: string | null,
): { kind: "planned" | "debt"; id: string; due: string } | null {
  if (!ref) return null;
  const [kind, id, due] = ref.split(":");
  if ((kind !== "planned" && kind !== "debt") || !id || !due) return null;
  return { kind, id, due };
}

export type ObligationPaymentPayload = {
  planned_payment_id?: string;
  debt_id?: string;
  due_date: string;
  amount: string;
  paid_on?: string;
  from_cash: boolean;
};

export function useRecordObligationPayment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: ObligationPaymentPayload) => {
      await api.post("/obligation-payments", payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: cashPositionQueryKey });
      // Paid in cash logs a cash expense: balances and lists move too.
      qc.invalidateQueries({ queryKey: accountsQueryKey });
      qc.invalidateQueries({ queryKey: ["transactions"] });
      qc.invalidateQueries({ queryKey: budgetsQueryKey });
      qc.invalidateQueries({ queryKey: dashboardQueryKey });
    },
  });
}

/** API names repeat the due date ("Arriendo (24/10)"); screens show it apart. */
export function plainName(name: string): string {
  return name.replace(/\s*\(\d{1,2}\/\d{1,2}\)$/, "");
}
