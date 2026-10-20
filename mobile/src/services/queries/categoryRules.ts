import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api";
import { budgetsQueryKey } from "./budgets";
import { dashboardQueryKey } from "./dashboard";

/** "merchants containing `pattern` go to `category`" — applied to every
 *  synced email before the built-in categorizer rules. */
export type CategoryRuleOut = {
  id: string;
  pattern: string;
  category: string;
  created_at: string;
};

export const categoryRulesQueryKey = ["category-rules"] as const;

export function useCategoryRules() {
  return useQuery({
    queryKey: categoryRulesQueryKey,
    queryFn: async () => (await api.get<CategoryRuleOut[]>("/category-rules")).data,
  });
}

/** What a rule created from this merchant would match ("d1"). */
export function useRuleSuggestion(merchant: string | null | undefined) {
  return useQuery({
    queryKey: [...categoryRulesQueryKey, "suggestion", merchant],
    enabled: !!merchant,
    staleTime: Infinity,
    queryFn: async () =>
      (
        await api.get<{ pattern: string | null }>("/category-rules/suggestion", {
          params: { merchant },
        })
      ).data.pattern,
  });
}

export function useSaveCategoryRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { pattern: string; category: string; apply_to_past: boolean }) =>
      (
        await api.post<{ rule: CategoryRuleOut; updated: number }>("/category-rules", payload)
      ).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: categoryRulesQueryKey });
      // apply_to_past moves transactions: refresh everything that sums them.
      qc.invalidateQueries({ queryKey: ["transactions"] });
      qc.invalidateQueries({ queryKey: budgetsQueryKey });
      qc.invalidateQueries({ queryKey: dashboardQueryKey });
      qc.invalidateQueries({ queryKey: ["insights"] });
    },
  });
}

export function useDeleteCategoryRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/category-rules/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: categoryRulesQueryKey }),
  });
}
