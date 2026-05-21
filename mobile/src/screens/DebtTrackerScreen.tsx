import { StyleSheet, Text, View } from "react-native";

import { colors } from "../theme/colors";

export default function DebtTrackerScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Debt Tracker</Text>
      <Text style={styles.subtitle}>
        Track outstanding balances, minimum payments and interest rates.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    padding: 24,
    justifyContent: "center",
  },
  title: { color: colors.textPrimary, fontSize: 28, fontWeight: "700", marginBottom: 12 },
  subtitle: { color: colors.textSecondary, fontSize: 14 },
});
