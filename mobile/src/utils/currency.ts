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
