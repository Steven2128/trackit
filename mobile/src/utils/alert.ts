import { Alert as NativeAlert, AlertButton, Platform } from "react-native";

/**
 * Drop-in for react-native's `Alert`, whose web implementation is a no-op.
 * On web: no buttons / one button → `window.alert`; a cancel + action pair →
 * `window.confirm`, running the first non-cancel button on OK.
 */
function alert(title: string, message?: string, buttons?: AlertButton[]): void {
  if (Platform.OS !== "web") {
    NativeAlert.alert(title, message, buttons);
    return;
  }

  const text = message ? `${title}\n\n${message}` : title;
  const actions = (buttons ?? []).filter((b) => b.style !== "cancel");
  const cancel = (buttons ?? []).find((b) => b.style === "cancel");

  if (!buttons || buttons.length <= 1) {
    window.alert(text);
    buttons?.[0]?.onPress?.();
    return;
  }

  if (window.confirm(text)) {
    actions[0]?.onPress?.();
  } else {
    cancel?.onPress?.();
  }
}

export const Alert = { alert };
