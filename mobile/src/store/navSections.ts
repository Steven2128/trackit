import { create } from "zustand";

import { storage } from "../utils/storage";

const KEY = "trackit.navCollapsed";

type NavSectionsState = {
  /** Section key → collapsed. Missing means open. */
  collapsed: Record<string, boolean>;
  toggle: (section: string) => void;
};

/** Which menu groups (sidebar and "Más") are folded; survives reloads. */
export const useNavSections = create<NavSectionsState>((set, get) => ({
  collapsed: {},
  toggle: (section) => {
    const collapsed = { ...get().collapsed, [section]: !get().collapsed[section] };
    set({ collapsed });
    storage.setItem(KEY, JSON.stringify(collapsed)).catch(() => {});
  },
}));

storage
  .getItem(KEY)
  .then((raw) => {
    if (raw) useNavSections.setState({ collapsed: JSON.parse(raw) as Record<string, boolean> });
  })
  .catch(() => {});
