const cop = new Intl.NumberFormat("es-CO", {
  style: "currency",
  currency: "COP",
  maximumFractionDigits: 0,
});

export function formatCOP(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "$0";
  const n = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(n)) return "$0";
  return cop.format(n);
}

export function parseCOP(input: string): number {
  const digits = input.replace(/[^\d]/g, "");
  return digits === "" ? 0 : Number(digits);
}

/** Live thousands separators for a money input as the user types:
 *  "1050905" → "1.050.905". Whole pesos only, so parseCOP (which drops
 *  every non-digit) reads the dots back as nothing. */
export function formatCOPInput(input: string): string {
  const digits = input.replace(/[^\d]/g, "").replace(/^0+(?=\d)/, "");
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

/** A stored amount ("402708.83") as the initial text of a money input:
 *  rounded to whole pesos — "402708.83" typed back raw would parse as
 *  40.270.883. */
export function toCOPInput(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "";
  const n = Math.round(Number(value));
  return Number.isNaN(n) ? "" : formatCOPInput(String(n));
}
