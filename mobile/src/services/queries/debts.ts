import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api";
import { dashboardQueryKey } from "./dashboard";

export type DebtOut = {
  id: string;
  bank_name: string;
  total_amount: string;
  interest_rate: string | null;
  minimum_payment: string | null;
  created_at: string;
};

export type DebtPayload = {
  bank_name: string;
  total_amount: string;
  interest_rate?: string | null;
  minimum_payment?: string | null;
};

export const debtsQueryKey = ["debts"] as const;

function invalidateAll(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: debtsQueryKey });
  qc.invalidateQueries({ queryKey: dashboardQueryKey });
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
