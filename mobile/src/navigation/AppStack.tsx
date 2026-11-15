import { Ionicons } from "@expo/vector-icons";
import {
  BottomTabBar,
  createBottomTabNavigator,
  type BottomTabBarProps,
  type BottomTabNavigationOptions,
  type BottomTabNavigationProp,
} from "@react-navigation/bottom-tabs";
import { useNavigation } from "@react-navigation/native";
import { Platform, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import BudgetsScreen from "../screens/BudgetsScreen";
import CardsScreen from "../screens/CardsScreen";
import DashboardScreen from "../screens/DashboardScreen";
import DebtTrackerScreen from "../screens/DebtTrackerScreen";
import GoalsScreen from "../screens/GoalsScreen";
import MoreScreen from "../screens/MoreScreen";
import NetWorthScreen from "../screens/NetWorthScreen";
import PlanScreen from "../screens/PlanScreen";
import ProfileScreen from "../screens/ProfileScreen";
import SubscriptionsScreen from "../screens/SubscriptionsScreen";
import TransactionsScreen from "../screens/TransactionsScreen";
import { useNavSections } from "../store/navSections";
import { colors } from "../theme/colors";
import { SIDEBAR_RAIL_WIDTH, SIDEBAR_WIDTH, useIsWide } from "../theme/layout";

// One tab navigator for every section. Wide screens list them all in the
// sidebar. Phones show Inicio / Movimientos / Presupuesto / Deudas / Más in the
// bottom bar; the rest are tabs with a hidden button, reached from "Más" (and
// from shortcuts in other screens), so the bottom bar never disappears.
export type AppTabParamList = {
  Dashboard: undefined;
  // category preselects the filter chip (used by Dashboard's category rows).
  Transactions: { category?: string | null } | undefined;
  Budgets: undefined;
  Subscriptions: undefined;
  DebtTracker: undefined;
  // Phone hub listing the sections below; hidden from the sidebar.
  More: undefined;
  Cards: undefined;
  Plan: undefined;
  Goals: undefined;
  NetWorth: undefined;
  Profile: undefined;
};

type IconName = keyof typeof Ionicons.glyphMap;

const TAB_ICONS: Record<keyof AppTabParamList, { active: IconName; inactive: IconName }> = {
  Dashboard: { active: "stats-chart", inactive: "stats-chart-outline" },
  Transactions: { active: "receipt", inactive: "receipt-outline" },
  Budgets: { active: "pie-chart", inactive: "pie-chart-outline" },
  Subscriptions: { active: "repeat", inactive: "repeat-outline" },
  DebtTracker: { active: "trending-down", inactive: "trending-down-outline" },
  More: { active: "grid", inactive: "grid-outline" },
  Cards: { active: "card", inactive: "card-outline" },
  Plan: { active: "map", inactive: "map-outline" },
  Goals: { active: "flag", inactive: "flag-outline" },
  NetWorth: { active: "wallet", inactive: "wallet-outline" },
  Profile: { active: "person-circle", inactive: "person-circle-outline" },
};

const PLANNING_TABS = new Set<string>(["Plan", "Goals", "NetWorth"]);
// No button in the phone bottom bar: reached through "Más".
const SECONDARY_TABS = new Set<string>(["Subscriptions", "Cards", "Plan", "Goals", "NetWorth", "Profile"]);
// Not in the sidebar's main list (Profile is pinned at its bottom instead).
const SIDEBAR_SKIP = new Set<string>(["More", "Profile"]);

// Key in the navSections store for the whole bar (sidebar / bottom bar).
const NAVBAR = "navbar";

function Sidebar({ state, descriptors, navigation }: BottomTabBarProps) {
  const collapsed = useNavSections((s) => s.collapsed);
  const toggle = useNavSections((s) => s.toggle);
  // Rail: the whole sidebar folded down to a strip of icons.
  const rail = !!collapsed[NAVBAR];

  const renderItem = (index: number) => {
    const route = state.routes[index];
    const focused = state.index === index;
    const name = route.name as keyof AppTabParamList;
    const color = focused ? colors.primary : colors.textSecondary;
    return (
      <Pressable
        key={route.key}
        accessibilityRole="tab"
        accessibilityLabel={descriptors[route.key].options.title}
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
          rail && sidebar.itemRail,
          focused && sidebar.itemActive,
          !focused && (hovered || pressed) && sidebar.itemHover,
        ]}
      >
        <Ionicons
          name={focused ? TAB_ICONS[name].active : TAB_ICONS[name].inactive}
          size={20}
          color={color}
        />
        {rail ? null : (
          <Text style={[sidebar.label, { color: focused ? colors.textPrimary : colors.textSecondary }]}>
            {descriptors[route.key].options.title}
          </Text>
        )}
      </Pressable>
    );
  };

  const indexes = state.routes.map((_, i) => i);
  const mainGroup = indexes.filter(
    (i) => !PLANNING_TABS.has(state.routes[i].name) && !SIDEBAR_SKIP.has(state.routes[i].name),
  );
  const planningGroup = indexes.filter((i) => PLANNING_TABS.has(state.routes[i].name));
  const profile = indexes.filter((i) => state.routes[i].name === "Profile");

  const toggleButton = (
    <Pressable
      onPress={() => toggle(NAVBAR)}
      hitSlop={6}
      accessibilityRole="button"
      accessibilityLabel={rail ? "Expandir menú" : "Colapsar menú"}
      accessibilityState={{ expanded: !rail }}
      style={({ pressed, hovered }: { pressed: boolean; hovered?: boolean }) => [
        sidebar.toggle,
        (hovered || pressed) && sidebar.itemHover,
      ]}
    >
      <Ionicons name={rail ? "menu" : "chevron-back"} size={20} color={colors.textSecondary} />
    </Pressable>
  );

  if (rail) {
    return (
      <ScrollView
        style={[sidebar.root, sidebar.rootRail]}
        contentContainerStyle={[sidebar.content, sidebar.contentRail]}
      >
        {toggleButton}
        {mainGroup.map(renderItem)}
        <View style={sidebar.railDivider} />
        {planningGroup.map(renderItem)}
        <View style={sidebar.spacer} />
        {profile.map(renderItem)}
      </ScrollView>
    );
  }

  // Accordion group. Folded, it still shows the current section so you can
  // see where you are.
  const renderGroup = (key: string, title: string, group: number[]) => {
    const folded = !!collapsed[key];
    return (
      <View style={sidebar.group}>
        <Pressable
          onPress={() => toggle(key)}
          accessibilityRole="button"
          accessibilityState={{ expanded: !folded }}
          style={({ pressed, hovered }: { pressed: boolean; hovered?: boolean }) => [
            sidebar.sectionRow,
            (hovered || pressed) && sidebar.itemHover,
          ]}
        >
          <Text style={sidebar.section}>{title}</Text>
          <Ionicons
            name={folded ? "chevron-forward" : "chevron-down"}
            size={14}
            color={colors.textSecondary}
          />
        </Pressable>
        {group.filter((i) => !folded || state.index === i).map(renderItem)}
      </View>
    );
  };

  return (
    // Scrolls: a phone in landscape is "wide" but too short for ten items.
    <ScrollView style={sidebar.root} contentContainerStyle={sidebar.content}>
      <View style={sidebar.brandRow}>
        <Text style={sidebar.brand}>TrackIt</Text>
        {toggleButton}
      </View>
      {renderGroup("main", "Tu plata", mainGroup)}
      {renderGroup("planning", "Planificación", planningGroup)}
      <View style={sidebar.spacer} />
      {profile.map(renderItem)}
    </ScrollView>
  );
}

const sidebar = StyleSheet.create({
  root: {
    width: SIDEBAR_WIDTH,
    flexGrow: 0,
    height: "100%",
    backgroundColor: colors.surface,
    borderRightWidth: 1,
    borderRightColor: colors.border,
  },
  // flexGrow keeps Perfil pinned to the bottom when everything fits.
  content: { flexGrow: 1, paddingHorizontal: 12, paddingVertical: 20, gap: 2 },
  spacer: { flex: 1, minHeight: 12 },
  rootRail: { width: SIDEBAR_RAIL_WIDTH },
  contentRail: { paddingHorizontal: 8, alignItems: "center", gap: 4 },
  railDivider: { height: 1, alignSelf: "stretch", backgroundColor: colors.border, marginVertical: 8 },
  brandRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingLeft: 12,
    marginBottom: 12,
  },
  brand: { color: colors.textPrimary, fontSize: 22, fontWeight: "800" },
  toggle: {
    width: 40,
    height: 40,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
  },
  itemRail: { width: 44, height: 44, paddingHorizontal: 0, paddingVertical: 0, justifyContent: "center" },
  group: { gap: 2, marginBottom: 10 },
  sectionRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 10,
  },
  section: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.6,
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

/** Phone bottom bar that can be tucked away to give the page the full height;
 *  a small tab stays at the bottom edge to bring it back. */
function PhoneBar(props: BottomTabBarProps) {
  const hiddenBar = useNavSections((s) => !!s.collapsed[NAVBAR]);
  const toggle = useNavSections((s) => s.toggle);

  const handle = (
    <Pressable
      onPress={() => toggle(NAVBAR)}
      hitSlop={{ top: 12, bottom: 8, left: 16, right: 16 }}
      accessibilityRole="button"
      accessibilityLabel={hiddenBar ? "Mostrar menú" : "Ocultar menú"}
      accessibilityState={{ expanded: !hiddenBar }}
      style={({ pressed }) => [phoneBar.handle, pressed && { opacity: 0.6 }]}
    >
      <Ionicons name={hiddenBar ? "chevron-up" : "chevron-down"} size={16} color={colors.textSecondary} />
    </Pressable>
  );

  if (hiddenBar) {
    return (
      <View style={[phoneBar.floating, { bottom: props.insets.bottom }]} pointerEvents="box-none">
        {handle}
      </View>
    );
  }
  return (
    <View>
      <View style={phoneBar.above} pointerEvents="box-none">
        {handle}
      </View>
      <BottomTabBar {...props} />
    </View>
  );
}

const phoneBar = StyleSheet.create({
  // Sits on the bar's top edge, like a drawer pull.
  above: { position: "absolute", top: -22, left: 0, right: 0, alignItems: "center", zIndex: 1 },
  floating: { position: "absolute", left: 0, right: 0, alignItems: "center" },
  handle: {
    width: 64,
    height: 22,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderBottomWidth: 0,
    borderColor: colors.border,
    borderTopLeftRadius: 12,
    borderTopRightRadius: 12,
  },
});

const Tab = createBottomTabNavigator<AppTabParamList>();

type TabNavigation = BottomTabNavigationProp<AppTabParamList>;

export function HeaderAvatarButton() {
  const navigation = useNavigation<TabNavigation>();
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

/** Phones: sections opened from "Más" (or a shortcut) get a way back. */
function HeaderBackButton() {
  const navigation = useNavigation<TabNavigation>();
  return (
    <Pressable
      onPress={() => (navigation.canGoBack() ? navigation.goBack() : navigation.navigate("More"))}
      hitSlop={8}
      accessibilityLabel="Volver"
      style={({ pressed }) => [{ paddingHorizontal: 12 }, pressed && { opacity: 0.6 }]}
    >
      <Ionicons name="chevron-back" size={26} color={colors.primary} />
    </Pressable>
  );
}

/** "Más" stays lit while one of the sections it lists is open. */
function moreTabOptions(state: { index: number; routes: { name: string }[] }): BottomTabNavigationOptions {
  const inside = SECONDARY_TABS.has(state.routes[state.index].name);
  const tint = (color: string) => (inside ? colors.primary : color);
  return {
    tabBarIcon: ({ focused, color, size }) => (
      <Ionicons
        name={focused || inside ? TAB_ICONS.More.active : TAB_ICONS.More.inactive}
        size={size}
        color={tint(color)}
      />
    ),
    tabBarLabel: ({ color }) => (
      <Text allowFontScaling={false} style={{ fontSize: 10, fontWeight: "600", color: tint(color) }}>
        Más
      </Text>
    ),
  };
}

export default function AppStack() {
  const isWide = useIsWide();
  return (
    <Tab.Navigator
      // Every tab switch is a history entry, so the browser back button
      // returns to the previous section instead of skipping it.
      backBehavior="history"
      tabBar={(props) => (isWide ? <Sidebar {...props} /> : <PhoneBar {...props} />)}
      screenOptions={({ route, navigation }) => {
        const hidden = !isWide && SECONDARY_TABS.has(route.name);
        return {
          headerStyle: { backgroundColor: colors.background },
          headerTitleStyle: { color: colors.textPrimary, fontWeight: "700" },
          headerShadowVisible: false,
          headerLeft: hidden ? () => <HeaderBackButton /> : undefined,
          // The sidebar already links to Perfil.
          headerRight:
            isWide || route.name === "Profile" ? undefined : () => <HeaderAvatarButton />,
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
          // ("Presupuesto") fit in a 5-tab bar without truncating.
          tabBarLabelStyle: { fontSize: 10, fontWeight: "600" },
          tabBarItemStyle: hidden ? { display: "none" } : { paddingHorizontal: 0 },
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
          ...(route.name === "More" ? moreTabOptions(navigation.getState()) : null),
        };
      }}
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
        options={{ title: "Suscripciones" }}
      />
      <Tab.Screen
        name="DebtTracker"
        component={DebtTrackerScreen}
        options={{ title: "Deudas", tabBarLabel: "Deudas" }}
      />
      <Tab.Screen name="More" component={MoreScreen} options={{ title: "Más" }} />
      <Tab.Screen name="Cards" component={CardsScreen} options={{ title: "Tarjetas" }} />
      <Tab.Screen name="Plan" component={PlanScreen} options={{ title: "Plan del mes" }} />
      <Tab.Screen name="Goals" component={GoalsScreen} options={{ title: "Metas de ahorro" }} />
      <Tab.Screen name="NetWorth" component={NetWorthScreen} options={{ title: "Patrimonio" }} />
      <Tab.Screen name="Profile" component={ProfileScreen} options={{ title: "Perfil" }} />
    </Tab.Navigator>
  );
}
