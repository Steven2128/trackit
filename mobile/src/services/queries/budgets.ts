import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api";

export type BudgetOut = {
  id: string;
  category: string;
  monthly_limit: string;
  created_at: string;
};

export type BudgetAlertStatus = "ok" | "warning" | "exceeded";

export type BudgetStatusItem = {
  category: string;
  monthly_limit: string;
  spent: string;
  pct: string;
  status: BudgetAlertStatus;
};

export type BudgetStatusResponse = {
  month: string;
  items: BudgetStatusItem[];
};

export const budgetsQueryKey = ["budgets"] as const;

function invalidateBudgets(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: budgetsQueryKey });
}

export function useBudgetStatus(month?: string) {
  return useQuery({
    queryKey: [...budgetsQueryKey, "status", month ?? "current"],
    queryFn: async () => {
      const res = await api.get<BudgetStatusResponse>("/budgets/status", {
        params: month ? { month } : undefined,
      });
      return res.data;
    },
  });
}

export function useUpsertBudget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ category, monthly_limit }: { category: string; monthly_limit: string }) => {
      const res = await api.put<BudgetOut>(`/budgets/${category}`, { monthly_limit });
      return res.data;
    },
    onSuccess: () => invalidateBudgets(qc),
  });
}

export function useDeleteBudget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (category: string) => {
      await api.delete(`/budgets/${category}`);
    },
    onSuccess: () => invalidateBudgets(qc),
  });
}
