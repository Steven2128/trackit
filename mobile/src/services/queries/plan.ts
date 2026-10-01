import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api";

export type IncomeSourceOut = {
  id: string;
  name: string;
  amount: string;
  expected_day: number;
  created_at: string;
};

export type IncomeSourcePayload = {
  name: string;
  amount: string;
  expected_day: number;
};

export type PlannedPaymentOut = {
  id: string;
  name: string;
  amount: string;
  due_day: number | null;
  grace_days: number;
  is_debt_payment: boolean;
  paid_month: string | null;
  created_at: string;
};

export type PlannedPaymentPayload = {
  name: string;
  amount: string;
  due_day?: number | null;
  grace_days?: number;
  is_debt_payment?: boolean;
};

export type UpcomingPaymentOut = {
  id: string | null;
  name: string;
  amount: string;
  deadline: string | null;
  days_left: number | null;
  is_debt_payment: boolean;
  is_paid: boolean;
};

export type CashFlowResponse = {
  monthly_income: string;
  monthly_committed: string;
  available: string;
  next_income_date: string | null;
  next_income_name: string | null;
  next_income_amount: string | null;
  upcoming: UpcomingPaymentOut[];
  checklist: UpcomingPaymentOut[];
};

export const planQueryKey = ["plan"] as const;

function invalidatePlan(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: planQueryKey });
}

export function useCashFlow() {
  return useQuery({
    queryKey: [...planQueryKey, "cashflow"],
    queryFn: async () => {
      const res = await api.get<CashFlowResponse>("/cashflow");
      return res.data;
    },
  });
}

export function useIncomeSources() {
  return useQuery({
    queryKey: [...planQueryKey, "incomes"],
    queryFn: async () => {
      const res = await api.get<IncomeSourceOut[]>("/income-sources");
      return res.data;
    },
  });
}

export function useCreateIncomeSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: IncomeSourcePayload) => {
      const res = await api.post<IncomeSourceOut>("/income-sources", payload);
      return res.data;
    },
    onSuccess: () => invalidatePlan(qc),
  });
}

export function useUpdateIncomeSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, payload }: { id: string; payload: Partial<IncomeSourcePayload> }) => {
      const res = await api.patch<IncomeSourceOut>(`/income-sources/${id}`, payload);
      return res.data;
    },
    onSuccess: () => invalidatePlan(qc),
  });
}

export function useDeleteIncomeSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/income-sources/${id}`);
    },
    onSuccess: () => invalidatePlan(qc),
  });
}

export function usePlannedPayments() {
  return useQuery({
    queryKey: [...planQueryKey, "payments"],
    queryFn: async () => {
      const res = await api.get<PlannedPaymentOut[]>("/planned-payments");
      return res.data;
    },
  });
}

export function useCreatePlannedPayment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: PlannedPaymentPayload) => {
      const res = await api.post<PlannedPaymentOut>("/planned-payments", payload);
      return res.data;
    },
    onSuccess: () => invalidatePlan(qc),
  });
}

export function useUpdatePlannedPayment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, payload }: { id: string; payload: Partial<PlannedPaymentPayload> }) => {
      const res = await api.patch<PlannedPaymentOut>(`/planned-payments/${id}`, payload);
      return res.data;
    },
    onSuccess: () => invalidatePlan(qc),
  });
}

// Check/un-check a commitment for the current local month. paid_month is
// month-scoped on the backend, so checks reset themselves on month change.
export function useTogglePaymentPaid() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, paidMonth }: { id: string; paidMonth: string | null }) => {
      const res = await api.patch<PlannedPaymentOut>(`/planned-payments/${id}`, {
        paid_month: paidMonth,
      });
      return res.data;
    },
    onSuccess: () => invalidatePlan(qc),
  });
}

export function useDeletePlannedPayment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/planned-payments/${id}`);
    },
    onSuccess: () => invalidatePlan(qc),
  });
}
