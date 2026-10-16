import { Ionicons } from "@expo/vector-icons";
import {
  createBottomTabNavigator,
  type BottomTabBarProps,
} from "@react-navigation/bottom-tabs";
import { useNavigation } from "@react-navigation/native";
import {
  createNativeStackNavigator,
  type NativeStackNavigationProp,
} from "@react-navigation/native-stack";
import { Platform, Pressable, StyleSheet, Text, View } from "react-native";

import BudgetsScreen from "../screens/BudgetsScreen";
import DashboardScreen from "../screens/DashboardScreen";
import DebtTrackerScreen from "../screens/DebtTrackerScreen";
import GoalsScreen from "../screens/GoalsScreen";
import NetWorthScreen from "../screens/NetWorthScreen";
import PlanScreen from "../screens/PlanScreen";
import ProfileScreen from "../screens/ProfileScreen";
import SubscriptionsScreen from "../screens/SubscriptionsScreen";
import TransactionsScreen from "../screens/TransactionsScreen";
import { colors } from "../theme/colors";
import { SIDEBAR_WIDTH, useIsWide } from "../theme/layout";

// Profile, Goals, Plan and NetWorth live outside the tab bar (header avatar /
// dashboard shortcuts) to keep bottom nav at 5 items. On wide screens the
// tab bar becomes a sidebar with room for Plan/Goals/NetWorth as tabs too, so
// `navigate("Plan")` resolves to the tab there and to the stack on phones.
export type AppStackParamList = {
  Tabs: undefined;
  Profile: undefined;
  Goals: undefined;
  Plan: undefined;
  NetWorth: undefined;
};

export type AppTabParamList = {
  Dashboard: undefined;
  // category preselects the filter chip (used by Dashboard's category rows).
  Transactions: { category?: string | null } | undefined;
  Budgets: undefined;
  Subscriptions: undefined;
  DebtTracker: undefined;
  // Wide screens only (sidebar).
  Plan: undefined;
  Goals: undefined;
  NetWorth: undefined;
};

type IconName = keyof typeof Ionicons.glyphMap;

const TAB_ICONS: Record<keyof AppTabParamList, { active: IconName; inactive: IconName }> = {
  Dashboard: { active: "stats-chart", inactive: "stats-chart-outline" },
  Transactions: { active: "receipt", inactive: "receipt-outline" },
  Budgets: { active: "pie-chart", inactive: "pie-chart-outline" },
  Subscriptions: { active: "repeat", inactive: "repeat-outline" },
  DebtTracker: { active: "card", inactive: "card-outline" },
  Plan: { active: "map", inactive: "map-outline" },
  Goals: { active: "flag", inactive: "flag-outline" },
  NetWorth: { active: "wallet", inactive: "wallet-outline" },
};

const PLANNING_TABS = new Set<string>(["Plan", "Goals", "NetWorth"]);

function Sidebar({ state, descriptors, navigation }: BottomTabBarProps) {
  const renderItem = (index: number) => {
    const route = state.routes[index];
    const focused = state.index === index;
    const name = route.name as keyof AppTabParamList;
    const color = focused ? colors.primary : colors.textSecondary;
    return (
      <Pressable
        key={route.key}
        accessibilityRole="tab"
        accessibilityState={{ selected: focused }}
        onPress={() => {
          const event = navigation.emit({
            type: "tabPress",
            target: route.key,
            canPreventDefault: true,
          });
          if (!focused && !event.defaultPrevented) navigation.navigate(route.name);
        }}
        style={({ pressed, hovered }: { pressed: boolean; hovered?: boolean }) => [
          sidebar.item,
          focused && sidebar.itemActive,
          !focused && (hovered || pressed) && sidebar.itemHover,
        ]}
      >
        <Ionicons
          name={focused ? TAB_ICONS[name].active : TAB_ICONS[name].inactive}
          size={20}
          color={color}
        />
        <Text style={[sidebar.label, { color: focused ? colors.textPrimary : colors.textSecondary }]}>
          {descriptors[route.key].options.title}
        </Text>
      </Pressable>
    );
  };

  const indexes = state.routes.map((_, i) => i);
  return (
    <View style={sidebar.root}>
      <Text style={sidebar.brand}>TrackIt</Text>
      {indexes.filter((i) => !PLANNING_TABS.has(state.routes[i].name)).map(renderItem)}
      <Text style={sidebar.section}>Planificación</Text>
      {indexes.filter((i) => PLANNING_TABS.has(state.routes[i].name)).map(renderItem)}
      <View style={{ flex: 1 }} />
      <Pressable
        onPress={() => navigation.navigate("Profile" as never)}
        style={({ pressed, hovered }: { pressed: boolean; hovered?: boolean }) => [
          sidebar.item,
          (hovered || pressed) && sidebar.itemHover,
        ]}
      >
        <Ionicons name="person-circle-outline" size={20} color={colors.textSecondary} />
        <Text style={[sidebar.label, { color: colors.textSecondary }]}>Perfil</Text>
      </Pressable>
    </View>
  );
}

const sidebar = StyleSheet.create({
  root: {
    width: SIDEBAR_WIDTH,
    height: "100%",
    backgroundColor: colors.surface,
    borderRightWidth: 1,
    borderRightColor: colors.border,
    paddingHorizontal: 12,
    paddingVertical: 20,
    gap: 2,
  },
  brand: {
    color: colors.textPrimary,
    fontSize: 22,
    fontWeight: "800",
    paddingHorizontal: 12,
    marginBottom: 20,
  },
  section: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.6,
    paddingHorizontal: 12,
    marginTop: 18,
    marginBottom: 6,
  },
  item: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 10,
  },
  itemActive: { backgroundColor: colors.primarySoft },
  itemHover: { backgroundColor: colors.surfaceMuted },
  label: { fontSize: 14, fontWeight: "600" },
});

const Tab = createBottomTabNavigator<AppTabParamList>();
const Stack = createNativeStackNavigator<AppStackParamList>();

export function HeaderAvatarButton() {
  const navigation = useNavigation<NativeStackNavigationProp<AppStackParamList>>();
  return (
    <Pressable
      onPress={() => navigation.navigate("Profile")}
      hitSlop={8}
      accessibilityLabel="Perfil"
      style={({ pressed }) => [{ paddingHorizontal: 12 }, pressed && { opacity: 0.6 }]}
    >
      <Ionicons name="person-circle-outline" size={28} color={colors.textPrimary} />
    </Pressable>
  );
}

function Tabs() {
  const isWide = useIsWide();
  return (
    <Tab.Navigator
      tabBar={isWide ? (props) => <Sidebar {...props} /> : undefined}
      screenOptions={({ route }) => ({
        headerStyle: { backgroundColor: colors.background },
        headerTitleStyle: { color: colors.textPrimary, fontWeight: "700" },
        headerShadowVisible: false,
        // The sidebar already links to Perfil.
        headerRight: isWide ? undefined : () => <HeaderAvatarButton />,
        tabBarPosition: isWide ? "left" : "bottom",
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
          paddingTop: 6,
          // Native gets its height from the bottom safe-area inset; the
          // browser has none, which clips the labels under the icons.
          ...(Platform.OS === "web" ? { height: 72, paddingBottom: 10 } : null),
        },
        // 10px + no per-item padding so long Spanish labels
        // ("Suscripciones") fit in a 5-tab bar without truncating.
        tabBarLabelStyle: { fontSize: 10, fontWeight: "600" },
        tabBarItemStyle: { paddingHorizontal: 0 },
        // React Navigation switches to "beside-icon" on wide (browser)
        // windows, which hides the labels in our narrow centered column.
        tabBarLabelPosition: "below-icon",
        tabBarAllowFontScaling: false,
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textSecondary,
        tabBarIcon: ({ focused, color, size }) => (
          <Ionicons
            name={focused ? TAB_ICONS[route.name].active : TAB_ICONS[route.name].inactive}
            size={size}
            color={color}
          />
        ),
      })}
    >
      <Tab.Screen
        name="Dashboard"
        component={DashboardScreen}
        // The screen renders its own personalized greeting header (with avatar).
        options={{ title: "Inicio", tabBarLabel: "Inicio", headerShown: false }}
      />
      <Tab.Screen
        name="Transactions"
        component={TransactionsScreen}
        options={{ title: "Movimientos", tabBarLabel: "Movimientos" }}
      />
      <Tab.Screen
        name="Budgets"
        component={BudgetsScreen}
        options={{ title: "Presupuesto", tabBarLabel: "Presupuesto" }}
      />
      <Tab.Screen
        name="Subscriptions"
        component={SubscriptionsScreen}
        options={{ title: "Suscripciones", tabBarLabel: "Suscripciones" }}
      />
      <Tab.Screen
        name="DebtTracker"
        component={DebtTrackerScreen}
        options={{ title: "Deudas", tabBarLabel: "Deudas" }}
      />
      {isWide ? (
        <>
          <Tab.Screen name="Plan" component={PlanScreen} options={{ title: "Plan del mes" }} />
          <Tab.Screen name="Goals" component={GoalsScreen} options={{ title: "Metas de ahorro" }} />
          <Tab.Screen name="NetWorth" component={NetWorthScreen} options={{ title: "Patrimonio" }} />
        </>
      ) : null}
    </Tab.Navigator>
  );
}

const stackHeader = {
  headerStyle: { backgroundColor: colors.background },
  headerTitleStyle: { color: colors.textPrimary, fontWeight: "700" as const },
  headerTintColor: colors.primary,
  headerShadowVisible: false,
};

export default function AppStack() {
  return (
    <Stack.Navigator>
      <Stack.Screen name="Tabs" component={Tabs} options={{ headerShown: false }} />
      <Stack.Screen
        name="Profile"
        component={ProfileScreen}
        options={{ title: "Perfil", presentation: "modal", ...stackHeader }}
      />
      <Stack.Screen
        name="Goals"
        component={GoalsScreen}
        options={{ title: "Metas de ahorro", ...stackHeader }}
      />
      <Stack.Screen
        name="Plan"
        component={PlanScreen}
        options={{ title: "Plan del mes", ...stackHeader }}
      />
      <Stack.Screen
        name="NetWorth"
        component={NetWorthScreen}
        options={{ title: "Patrimonio", ...stackHeader }}
      />
    </Stack.Navigator>
  );
}
