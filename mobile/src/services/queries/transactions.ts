import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api";
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
};

export type TransactionListResponse = {
  items: TransactionOut[];
  total: number;
  limit: number;
  offset: number;
};

export type TransactionFilters = {
  month: string;
  category?: string | null;
  type?: TransactionType | null;
  limit?: number;
};

export const transactionsQueryKey = (filters: TransactionFilters) =>
  ["transactions", filters] as const;

export function useTransactions(filters: TransactionFilters) {
  return useQuery({
    queryKey: transactionsQueryKey(filters),
    queryFn: async () => {
      const params: Record<string, string | number> = {
        month: filters.month,
        limit: filters.limit ?? 200,
      };
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
};

export function useUpdateTransaction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...fields }: TransactionPatch) => {
      const res = await api.patch<TransactionOut>(`/transactions/${id}`, fields);
      return res.data;
    },
    onSuccess: () => {
      // Recategorizing moves spending between categories — everything
      // derived from transaction categories must refetch.
      qc.invalidateQueries({ queryKey: ["transactions"] });
      qc.invalidateQueries({ queryKey: budgetsQueryKey });
      qc.invalidateQueries({ queryKey: dashboardQueryKey });
      qc.invalidateQueries({ queryKey: ["insights"] });
    },
  });
}
