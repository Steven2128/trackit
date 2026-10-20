const MESES = [
  "ene", "feb", "mar", "abr", "may", "jun",
  "jul", "ago", "sep", "oct", "nov", "dic",
];

function ymdLocal(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function formatDayHeader(iso: string): string {
  const d = new Date(iso);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);

  const key = ymdLocal(d);
  if (key === ymdLocal(today)) return "Hoy";
  if (key === ymdLocal(yesterday)) return "Ayer";
  return `${d.getDate()} ${MESES[d.getMonth()]}`;
}

export function dayKey(iso: string): string {
  return ymdLocal(new Date(iso));
}

export function currentMonthYYYYMM(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  return `${y}-${m}`;
}

export function shiftMonth(yyyymm: string, delta: number): string {
  const [y, m] = yyyymm.split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  const ny = d.getFullYear();
  const nm = String(d.getMonth() + 1).padStart(2, "0");
  return `${ny}-${nm}`;
}

export function humanizeMonth(yyyymm: string): string {
  const [y, m] = yyyymm.split("-").map(Number);
  const label = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"][m - 1];
  return `${label} ${y}`;
}

const DIAS = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];

/** Whole local days between `iso` and today (0 = today, 1 = yesterday). */
export function daysAgo(iso: string): number {
  const d = new Date(iso);
  const then = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((today.getTime() - then.getTime()) / 86_400_000);
}

/** When a typed-in expense happened, `ago` local days back. Today is "now";
 *  past days use noon — the hour doesn't matter and noon can't slip into
 *  the neighbouring day. */
export function expenseInstant(ago: number): string {
  const now = new Date();
  if (ago <= 0) return now.toISOString();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate() - ago, 12).toISOString();
}

/** "lun 13 oct" */
export function formatShortDay(iso: string): string {
  const d = new Date(iso);
  return `${DIAS[d.getDay()]} ${d.getDate()} ${MESES[d.getMonth()]}`;
}
