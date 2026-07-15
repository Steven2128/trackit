import { NavigationContainer } from "@react-navigation/native";
import { useEffect } from "react";

import SplashScreen from "../screens/SplashScreen";
import { registerForPushNotifications } from "../services/notifications";
import { useAuthStore } from "../store/auth";
import AppStack from "./AppStack";
import AuthStack from "./AuthStack";

export default function RootNavigator() {
  const hydrated = useAuthStore((s) => s.hydrated);
  const accessToken = useAuthStore((s) => s.accessToken);
  const hydrate = useAuthStore((s) => s.hydrate);

  useEffect(() => {
    if (!hydrated) {
      hydrate();
    }
  }, [hydrated, hydrate]);

  useEffect(() => {
    if (accessToken) {
      registerForPushNotifications();
    }
  }, [accessToken]);

  if (!hydrated) {
    return <SplashScreen />;
  }

  return (
    <NavigationContainer>
      {accessToken ? <AppStack /> : <AuthStack />}
    </NavigationContainer>
  );
}
