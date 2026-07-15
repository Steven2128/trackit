import Constants from "expo-constants";
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";

import { api } from "./api";

// Foreground behavior: show the banner even with the app open — a budget
// alert that lands while the user is browsing should still be visible.
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

/**
 * Ask permission, fetch the Expo push token and register it with the
 * backend. Safe to call on every login/app start — the backend upserts.
 *
 * In Expo Go (SDK 53+) remote push is unsupported and `getExpoPushTokenAsync`
 * throws — we swallow that so dev sessions keep working; a development build
 * or production app registers normally.
 */
export async function registerForPushNotifications(): Promise<void> {
  try {
    if (Platform.OS === "android") {
      await Notifications.setNotificationChannelAsync("default", {
        name: "Alertas TrackIt",
        importance: Notifications.AndroidImportance.DEFAULT,
      });
    }

    const existing = await Notifications.getPermissionsAsync();
    let status = existing.status;
    if (status !== "granted") {
      status = (await Notifications.requestPermissionsAsync()).status;
    }
    if (status !== "granted") return;

    const projectId =
      Constants.expoConfig?.extra?.eas?.projectId ?? Constants.easConfig?.projectId;
    const { data: token } = await Notifications.getExpoPushTokenAsync(
      projectId ? { projectId } : undefined,
    );

    await api.post("/notifications/token", { token, platform: Platform.OS });
  } catch (err) {
    // Expo Go without push support, permission dialogs dismissed, offline —
    // none of these should break the session.
    console.warn("push token registration skipped:", err);
  }
}
