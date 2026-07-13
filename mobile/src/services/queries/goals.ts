import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api";

export type SavingsGoalOut = {
  id: string;
  name: string;
  target_amount: string;
  current_amount: string;
  target_date: string | null;
  created_at: string;
  pct: number;
};

export type SavingsGoalPayload = {
  name: string;
  target_amount: string;
  current_amount?: string;
  target_date?: string | null;
};

export const goalsQueryKey = ["goals"] as const;

export function useGoals() {
  return useQuery({
    queryKey: goalsQueryKey,
    queryFn: async () => {
      const res = await api.get<SavingsGoalOut[]>("/goals");
      return res.data;
    },
  });
}

export function useCreateGoal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: SavingsGoalPayload) => {
      const res = await api.post<SavingsGoalOut>("/goals", payload);
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: goalsQueryKey }),
  });
}

export function useUpdateGoal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, payload }: { id: string; payload: Partial<SavingsGoalPayload> }) => {
      const res = await api.patch<SavingsGoalOut>(`/goals/${id}`, payload);
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: goalsQueryKey }),
  });
}

export function useDeleteGoal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/goals/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: goalsQueryKey }),
  });
}
