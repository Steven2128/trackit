import type { Ionicons } from "@expo/vector-icons";

type IconName = keyof typeof Ionicons.glyphMap;

export type CategoryDef = {
  key: string;
  label: string;
  icon: IconName;
  color: string;
};

// Keys must match what the backend emits: categorizer.py rules plus
// `transfer` (transfer_matcher), `cash_withdrawal` (parsers) and
// `debt_payment` (credit-card payments and the bank debit that funded them).
// Uncategorized rows arrive as null and render via FALLBACK.
export const CATEGORIES: CategoryDef[] = [
  { key: "food", label: "Comida", icon: "restaurant", color: "#F2B441" },
  { key: "transport", label: "Transporte", icon: "car", color: "#5B8DEF" },
  { key: "bills", label: "Servicios", icon: "flash", color: "#3FB67C" },
  { key: "shopping", label: "Compras", icon: "bag-handle", color: "#E88BB6" },
  { key: "health", label: "Salud", icon: "medkit", color: "#E5484D" },
  { key: "entertainment", label: "Entretenimiento", icon: "film", color: "#B98CF0" },
  { key: "subscriptions", label: "Suscripciones", icon: "repeat", color: "#5B8DEF" },
  { key: "transfer", label: "Transferencia", icon: "swap-horizontal", color: "#A3A8B3" },
  { key: "cash_withdrawal", label: "Retiro", icon: "cash", color: "#D9A053" },
  { key: "debt_payment", label: "Pago de deuda", icon: "card", color: "#E5484D" },
];

const FALLBACK: CategoryDef = { key: "other", label: "Otros", icon: "cube", color: "#A3A8B3" };

export function getCategory(key: string | null | undefined): CategoryDef {
  if (!key) return FALLBACK;
  const found = CATEGORIES.find((c) => c.key === key);
  if (found) return found;
  // User-defined category: prettify the slug ("gastos_mascota" → "Gastos mascota").
  const label = key.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
  return { key, label, icon: "pricetag", color: "#8FD0C6" };
}

// Display name → backend category slug (must satisfy ^[a-z0-9_]{1,64}$).
export function slugifyCategory(name: string): string {
  return name
    .normalize("NFKD")
    // strip combining accents left by NFKD ("á" → "a" + U+0301)
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 64);
}

// Custom category keys present in a list (e.g. budget status items) that
// aren't part of the built-in set.
export function customCategoryKeys(keys: Array<string | null | undefined>): string[] {
  const seen = new Set<string>();
  for (const key of keys) {
    if (key && !CATEGORIES.some((c) => c.key === key)) seen.add(key);
  }
  return [...seen].sort();
}
