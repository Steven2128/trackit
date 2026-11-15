import type { LinkingOptions } from "@react-navigation/native";
import { Platform } from "react-native";

// Signed-in and signed-out trees differ, so params are left untyped here.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyLinking = LinkingOptions<any>;

/**
 * Browser URLs for each screen (web only): makes the back button, reloads and
 * shared links work instead of always landing on Inicio.
 *
 * Every section is a tab (see AppStack), so the map is the same on phones and
 * on wide screens. Static hosting rewrites every path to index.html
 * (render.yaml).
 */
export function buildLinking(signedIn: boolean): AnyLinking | undefined {
  if (Platform.OS !== "web") return undefined;

  if (!signedIn) {
    return { prefixes: [], config: { screens: { Login: "*" } } };
  }

  return {
    prefixes: [],
    config: {
      screens: {
        Dashboard: "",
        Transactions: "movimientos",
        Budgets: "presupuesto",
        Subscriptions: "suscripciones",
        DebtTracker: "deudas",
        More: "mas",
        Cards: "tarjetas",
        Plan: "plan",
        Goals: "metas",
        NetWorth: "patrimonio",
        Profile: "perfil",
      },
    },
  };
}
