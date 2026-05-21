import { StyleSheet, Text, View } from "react-native";

import { colors } from "../theme/colors";

export default function TransactionsScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Transactions</Text>
      <Text style={styles.subtitle}>
        Parsed bank emails will show up here as a feed.
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
