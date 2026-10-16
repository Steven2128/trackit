import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StatusBar } from "expo-status-bar";
import { Platform, StyleSheet, View } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";

import RootNavigator from "./src/navigation/RootNavigator";
import { colors } from "./src/theme/colors";
import { MAX_CONTENT_WIDTH } from "./src/theme/layout";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 60_000,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  return (
    <GestureHandlerRootView style={styles.root}>
      <QueryClientProvider client={queryClient}>
        <SafeAreaProvider>
          <StatusBar style="light" />
          {/* The UI is designed for a phone: on a wide browser window keep
              it as a centered column instead of stretching edge to edge. */}
          <View style={styles.column}>
            <RootNavigator />
          </View>
        </SafeAreaProvider>
      </QueryClientProvider>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  column: {
    flex: 1,
    width: "100%",
    ...(Platform.OS === "web" ? { maxWidth: MAX_CONTENT_WIDTH, alignSelf: "center" as const } : null),
  },
});
