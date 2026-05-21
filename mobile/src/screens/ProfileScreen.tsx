import { Pressable, StyleSheet, Text, View } from "react-native";

import { useAuthStore } from "../store/auth";
import { colors } from "../theme/colors";

export default function ProfileScreen() {
  const user = useAuthStore((s) => s.user);
  const clearSession = useAuthStore((s) => s.clearSession);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Profile</Text>
      {user ? (
        <>
          <Text style={styles.label}>Signed in as</Text>
          <Text style={styles.value}>{user.email}</Text>
        </>
      ) : (
        <Text style={styles.value}>No active session</Text>
      )}

      <Pressable style={styles.signOut} onPress={() => clearSession()}>
        <Text style={styles.signOutText}>Sign out</Text>
      </Pressable>
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
  title: { color: colors.textPrimary, fontSize: 28, fontWeight: "700", marginBottom: 24 },
  label: { color: colors.textSecondary, fontSize: 12, marginBottom: 4 },
  value: { color: colors.textPrimary, fontSize: 16, marginBottom: 48 },
  signOut: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 10,
    alignSelf: "flex-start",
  },
  signOutText: { color: colors.danger, fontSize: 14, fontWeight: "600" },
});
