import { useWindowDimensions, type ViewStyle } from "react-native";

// Phone-first UI that reflows on wide screens (browser, tablet landscape):
// sidebar instead of bottom tabs, centered page, multi-column grids and
// floating sheets. Below the breakpoint everything stays as on the phone.
export const WIDE_BREAKPOINT = 900;
export const SIDEBAR_WIDTH = 232;
export const PAGE_MAX_WIDTH = 1180;

export function useIsWide(): boolean {
  const { width } = useWindowDimensions();
  return width >= WIDE_BREAKPOINT;
}

/** Scroll content wrapper: no-op on phones, centered column on wide screens. */
export const pageStyle: ViewStyle = {
  width: "100%",
  maxWidth: PAGE_MAX_WIDTH,
  alignSelf: "center",
};
