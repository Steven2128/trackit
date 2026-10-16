import { BottomSheetBackdrop, type BottomSheetBackdropProps } from "@gorhom/bottom-sheet";
import { BottomTabBarHeightContext } from "@react-navigation/bottom-tabs";
import { useIsFocused } from "@react-navigation/native";
import { useCallback, useContext, useEffect, useState } from "react";
import { Platform, useWindowDimensions, type ViewStyle } from "react-native";

import { SIDEBAR_WIDTH, WIDE_BREAKPOINT } from "../theme/layout";

const SHEET_WIDTH = 520;

type SheetProps = {
  index?: number;
  onChange?: (index: number) => void;
  detached?: boolean;
  bottomInset?: number;
  style?: ViewStyle;
  backdropComponent?: (props: BottomSheetBackdropProps) => React.ReactElement;
};

/**
 * Browser behaviour for our `@gorhom/bottom-sheet` forms. Native is untouched
 * (`mounted` always true, no extra props).
 *
 * On web a closed sheet (index -1) mis-measures its hidden position when its
 * tab becomes visible and peeks over the page, so there the sheet is only
 * mounted while open: it mounts at index 0 and unmounts once the close
 * animation ends, and only while its screen is focused — tab scenes stay
 * mounted on web, so a sheet left open on another tab would otherwise float
 * over the current one. It also gets a dimmed backdrop (click outside closes) and,
 * on wide screens, floats as a centered card instead of spanning the page.
 *
 * Usage: `if (!sheet.mounted) return null;` then spread `sheet.props` last on
 * `<BottomSheet>` so `index` overrides the `-1` used on native.
 */
export function useWebSheet(open: boolean): { mounted: boolean; props: SheetProps } {
  const isWeb = Platform.OS === "web";
  const { width } = useWindowDimensions();
  const [mounted, setMounted] = useState(open);
  const isFocused = useIsFocused();
  // Bottom tab bar height on phone-width tab screens; undefined elsewhere.
  const tabBarHeight = useContext(BottomTabBarHeightContext) ?? 0;

  useEffect(() => {
    if (open) setMounted(true);
  }, [open]);

  const onChange = useCallback((index: number) => {
    if (index === -1) setMounted(false);
  }, []);

  const backdropComponent = useCallback(
    (props: BottomSheetBackdropProps) => (
      <BottomSheetBackdrop
        {...props}
        appearsOnIndex={0}
        disappearsOnIndex={-1}
        opacity={0.6}
        pressBehavior="close"
      />
    ),
    [],
  );

  if (!isWeb) return { mounted: true, props: {} };

  const props: SheetProps = { index: 0, onChange, backdropComponent };
  if (width >= WIDE_BREAKPOINT) {
    const margin = Math.max(16, (width - SIDEBAR_WIDTH - SHEET_WIDTH) / 2);
    Object.assign(props, { detached: true, bottomInset: 24, style: { marginHorizontal: margin } });
  } else if (tabBarHeight > 0) {
    // The browser lays the sheet out over the whole scene, so without this
    // its bottom (Guardar / Eliminar) ends up hidden behind the tab bar.
    Object.assign(props, { detached: true, bottomInset: tabBarHeight });
  }
  return { mounted: (mounted || open) && isFocused, props };
}
