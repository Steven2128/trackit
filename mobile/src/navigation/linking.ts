import type { LinkingOptions } from "@react-navigation/native";
import { Platform } from "react-native";

// Signed-in and signed-out trees differ, so params are left untyped here.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyLinking = LinkingOptions<any>;

/**
 * Browser URLs for each screen (web only): makes the back button, reloads and
 * shared links work instead of always landing on Inicio.
 *
 * Plan / Goals / NetWorth / Profile are tabs on wide screens and stack screens on
 * phones (see AppStack), so the same path maps to whichever exists.
 * Static hosting rewrites every path to index.html (render.yaml).
 */
export function buildLinking(signedIn: boolean, isWide: boolean): AnyLinking | undefined {
  if (Platform.OS !== "web") return undefined;

  if (!signedIn) {
    return { prefixes: [], config: { screens: { Login: "*" } } };
  }

  const planning = { Plan: "plan", Goals: "metas", NetWorth: "patrimonio", Profile: "perfil" };
  return {
    prefixes: [],
    config: {
      // A deep link to a stack screen (e.g. /plan on a phone) still gets the
      // tabs underneath, so its header shows a back arrow.
      initialRouteName: "Tabs",
      screens: {
        Tabs: {
          screens: {
            Dashboard: "",
            Transactions: "movimientos",
            Budgets: "presupuesto",
            Subscriptions: "suscripciones",
            DebtTracker: "deudas",
            ...(isWide ? planning : {}),
          },
        },
        ...(isWide ? {} : planning),
      },
    },
  };
}
