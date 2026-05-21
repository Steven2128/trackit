export const colors = {
  background: "#0E0F12",
  surface: "#1A1C22",
  surfaceMuted: "#23262E",
  primary: "#5B8DEF",
  primaryDim: "#3E6BC6",
  textPrimary: "#F2F3F5",
  textSecondary: "#A3A8B3",
  border: "#2A2D36",
  success: "#3FB67C",
  danger: "#E5484D",
  warning: "#F2B441",
} as const;

export type ColorName = keyof typeof colors;
