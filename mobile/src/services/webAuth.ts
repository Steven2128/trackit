import { Platform } from "react-native";

/**
 * Browser half of the server-side OAuth flow. Native uses
 * `WebBrowser.openAuthSessionAsync` + the `trackit://` scheme; on web we do
 * a full-page redirect and the backend sends us back to `return_url` with
 * the result in the URL fragment (`#kind=auth&access_token=...`).
 */

export const isWeb = Platform.OS === "web";

export function webReturnUrl(): string {
  return `${window.location.origin}/`;
}

export function redirectTo(url: string): void {
  window.location.assign(url);
}

export type OAuthFragment = Record<string, string> & { kind?: string };

let pending: OAuthFragment | null | undefined;

/**
 * Read (once) the OAuth result left in the fragment and strip it from the
 * address bar so tokens don't linger in history or get copy-pasted.
 */
export function takeOAuthFragment(): OAuthFragment | null {
  if (!isWeb) return null;
  if (pending === undefined) {
    const hash = window.location.hash.replace(/^#/, "");
    const params = new URLSearchParams(hash);
    pending = params.has("kind") ? Object.fromEntries(params.entries()) : null;
    if (pending) {
      window.history.replaceState(null, "", window.location.pathname + window.location.search);
    }
  }
  const result = pending;
  pending = null;
  return result;
}
