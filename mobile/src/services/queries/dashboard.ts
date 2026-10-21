import { useQuery } from "@tanstack/react-query";

import { api } from "../api";

export type MonthCategoryItem = {
  category: string | null;
  total: string;
  count: number;
};

export type MonthTrendEntry = {
  month: string;
  total_spent: string;
  total_received: string; // credits minus own transfers and card payments
  by_category: MonthCategoryItem[];
};

export type CurrentMonthSnapshot = {
  month: string;
  total_spent: string;
  total_received: string;
  by_category: MonthCategoryItem[];
  transaction_count: number;
};

export type DebtSnapshot = {
  total_debt: string;
  total_minimum_payment: string;
  debt_count: number;
};

export type DashboardResponse = {
  monthly_trend: MonthTrendEntry[];
  current_month: CurrentMonthSnapshot;
  debts: DebtSnapshot;
};

export const dashboardQueryKey = ["dashboard"] as const;

export function useDashboard() {
  return useQuery({
    queryKey: dashboardQueryKey,
    queryFn: async () => {
      const res = await api.get<DashboardResponse>("/dashboard");
      return res.data;
    },
  });
}
