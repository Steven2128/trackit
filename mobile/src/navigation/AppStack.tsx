import { Ionicons } from "@expo/vector-icons";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { useNavigation } from "@react-navigation/native";
import {
  createNativeStackNavigator,
  type NativeStackNavigationProp,
} from "@react-navigation/native-stack";
import { Pressable } from "react-native";

import BudgetsScreen from "../screens/BudgetsScreen";
import DashboardScreen from "../screens/DashboardScreen";
import DebtTrackerScreen from "../screens/DebtTrackerScreen";
import GoalsScreen from "../screens/GoalsScreen";
import PlanScreen from "../screens/PlanScreen";
import ProfileScreen from "../screens/ProfileScreen";
import SubscriptionsScreen from "../screens/SubscriptionsScreen";
import TransactionsScreen from "../screens/TransactionsScreen";
import { colors } from "../theme/colors";

// Profile, Goals and Plan live outside the tab bar (header avatar / dashboard
// shortcuts) to keep bottom nav at 5 items.
export type AppStackParamList = {
  Tabs: undefined;
  Profile: undefined;
  Goals: undefined;
  Plan: undefined;
};

export type AppTabParamList = {
  Dashboard: undefined;
  // category preselects the filter chip (used by Dashboard's category rows).
  Transactions: { category?: string | null } | undefined;
  Budgets: undefined;
  Subscriptions: undefined;
  DebtTracker: undefined;
};

type IconName = keyof typeof Ionicons.glyphMap;

const TAB_ICONS: Record<keyof AppTabParamList, { active: IconName; inactive: IconName }> = {
  Dashboard: { active: "stats-chart", inactive: "stats-chart-outline" },
  Transactions: { active: "receipt", inactive: "receipt-outline" },
  Budgets: { active: "pie-chart", inactive: "pie-chart-outline" },
  Subscriptions: { active: "repeat", inactive: "repeat-outline" },
  DebtTracker: { active: "card", inactive: "card-outline" },
};

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
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerStyle: { backgroundColor: colors.background },
        headerTitleStyle: { color: colors.textPrimary, fontWeight: "700" },
        headerShadowVisible: false,
        headerRight: () => <HeaderAvatarButton />,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
          paddingTop: 6,
        },
        // 10px + no per-item padding so long Spanish labels
        // ("Suscripciones") fit in a 5-tab bar without truncating.
        tabBarLabelStyle: { fontSize: 10, fontWeight: "600" },
        tabBarItemStyle: { paddingHorizontal: 0 },
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
    </Stack.Navigator>
  );
}
