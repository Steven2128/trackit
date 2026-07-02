export type CategoryDef = { key: string; label: string; emoji: string };

export const CATEGORIES: CategoryDef[] = [
  { key: "food", label: "Comida", emoji: "🍽" },
  { key: "transport", label: "Transporte", emoji: "🚗" },
  { key: "grocery", label: "Mercado", emoji: "🛒" },
  { key: "health", label: "Salud", emoji: "🏥" },
  { key: "entertainment", label: "Entretenimiento", emoji: "🎬" },
  { key: "income", label: "Ingreso", emoji: "💰" },
  { key: "transfer", label: "Transferencia", emoji: "↔" },
  { key: "cash_withdrawal", label: "Retiro", emoji: "💵" },
  { key: "other", label: "Otros", emoji: "📦" },
];

const FALLBACK: CategoryDef = { key: "other", label: "Otros", emoji: "📦" };

export function getCategory(key: string | null | undefined): CategoryDef {
  if (!key) return FALLBACK;
  const found = CATEGORIES.find((c) => c.key === key);
  if (found) return found;
  return { key, label: key, emoji: "📦" };
}
