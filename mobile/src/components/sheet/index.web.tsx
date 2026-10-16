import { Ionicons } from "@expo/vector-icons";
import { forwardRef, useEffect, useImperativeHandle, type ReactNode } from "react";
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  View,
  useWindowDimensions,
  type ScrollViewProps,
  type StyleProp,
  type TextInputProps,
  type ViewProps,
  type ViewStyle,
} from "react-native";

import { colors } from "../../theme/colors";
import { WIDE_BREAKPOINT } from "../../theme/layout";

/**
 * Browser stand-in for @gorhom/bottom-sheet, with the same exports our forms
 * use. In the browser the library mis-measures: closed sheets peeked over the
 * page, and open ones sized to their content ran past the bottom edge of
 * short windows (e.g. "Eliminar deuda" at 1024×768). Patching each case broke
 * another, so web uses a plain modal instead: a centered card on wide screens,
 * anchored to the bottom on phones, always capped to the window and
 * scrollable inside. Closes with the ✕, a backdrop click or Escape (on a
 * phone the card covers most of the screen, so the ✕ is the reliable way).
 *
 * Visibility is controlled by mounting (see useWebSheet), so the imperative
 * expand/close the forms call are no-ops here.
 */

type SheetProps = {
  children: ReactNode;
  onClose?: () => void;
  backgroundStyle?: StyleProp<ViewStyle>;
  // Accepted for parity with the native sheet and ignored: layout is
  // handled here and there is no drag gesture.
  index?: number;
  snapPoints?: (string | number)[];
  enablePanDownToClose?: boolean;
  handleIndicatorStyle?: StyleProp<ViewStyle>;
};

export type WebSheetHandle = { expand: () => void; close: () => void };

const BottomSheet = forwardRef<WebSheetHandle, SheetProps>(function WebSheet(
  { children, onClose, backgroundStyle },
  ref,
) {
  useImperativeHandle(ref, () => ({ expand: () => {}, close: () => {} }), []);
  const { width, height } = useWindowDimensions();
  const wide = width >= WIDE_BREAKPOINT;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose?.();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <Modal transparent visible animationType="fade" onRequestClose={onClose}>
      <View style={[styles.overlay, wide ? styles.overlayWide : styles.overlayNarrow]}>
        <Pressable
          style={StyleSheet.absoluteFill}
          onPress={onClose}
          accessibilityLabel="Cerrar"
        />
        <View
          style={[
            styles.card,
            backgroundStyle,
            wide
              ? [styles.cardWide, { maxHeight: height * 0.88 }]
              : [styles.cardNarrow, { maxHeight: height * 0.9 }],
          ]}
        >
          <View style={styles.handleRow}>
            <View style={styles.handle} />
            <Pressable
              onPress={onClose}
              hitSlop={10}
              accessibilityRole="button"
              accessibilityLabel="Cerrar formulario"
              style={({ pressed }) => [styles.closeBtn, pressed && { opacity: 0.6 }]}
            >
              <Ionicons name="close" size={20} color={colors.textSecondary} />
            </Pressable>
          </View>
          {children}
        </View>
      </View>
    </Modal>
  );
});

export default BottomSheet;

export function BottomSheetScrollView({ style, ...props }: ScrollViewProps) {
  return (
    <ScrollView
      keyboardShouldPersistTaps="handled"
      style={[styles.scroll, style]}
      {...props}
    />
  );
}

// Static forms scroll too: on a short window their last button would
// otherwise be clipped by the card's max height.
export function BottomSheetView({ style, children }: ViewProps) {
  return (
    <ScrollView
      keyboardShouldPersistTaps="handled"
      style={styles.scroll}
      contentContainerStyle={style}
    >
      {children}
    </ScrollView>
  );
}

export const BottomSheetTextInput = forwardRef<TextInput, TextInputProps>(
  function WebSheetTextInput(props, ref) {
    return <TextInput ref={ref} {...props} />;
  },
);

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.6)",
  },
  overlayWide: { alignItems: "center", justifyContent: "center", padding: 24 },
  overlayNarrow: { justifyContent: "flex-end" },
  card: {
    backgroundColor: colors.surface,
    overflow: "hidden",
  },
  cardWide: { width: 520, maxWidth: "100%", borderRadius: 16 },
  cardNarrow: { width: "100%", borderTopLeftRadius: 16, borderTopRightRadius: 16 },
  handleRow: { alignItems: "center", paddingTop: 8, paddingBottom: 4, minHeight: 32 },
  closeBtn: { position: "absolute", right: 10, top: 6, padding: 4 },
  handle: { width: 36, height: 4, borderRadius: 2, backgroundColor: colors.border },
  scroll: { flexGrow: 0, flexShrink: 1 },
});
