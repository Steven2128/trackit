import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api";

/** Someone the user shares expenses or lends money with (GET /contacts). */
export type ContactOut = { id: string; name: string; created_at: string };

export const contactsQueryKey = ["contacts"] as const;

export function useContacts() {
  return useQuery({
    queryKey: contactsQueryKey,
    queryFn: async () => (await api.get<ContactOut[]>("/contacts")).data,
  });
}

export function useCreateContact() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (name: string) =>
      (await api.post<ContactOut>("/contacts", { name })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: contactsQueryKey });
      // The shared card lists every contact with its balance.
      qc.invalidateQueries({ queryKey: ["transactions", "shared"] });
    },
  });
}
