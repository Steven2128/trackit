import type { Ionicons } from "@expo/vector-icons";

type IconName = keyof typeof Ionicons.glyphMap;

export type CategoryDef = {
  key: string;
  label: string;
  icon: IconName;
  color: string;
};

export const CATEGORIES: CategoryDef[] = [
  { key: "food", label: "Comida", icon: "restaurant", color: "#F2B441" },
  { key: "transport", label: "Transporte", icon: "car", color: "#5B8DEF" },
  { key: "grocery", label: "Mercado", icon: "cart", color: "#3FB67C" },
  { key: "health", label: "Salud", icon: "medkit", color: "#E5484D" },
  { key: "entertainment", label: "Entretenimiento", icon: "film", color: "#B98CF0" },
  { key: "subscriptions", label: "Suscripciones", icon: "repeat", color: "#5B8DEF" },
  { key: "income", label: "Ingreso", icon: "trending-up", color: "#3FB67C" },
  { key: "transfer", label: "Transferencia", icon: "swap-horizontal", color: "#A3A8B3" },
  { key: "cash_withdrawal", label: "Retiro", icon: "cash", color: "#D9A053" },
  { key: "other", label: "Otros", icon: "cube", color: "#A3A8B3" },
];

const FALLBACK: CategoryDef = { key: "other", label: "Otros", icon: "cube", color: "#A3A8B3" };

export function getCategory(key: string | null | undefined): CategoryDef {
  if (!key) return FALLBACK;
  const found = CATEGORIES.find((c) => c.key === key);
  if (found) return found;
  return { key, label: key, icon: "cube", color: "#A3A8B3" };
}
