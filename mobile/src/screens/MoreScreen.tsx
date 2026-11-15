import { Ionicons } from "@expo/vector-icons";
import type { BottomTabNavigationProp } from "@react-navigation/bottom-tabs";
import { useNavigation } from "@react-navigation/native";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import type { AppTabParamList } from "../navigation/AppStack";
import { colors } from "../theme/colors";
import { pageStyle } from "../theme/layout";

type IconName = keyof typeof Ionicons.glyphMap;
type Target =
  "Subscriptions" | "Cards" | "Plan" | "Goals" | "NetWorth" | "Profile";

const SECTIONS: {
  key: string;
  title: string;
  items: { to: Target; label: string; hint: string; icon: IconName }[];
}[] = [
  {
    key: "main",
    title: "Tu plata",
    items: [
      {
        to: "Cards",
        label: "Tarjetas",
        hint: "Extractos, compras y cuotas",
        icon: "card-outline",
      },
      {
        to: "Subscriptions",
        label: "Suscripciones",
        hint: "Cobros que se repiten",
        icon: "repeat-outline",
      },
    ],
  },
  {
    key: "planning",
    title: "Planificación",
    items: [
      {
        to: "Plan",
        label: "Plan del mes",
        hint: "Ingresos y pagos por quincena",
        icon: "map-outline",
      },
      {
        to: "Goals",
        label: "Metas de ahorro",
        hint: "Cuánto apartar para llegar",
        icon: "flag-outline",
      },
      {
        to: "NetWorth",
        label: "Patrimonio",
        hint: "Cuentas, efectivo y deudas",
        icon: "wallet-outline",
      },
    ],
  },
  {
    key: "account",
    title: "Cuenta",
    items: [
      {
        to: "Profile",
        label: "Perfil",
        hint: "Gmail, sincronización y sesión",
        icon: "person-circle-outline",
      },
    ],
  },
];

/** Phone hub for every section that doesn't fit in the bottom bar. */
export default function MoreScreen() {
  const navigation = useNavigation<BottomTabNavigationProp<AppTabParamList>>();

  return (
    <ScrollView
      style={styles.root}
      contentContainerStyle={[styles.content, pageStyle]}
    >
      {SECTIONS.map((section) => {
        return (
          <View key={section.key}>
            <Text style={styles.sectionLabel}>{section.title}</Text>
            <View style={styles.group}>
              {section.items.map((item, i) => (
                <Pressable
                  key={item.to}
                  accessibilityRole="link"
                  onPress={() => navigation.navigate(item.to)}
                  style={({ pressed }) => [
                    styles.row,
                    i > 0 && styles.rowDivider,
                    pressed && styles.pressed,
                  ]}
                >
                  <View style={styles.iconBox}>
                    <Ionicons
                      name={item.icon}
                      size={20}
                      color={colors.primary}
                    />
                  </View>
                  <View style={styles.body}>
                    <Text style={styles.label}>{item.label}</Text>
                    <Text style={styles.hint} numberOfLines={1}>
                      {item.hint}
                    </Text>
                  </View>
                  <Ionicons
                    name="chevron-forward"
                    size={16}
                    color={colors.textSecondary}
                  />
                </Pressable>
              ))}
            </View>
          </View>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  content: { padding: 16, paddingBottom: 32 },
  sectionLabel: {
    color: colors.textSecondary,
    fontSize: 12,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.6,
    paddingHorizontal: 4,
    marginTop: 12,
    marginBottom: 8,
  },
  group: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: "hidden",
    marginBottom: 8,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 14,
    // Comfortable thumb target.
    minHeight: 60,
  },
  rowDivider: { borderTopWidth: 1, borderTopColor: colors.border },
  pressed: { backgroundColor: colors.surfaceMuted },
  iconBox: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: colors.primarySoft,
    alignItems: "center",
    justifyContent: "center",
  },
  body: { flex: 1 },
  label: { color: colors.textPrimary, fontSize: 15, fontWeight: "600" },
  hint: { color: colors.textSecondary, fontSize: 12, marginTop: 2 },
});
