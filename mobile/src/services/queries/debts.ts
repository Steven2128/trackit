import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api";
import { dashboardQueryKey } from "./dashboard";

export type DebtOut = {
  id: string;
  bank_name: string;
  total_amount: string;
  interest_rate: string | null;
  minimum_payment: string | null;
  // Credit-card email link (purchases/payments move total_amount).
  email_sender: string | null;
  email_format: string | null;
  card_last_digits: string | null;
  payment_due_date: string | null;
  email_linked_at: string | null;
  created_at: string;
};

export type DebtPayload = {
  bank_name: string;
  total_amount: string;
  interest_rate?: string | null;
  minimum_payment?: string | null;
  email_sender?: string | null;
  email_format?: string | null;
  card_last_digits?: string | null;
};

export type CardFormatOut = {
  key: string;
  label: string;
  default_sender: string | null;
};

export type DebtPayoffOut = {
  name: string;
  payoff_month: number | null;
  interest_paid: string;
};

export type StrategyResultOut = {
  strategy: "avalanche" | "snowball";
  months_to_free: number | null;
  total_interest: string;
  total_paid: string;
  payoff_order: string[];
  per_debt: DebtPayoffOut[];
  converges: boolean;
};

export type StrategyComparisonOut = {
  avalanche: StrategyResultOut;
  snowball: StrategyResultOut;
  interest_saved_by_avalanche: string;
  months_saved_by_avalanche: number | null;
  recommended: "avalanche" | "snowball";
};

export const debtsQueryKey = ["debts"] as const;

function invalidateAll(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: debtsQueryKey });
  qc.invalidateQueries({ queryKey: dashboardQueryKey });
  // Net worth subtracts debt balances.
  qc.invalidateQueries({ queryKey: ["accounts"] });
}

export function useDebts() {
  return useQuery({
    queryKey: debtsQueryKey,
    queryFn: async () => {
      const res = await api.get<DebtOut[]>("/debts");
      return res.data;
    },
  });
}

export function useCardFormats() {
  return useQuery({
    queryKey: [...debtsQueryKey, "card-formats"],
    queryFn: async () => {
      const res = await api.get<CardFormatOut[]>("/debts/card-formats");
      return res.data;
    },
    staleTime: Infinity,
  });
}

export function useDebtStrategy(extraMonthly: number, enabled: boolean) {
  return useQuery({
    queryKey: [...debtsQueryKey, "strategy", extraMonthly],
    queryFn: async () => {
      const res = await api.get<StrategyComparisonOut>("/debts/strategy", {
        params: { extra_monthly: extraMonthly },
      });
      return res.data;
    },
    enabled,
  });
}

export function useCreateDebt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: DebtPayload) => {
      const res = await api.post<DebtOut>("/debts", payload);
      return res.data;
    },
    onSuccess: () => invalidateAll(qc),
  });
}

export function useUpdateDebt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, payload }: { id: string; payload: Partial<DebtPayload> }) => {
      const res = await api.patch<DebtOut>(`/debts/${id}`, payload);
      return res.data;
    },
    onSuccess: () => invalidateAll(qc),
  });
}

export function useDeleteDebt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/debts/${id}`);
    },
    onSuccess: () => invalidateAll(qc),
  });
}
