import { useQuery } from "@tanstack/react-query";

import { api } from "../api";

export type AnomalyOut = {
  category: string;
  current: string;
  historical_avg: string;
  ratio: string;
};

export type UnusualSpendingResponse = {
  month: string;
  items: AnomalyOut[];
};

export type HealthScoreResponse = {
  total: number;
  debt: number;
  budgets: number;
  savings: number;
  anomalies: number;
};

export function useUnusualSpending() {
  return useQuery({
    queryKey: ["insights", "unusual-spending"],
    queryFn: async () => {
      const res = await api.get<UnusualSpendingResponse>("/insights/unusual-spending");
      return res.data;
    },
  });
}

export function useHealthScore() {
  return useQuery({
    queryKey: ["insights", "health-score"],
    queryFn: async () => {
      const res = await api.get<HealthScoreResponse>("/insights/health-score");
      return res.data;
    },
  });
}
