import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";

import GmailConnectCard from "../components/GmailConnectCard";
import { useAuthStore } from "../store/auth";
import { colors } from "../theme/colors";

export default function ProfileScreen() {
  const user = useAuthStore((s) => s.user);
  const clearSession = useAuthStore((s) => s.clearSession);

  return (
    <View style={styles.container}>
      <View style={styles.accountCard}>
        <View style={styles.avatar}>
          <Ionicons name="person" size={22} color={colors.primary} />
        </View>
        <View style={styles.accountBody}>
          <Text style={styles.accountName} numberOfLines={1}>
            {user?.name ?? "Sin sesión"}
          </Text>
          <Text style={styles.accountEmail} numberOfLines={1}>
            {user?.email ?? "—"}
          </Text>
        </View>
      </View>

      <GmailConnectCard />

      <Pressable
        style={({ pressed }) => [styles.signOut, pressed && styles.pressed]}
        onPress={() => clearSession()}
      >
        <Ionicons name="log-out-outline" size={18} color={colors.danger} />
        <Text style={styles.signOutText}>Cerrar sesión</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    padding: 16,
  },
  accountCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 16,
    marginBottom: 16,
    gap: 12,
  },
  avatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: `${colors.primary}26`,
    alignItems: "center",
    justifyContent: "center",
  },
  accountBody: { flex: 1 },
  accountName: { color: colors.textPrimary, fontSize: 16, fontWeight: "700" },
  accountEmail: { color: colors.textSecondary, fontSize: 13, marginTop: 2 },
  signOut: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    paddingVertical: 14,
    borderRadius: 10,
    marginTop: "auto",
  },
  pressed: { opacity: 0.7 },
  signOutText: { color: colors.danger, fontSize: 14, fontWeight: "600" },
});
