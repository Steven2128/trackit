import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api";
import { accountsQueryKey } from "./accounts";
import { budgetsQueryKey } from "./budgets";
import { dashboardQueryKey } from "./dashboard";

export type TransactionType = "debit" | "credit";

export type TransactionOut = {
  id: string;
  amount: string;
  merchant: string | null;
  category: string | null;
  transaction_type: TransactionType;
  currency: string;
  card_last_digits: string | null;
  occurred_at: string;
  note: string | null;
  debt_id: string | null;
  // Account the money moved in; "cash" = typed in by the user (editable amount).
  source: string | null;
};

export type TransactionListResponse = {
  items: TransactionOut[];
  total: number;
  limit: number;
  offset: number;
};

export type TransactionFilters = {
  // Omitted month = all time (used by a debt's movement list).
  month?: string;
  category?: string | null;
  type?: TransactionType | null;
  debtId?: string | null;
  limit?: number;
};

export const transactionsQueryKey = (filters: TransactionFilters) =>
  ["transactions", filters] as const;

export function useTransactions(filters: TransactionFilters) {
  return useQuery({
    queryKey: transactionsQueryKey(filters),
    queryFn: async () => {
      const params: Record<string, string | number> = {
        limit: filters.limit ?? 200,
      };
      if (filters.month) params.month = filters.month;
      if (filters.debtId) params.debt_id = filters.debtId;
      if (filters.category) params.category = filters.category;
      if (filters.type) params.type = filters.type;
      const res = await api.get<TransactionListResponse>("/transactions", { params });
      return res.data;
    },
  });
}

export type TransactionPatch = {
  id: string;
  category?: string | null;
  merchant?: string | null;
  note?: string | null;
  // Cash expenses only — the backend rejects it on bank rows.
  amount?: number;
};

function invalidateTransactionViews(qc: ReturnType<typeof useQueryClient>) {
  // Category and amount feed every derived view, and cash rows also move the
  // Efectivo balance in Patrimonio.
  qc.invalidateQueries({ queryKey: ["transactions"] });
  qc.invalidateQueries({ queryKey: budgetsQueryKey });
  qc.invalidateQueries({ queryKey: dashboardQueryKey });
  qc.invalidateQueries({ queryKey: ["insights"] });
  qc.invalidateQueries({ queryKey: accountsQueryKey });
}

export function useUpdateTransaction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...fields }: TransactionPatch) => {
      const res = await api.patch<TransactionOut>(`/transactions/${id}`, fields);
      return res.data;
    },
    onSuccess: () => invalidateTransactionViews(qc),
  });
}

/** Deletes a typed-in cash expense (the backend refuses bank rows). */
export function useDeleteCashTransaction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/transactions/${id}`);
    },
    onSuccess: () => invalidateTransactionViews(qc),
  });
}
