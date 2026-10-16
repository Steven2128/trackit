import { useQuery } from "@tanstack/react-query";

import { api } from "../api";

export type GmailStatus = {
  connected: boolean;
  email: string | null;
  last_sync_at: string | null;
};

export const gmailStatusQueryKey = ["gmail", "status"] as const;

export function useGmailStatus() {
  return useQuery({
    queryKey: gmailStatusQueryKey,
    queryFn: async () => (await api.get<GmailStatus>("/gmail/status")).data,
  });
}
