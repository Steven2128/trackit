import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api";
import { budgetsQueryKey } from "./budgets";
import { dashboardQueryKey } from "./dashboard";

export type AccountKind = "davivienda" | "nequi" | "cash";

export type AccountOut = {
  id: string;
  kind: AccountKind;
  name: string;
  opening_balance: string;
  opening_at: string;
  balance: string;
  last_reconciled_at: string | null;
  unexplained_this_month: string;
};

export type NetWorthOut = {
  accounts: AccountOut[];
  total_assets: string;
  total_debt: string;
  net_worth: string;
  unexplained_this_month: string;
};

export type ReconcileOut = {
  computed_balance: string;
  reported_balance: string;
  difference: string;
};

export type CashExpensePayload = {
  amount: string;
  merchant: string;
  category: string | null;
  // ISO instant; omitted = now.
  occurred_at?: string;
};

export const accountsQueryKey = ["accounts"] as const;

function invalidateMoney(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: accountsQueryKey });
  qc.invalidateQueries({ queryKey: ["transactions"] });
  qc.invalidateQueries({ queryKey: budgetsQueryKey });
  qc.invalidateQueries({ queryKey: dashboardQueryKey });
}

export function useNetWorth() {
  return useQuery({
    queryKey: accountsQueryKey,
    queryFn: async () => {
      const res = await api.get<NetWorthOut>("/accounts");
      return res.data;
    },
  });
}

// Creates the account, or restarts it from today's real balance.
export function useUpsertAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ kind, openingBalance }: { kind: AccountKind; openingBalance: number }) => {
      await api.put(`/accounts/${kind}`, { opening_balance: openingBalance.toString() });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: accountsQueryKey }),
  });
}

export function useReconcileAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ kind, balance }: { kind: AccountKind; balance: number }) => {
      const res = await api.post<ReconcileOut>(`/accounts/${kind}/reconcile`, {
        balance: balance.toString(),
      });
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: accountsQueryKey }),
  });
}

export function useCreateCashExpense() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: CashExpensePayload) => {
      await api.post("/transactions/cash", payload);
    },
    onSuccess: () => invalidateMoney(qc),
  });
}

/** Money in your accounts that isn't yours to spend (GET /fund-holds). */
export type FundHoldOut = { id: string; name: string; amount: string; created_at: string };

export const fundHoldsQueryKey = ["fund-holds"] as const;

function invalidateHolds(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: fundHoldsQueryKey });
  qc.invalidateQueries({ queryKey: ["cash-position"] });
}

export function useFundHolds() {
  return useQuery({
    queryKey: fundHoldsQueryKey,
    queryFn: async () => (await api.get<FundHoldOut[]>("/fund-holds")).data,
  });
}

export function useCreateFundHold() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { name: string; amount: string }) => {
      await api.post("/fund-holds", payload);
    },
    onSuccess: () => invalidateHolds(qc),
  });
}

export function useDeleteFundHold() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/fund-holds/${id}`);
    },
    onSuccess: () => invalidateHolds(qc),
  });
}
