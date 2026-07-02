import { useQuery } from "@tanstack/react-query";

import { api } from "../api";

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
