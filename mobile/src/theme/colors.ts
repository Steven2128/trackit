export const colors = {
  background: "#0E0F12",
  surface: "#1A1C22",
  surfaceMuted: "#23262E",
  primary: "#5B8DEF",
  primaryDim: "#3E6BC6",
  primarySoft: "rgba(91, 141, 239, 0.14)",
  textPrimary: "#F2F3F5",
  textSecondary: "#A3A8B3",
  border: "#2A2D36",
  success: "#3FB67C",
  successSoft: "rgba(63, 182, 124, 0.14)",
  danger: "#E5484D",
  dangerSoft: "rgba(229, 72, 77, 0.14)",
  warning: "#F2B441",
  warningSoft: "rgba(242, 180, 65, 0.14)",
} as const;

export type ColorName = keyof typeof colors;

// 4pt spacing rhythm — use these instead of magic numbers.
export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
} as const;

export const radius = {
  sm: 8,
  md: 12,
  lg: 16,
  pill: 999,
} as const;

// Type scale — nothing below 11px; body text at 15 for mobile readability.
export const type = {
  label: 11, // uppercase section labels
  meta: 12, // secondary metadata under titles
  body: 15, // primary row text
  title: 17, // screen-level titles
  hero: 28, // big money numbers
} as const;
