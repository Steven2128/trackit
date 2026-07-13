import { useQuery } from "@tanstack/react-query";

import { api } from "../api";

export type SubscriptionFrequency = "weekly" | "biweekly" | "monthly" | "yearly";

export type SubscriptionOut = {
  merchant: string;
  category: string | null;
  average_amount: string;
  frequency: SubscriptionFrequency;
  occurrences: number;
  last_occurred_at: string;
  next_expected_at: string;
};

export const subscriptionsQueryKey = ["subscriptions"] as const;

export function useSubscriptions(lookbackDays?: number) {
  return useQuery({
    queryKey: [...subscriptionsQueryKey, lookbackDays ?? "default"],
    queryFn: async () => {
      const res = await api.get<SubscriptionOut[]>("/subscriptions", {
        params: lookbackDays ? { lookback_days: lookbackDays } : undefined,
      });
      return res.data;
    },
  });
}
