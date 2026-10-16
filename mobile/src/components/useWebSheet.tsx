import { useIsFocused } from "@react-navigation/native";
import { Platform } from "react-native";

/**
 * Browser visibility for our sheet forms. Native is untouched (`mounted`
 * always true; the gorhom sheet opens and closes itself via its ref).
 *
 * On web, `./sheet` is a plain modal that is visible whenever it is mounted,
 * so the form is mounted only while open — and only while its screen is
 * focused: tab scenes stay mounted on web, and a form left open on another
 * tab would otherwise cover the current one.
 *
 * Usage: `if (!sheet.mounted) return null;` and spread `sheet.props` last on
 * the sheet (empty today; kept so call sites don't change if web needs
 * per-sheet props again).
 */
export function useWebSheet(open: boolean): { mounted: boolean; props: Record<string, never> } {
  const isFocused = useIsFocused();
  if (Platform.OS !== "web") return { mounted: true, props: {} };
  return { mounted: open && isFocused, props: {} };
}
