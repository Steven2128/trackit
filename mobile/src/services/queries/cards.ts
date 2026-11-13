import { useQuery } from "@tanstack/react-query";

import { api } from "../api";

/** GET /cards — each credit card (a debt linked to its emails) with the
 *  statement to pay, the one being built, purchases in installments and the
 *  saved statements (backend app/api/routes/cards.py). */
export type CardPurchase = {
  id: string;
  occurred_at: string;
  merchant: string | null;
  category: string | null;
  amount: string;
};

export type InstallmentPlan = {
  description: string;
  purchased_on: string; // YYYY-MM-DD
  amount: string;
  installment: number; // the one the last statement billed
  installments: number;
  billed: string | null;
  pending: string; // capital still to bill
  next_amount: string; // what the next statement bills
  remaining: number;
};

export type StatementSummary = {
  id: string;
  period_start: string | null;
  period_end: string; // the cut-off day
  due_date: string | null;
  minimum_payment: string | null;
  total_payment: string | null;
  purchases_total: string;
  payments_total: string;
  lines_count: number;
};

export type StatementLine = {
  position: number;
  posted_on: string;
  description: string;
  amount: string; // negative = payment
  billed: string | null;
  installment: number | null;
  installments: number | null;
  pending: string | null;
};

export type StatementDetail = StatementSummary & { lines: StatementLine[] };

export type CardOut = {
  debt_id: string;
  name: string;
  balance: string;
  credit_limit: string | null;
  available: string | null;
  minimum_payment: string | null;
  payment_due_date: string | null;
  paid_since_cutoff: string;
  cutoff_date: string | null;
  next_cutoff_date: string | null;
  next_due_date: string | null;
  purchases_since_cutoff: CardPurchase[];
  purchases_since_cutoff_total: string;
  next_installments: string;
  next_statement_estimate: string;
  installment_plans: InstallmentPlan[];
  statements: StatementSummary[];
};

export const cardsQueryKey = ["cards"] as const;

export function useCards() {
  return useQuery({
    queryKey: cardsQueryKey,
    queryFn: async () => {
      const res = await api.get<CardOut[]>("/cards");
      return res.data;
    },
  });
}

export function useCardStatement(debtId: string | undefined, statementId: string | null) {
  return useQuery({
    queryKey: [...cardsQueryKey, debtId, "statement", statementId],
    queryFn: async () => {
      const res = await api.get<StatementDetail>(`/cards/${debtId}/statements/${statementId}`);
      return res.data;
    },
    enabled: Boolean(debtId && statementId),
    // A statement never changes once issued.
    staleTime: Infinity,
  });
}
