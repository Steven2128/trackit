import { Ionicons } from "@expo/vector-icons";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";

import DashboardScreen from "../screens/DashboardScreen";
import DebtTrackerScreen from "../screens/DebtTrackerScreen";
import ProfileScreen from "../screens/ProfileScreen";
import TransactionsScreen from "../screens/TransactionsScreen";
import { colors } from "../theme/colors";

export type AppTabParamList = {
  Dashboard: undefined;
  Transactions: undefined;
  DebtTracker: undefined;
  Profile: undefined;
};

type IconName = keyof typeof Ionicons.glyphMap;

const TAB_ICONS: Record<keyof AppTabParamList, { active: IconName; inactive: IconName }> = {
  Dashboard: { active: "stats-chart", inactive: "stats-chart-outline" },
  Transactions: { active: "receipt", inactive: "receipt-outline" },
  DebtTracker: { active: "card", inactive: "card-outline" },
  Profile: { active: "person-circle", inactive: "person-circle-outline" },
};

const Tab = createBottomTabNavigator<AppTabParamList>();

export default function AppStack() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerStyle: { backgroundColor: colors.background },
        headerTitleStyle: { color: colors.textPrimary, fontWeight: "700" },
        headerShadowVisible: false,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
          paddingTop: 6,
        },
        tabBarLabelStyle: { fontSize: 11, fontWeight: "600" },
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
        options={{ title: "Inicio", tabBarLabel: "Inicio" }}
      />
      <Tab.Screen
        name="Transactions"
        component={TransactionsScreen}
        options={{ title: "Movimientos", tabBarLabel: "Movimientos" }}
      />
      <Tab.Screen
        name="DebtTracker"
        component={DebtTrackerScreen}
        options={{ title: "Deudas", tabBarLabel: "Deudas" }}
      />
      <Tab.Screen
        name="Profile"
        component={ProfileScreen}
        options={{ title: "Perfil", tabBarLabel: "Perfil" }}
      />
    </Tab.Navigator>
  );
}
