import { colors } from "../theme/colors";

// Ionicons are font glyphs in the private-use area: text to the DOM, but
// nothing a person can read.
const GLYPHS = /[-]/g;
const SHOW_DELAY_MS = 350;
const GAP = 8;

/**
 * Web only: hovering a control that shows just an icon pops its
 * `accessibilityLabel` as a tooltip. One listener for the whole app, so any
 * icon-only button gets it by having a label — nothing to wire per button.
 */
export function installTooltips(): void {
  if (typeof document === "undefined") return;

  const tip = document.createElement("div");
  tip.setAttribute("role", "tooltip");
  Object.assign(tip.style, {
    position: "fixed",
    zIndex: "2147483647",
    pointerEvents: "none",
    maxWidth: "240px",
    padding: "6px 10px",
    borderRadius: "8px",
    background: colors.surfaceMuted,
    border: `1px solid ${colors.border}`,
    color: colors.textPrimary,
    font: '600 12px system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
    boxShadow: "0 6px 20px rgba(0, 0, 0, 0.45)",
    opacity: "0",
    transition: "opacity 120ms ease",
    left: "0",
    top: "0",
  });
  document.body.appendChild(tip);

  let current: Element | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;

  const hide = () => {
    clearTimeout(timer);
    current = null;
    tip.style.opacity = "0";
  };

  const show = (el: Element, label: string) => {
    if (!el.isConnected) return;
    tip.textContent = label;
    const r = el.getBoundingClientRect();
    const t = tip.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    let left: number;
    let top: number;
    if (r.left < 100 && r.width < 80 && r.right + GAP + t.width < vw) {
      // Icon rail on the left edge: point sideways so the next icon stays visible.
      left = r.right + GAP;
      top = r.top + (r.height - t.height) / 2;
    } else {
      left = r.left + (r.width - t.width) / 2;
      top = r.bottom + GAP + t.height > vh ? r.top - GAP - t.height : r.bottom + GAP;
    }
    tip.style.left = `${Math.max(GAP, Math.min(left, vw - t.width - GAP))}px`;
    tip.style.top = `${Math.max(GAP, Math.min(top, vh - t.height - GAP))}px`;
    tip.style.opacity = "1";
  };

  document.addEventListener("pointerover", (e) => {
    // Touch has no hover; a tooltip there would just flash on every tap.
    if (e.pointerType !== "mouse") return;
    const el = (e.target as Element | null)?.closest?.("[aria-label]") ?? null;
    if (el === current) return;
    hide();
    if (!el) return;
    const label = el.getAttribute("aria-label")?.trim();
    const visibleText = (el.textContent ?? "").replace(GLYPHS, "").trim();
    // Only when the control doesn't already say what it does.
    if (!label || visibleText) return;
    current = el;
    timer = setTimeout(() => show(el, label), SHOW_DELAY_MS);
  });
  document.addEventListener("pointerdown", hide);
  document.addEventListener("scroll", hide, true);
  document.addEventListener("keydown", hide);
  window.addEventListener("blur", hide);
}
