# Mobile screens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace stubs of `DashboardScreen`, `TransactionsScreen`, and `DebtTrackerScreen` with full implementations that consume the existing backend endpoints.

**Architecture:** React Query for cache + cross-screen invalidation. `@gorhom/bottom-sheet` for debt create/edit. `react-native-chart-kit` for the 6-month trend. Shared utilities (`formatCOP`, `CATEGORIES`) and presentational components (`MoneyText`, `CategoryIcon`, `TransactionRow`, `DebtCard`, `DebtFormSheet`, `TrendChart`).

**Tech Stack:** Expo SDK 54, React Native 0.81, TypeScript, `@tanstack/react-query` (already installed), `@gorhom/bottom-sheet`, `react-native-chart-kit`, `react-native-svg`, `react-native-reanimated`, `react-native-gesture-handler`.

**Spec:** `docs/superpowers/specs/2026-07-01-mobile-screens-design.md`

**Working dir:** All commands assume `cwd = <repo-root>/mobile` unless noted. Windows: use Bash tool (Git Bash).

**No JS test infra.** Verification per task = `npx tsc --noEmit` (typecheck). Feature correctness = manual walkthrough at end (Task 10).

---

## File map

**New files:**
- `mobile/babel.config.js`
- `mobile/src/utils/currency.ts`
- `mobile/src/utils/categories.ts`
- `mobile/src/utils/dates.ts`
- `mobile/src/components/MoneyText.tsx`
- `mobile/src/components/CategoryIcon.tsx`
- `mobile/src/components/TransactionRow.tsx`
- `mobile/src/components/DebtCard.tsx`
- `mobile/src/components/DebtFormSheet.tsx`
- `mobile/src/components/TrendChart.tsx`
- `mobile/src/services/queries/dashboard.ts`
- `mobile/src/services/queries/transactions.ts`
- `mobile/src/services/queries/debts.ts`

**Modified files:**
- `mobile/package.json` (deps)
- `mobile/App.tsx` (QueryClient config, GestureHandlerRootView wrap)
- `mobile/src/screens/DashboardScreen.tsx` (rewrite)
- `mobile/src/screens/TransactionsScreen.tsx` (rewrite)
- `mobile/src/screens/DebtTrackerScreen.tsx` (rewrite)

---

### Task 1: Install dependencies + configure reanimated

**Files:**
- Modify: `mobile/package.json`
- Create: `mobile/babel.config.js`
- Modify: `mobile/App.tsx`

- [ ] **Step 1: Install runtime deps via `expo install`** (uses Expo SDK-compatible versions)

Run from `mobile/`:
```bash
npx expo install react-native-svg react-native-gesture-handler react-native-reanimated @gorhom/bottom-sheet react-native-chart-kit
```
Expected: 5 packages added to `package.json` under `dependencies`. `@tanstack/react-query` is already installed — do not re-install.

- [ ] **Step 2: Create `mobile/babel.config.js` with the reanimated plugin**

Write file exactly:
```js
module.exports = function (api) {
  api.cache(true);
  return {
    presets: ["babel-preset-expo"],
    plugins: ["react-native-reanimated/plugin"],
  };
};
```

The reanimated plugin must be the **last** plugin listed (per Reanimated docs). If `gorhom/bottom-sheet` renders as an empty box, this file is the first thing to double-check.

- [ ] **Step 3: Update `App.tsx` — add `GestureHandlerRootView`, tighten QueryClient config**

Full file content (replace entirely):
```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StatusBar } from "expo-status-bar";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";

import RootNavigator from "./src/navigation/RootNavigator";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 60_000,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <QueryClientProvider client={queryClient}>
        <SafeAreaProvider>
          <StatusBar style="light" />
          <RootNavigator />
        </SafeAreaProvider>
      </QueryClientProvider>
    </GestureHandlerRootView>
  );
}
```

- [ ] **Step 4: Typecheck**

Run from `mobile/`:
```bash
npx tsc --noEmit
```
Expected: exit 0, no output.

- [ ] **Step 5: Commit**

```bash
cd .. && git add mobile/package.json mobile/package-lock.json mobile/babel.config.js mobile/App.tsx
git commit -m "chore(mobile): install chart/sheet deps + configure reanimated"
```

---

### Task 2: Currency utility

**Files:**
- Create: `mobile/src/utils/currency.ts`

- [ ] **Step 1: Write `currency.ts`**

```ts
// mobile/src/utils/currency.ts
const cop = new Intl.NumberFormat("es-CO", {
  style: "currency",
  currency: "COP",
  maximumFractionDigits: 0,
});

export function formatCOP(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "$0";
  const n = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(n)) return "$0";
  return cop.format(n);
}

export function parseCOP(input: string): number {
  const digits = input.replace(/[^\d]/g, "");
  return digits === "" ? 0 : Number(digits);
}
```

- [ ] **Step 2: Typecheck**

Run: `npx tsc --noEmit` from `mobile/`. Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add mobile/src/utils/currency.ts
git commit -m "feat(mobile): add COP currency formatter and parser"
```

---

### Task 3: Categories catalog + dates helper + MoneyText + CategoryIcon

**Files:**
- Create: `mobile/src/utils/categories.ts`
- Create: `mobile/src/utils/dates.ts`
- Create: `mobile/src/components/MoneyText.tsx`
- Create: `mobile/src/components/CategoryIcon.tsx`

- [ ] **Step 1: Create `categories.ts`**

```ts
// mobile/src/utils/categories.ts
export type CategoryDef = { key: string; label: string; emoji: string };

export const CATEGORIES: CategoryDef[] = [
  { key: "food", label: "Comida", emoji: "🍽" },
  { key: "transport", label: "Transporte", emoji: "🚗" },
  { key: "grocery", label: "Mercado", emoji: "🛒" },
  { key: "health", label: "Salud", emoji: "🏥" },
  { key: "entertainment", label: "Entretenimiento", emoji: "🎬" },
  { key: "income", label: "Ingreso", emoji: "💰" },
  { key: "transfer", label: "Transferencia", emoji: "↔" },
  { key: "cash_withdrawal", label: "Retiro", emoji: "💵" },
  { key: "other", label: "Otros", emoji: "📦" },
];

const FALLBACK: CategoryDef = { key: "other", label: "Otros", emoji: "📦" };

export function getCategory(key: string | null | undefined): CategoryDef {
  if (!key) return FALLBACK;
  const found = CATEGORIES.find((c) => c.key === key);
  if (found) return found;
  return { key, label: key, emoji: "📦" };
}
```

- [ ] **Step 2: Create `dates.ts`**

```ts
// mobile/src/utils/dates.ts
const MESES = [
  "ene", "feb", "mar", "abr", "may", "jun",
  "jul", "ago", "sep", "oct", "nov", "dic",
];

function ymdLocal(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function formatDayHeader(iso: string): string {
  const d = new Date(iso);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);

  const key = ymdLocal(d);
  if (key === ymdLocal(today)) return "Hoy";
  if (key === ymdLocal(yesterday)) return "Ayer";
  return `${d.getDate()} ${MESES[d.getMonth()]}`;
}

export function dayKey(iso: string): string {
  return ymdLocal(new Date(iso));
}

export function currentMonthYYYYMM(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  return `${y}-${m}`;
}

export function shiftMonth(yyyymm: string, delta: number): string {
  const [y, m] = yyyymm.split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  const ny = d.getFullYear();
  const nm = String(d.getMonth() + 1).padStart(2, "0");
  return `${ny}-${nm}`;
}

export function humanizeMonth(yyyymm: string): string {
  const [y, m] = yyyymm.split("-").map(Number);
  const label = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"][m - 1];
  return `${label} ${y}`;
}
```

- [ ] **Step 3: Create `MoneyText.tsx`**

```tsx
// mobile/src/components/MoneyText.tsx
import { StyleSheet, Text, TextProps } from "react-native";

import { colors } from "../theme/colors";
import { formatCOP } from "../utils/currency";

type Props = TextProps & {
  value: number | string | null | undefined;
  signed?: boolean;      // if true and value > 0, prefix "+"
  positive?: boolean;    // color green
  size?: "sm" | "md" | "lg" | "xl";
};

const SIZES: Record<NonNullable<Props["size"]>, number> = {
  sm: 12, md: 14, lg: 18, xl: 26,
};

export default function MoneyText({
  value, signed = false, positive = false, size = "md", style, ...rest
}: Props) {
  const text = formatCOP(value);
  const n = typeof value === "string" ? Number(value) : (value ?? 0);
  const withSign = signed && n > 0 ? `+${text}` : text;
  return (
    <Text
      {...rest}
      style={[
        styles.base,
        { fontSize: SIZES[size], color: positive ? colors.success : colors.textPrimary },
        style,
      ]}
    >
      {withSign}
    </Text>
  );
}

const styles = StyleSheet.create({
  base: { fontWeight: "700" },
});
```

- [ ] **Step 4: Create `CategoryIcon.tsx`**

```tsx
// mobile/src/components/CategoryIcon.tsx
import { StyleSheet, Text, View } from "react-native";

import { colors } from "../theme/colors";
import { getCategory } from "../utils/categories";

type Props = {
  categoryKey: string | null | undefined;
  size?: number;
};

export default function CategoryIcon({ categoryKey, size = 36 }: Props) {
  const cat = getCategory(categoryKey);
  return (
    <View style={[styles.wrap, { width: size, height: size, borderRadius: size / 2 }]}>
      <Text style={{ fontSize: size * 0.5 }}>{cat.emoji}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    backgroundColor: colors.surfaceMuted,
    alignItems: "center",
    justifyContent: "center",
  },
});
```

- [ ] **Step 5: Typecheck**

Run: `npx tsc --noEmit` from `mobile/`. Expected: exit 0.

- [ ] **Step 6: Commit**

```bash
git add mobile/src/utils/categories.ts mobile/src/utils/dates.ts mobile/src/components/MoneyText.tsx mobile/src/components/CategoryIcon.tsx
git commit -m "feat(mobile): add shared money/category/date utilities"
```

---

### Task 4: React Query hooks — dashboard, transactions, debts

**Files:**
- Create: `mobile/src/services/queries/dashboard.ts`
- Create: `mobile/src/services/queries/transactions.ts`
- Create: `mobile/src/services/queries/debts.ts`

- [ ] **Step 1: Create `queries/dashboard.ts`**

```ts
// mobile/src/services/queries/dashboard.ts
import { useQuery } from "@tanstack/react-query";

import { api } from "../api";

export type MonthCategoryItem = {
  category: string | null;
  total: string;
  count: number;
};

export type MonthTrendEntry = {
  month: string;
  total_spent: string;
  by_category: MonthCategoryItem[];
};

export type CurrentMonthSnapshot = {
  month: string;
  total_spent: string;
  by_category: MonthCategoryItem[];
  transaction_count: number;
};

export type DebtSnapshot = {
  total_debt: string;
  total_minimum_payment: string;
  debt_count: number;
};

export type DashboardResponse = {
  monthly_trend: MonthTrendEntry[];
  current_month: CurrentMonthSnapshot;
  debts: DebtSnapshot;
};

export const dashboardQueryKey = ["dashboard"] as const;

export function useDashboard() {
  return useQuery({
    queryKey: dashboardQueryKey,
    queryFn: async () => {
      const res = await api.get<DashboardResponse>("/dashboard");
      return res.data;
    },
  });
}
```

- [ ] **Step 2: Create `queries/transactions.ts`**

```ts
// mobile/src/services/queries/transactions.ts
import { useQuery } from "@tanstack/react-query";

import { api } from "../api";

export type TransactionType = "debit" | "credit";

export type TransactionOut = {
  id: string;
  amount: string;
  merchant: string | null;
  category: string | null;
  transaction_type: TransactionType;
  currency: string;
  card_last_digits: string | null;
  occurred_at: string;
};

export type TransactionListResponse = {
  items: TransactionOut[];
  total: number;
  limit: number;
  offset: number;
};

export type TransactionFilters = {
  month: string;                  // YYYY-MM
  category?: string | null;
  type?: TransactionType | null;
  limit?: number;
};

export const transactionsQueryKey = (filters: TransactionFilters) =>
  ["transactions", filters] as const;

export function useTransactions(filters: TransactionFilters) {
  return useQuery({
    queryKey: transactionsQueryKey(filters),
    queryFn: async () => {
      const params: Record<string, string | number> = {
        month: filters.month,
        limit: filters.limit ?? 200,
      };
      if (filters.category) params.category = filters.category;
      if (filters.type) params.type = filters.type;
      const res = await api.get<TransactionListResponse>("/transactions", { params });
      return res.data;
    },
  });
}
```

- [ ] **Step 3: Create `queries/debts.ts`**

```ts
// mobile/src/services/queries/debts.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api";
import { dashboardQueryKey } from "./dashboard";

export type DebtOut = {
  id: string;
  bank_name: string;
  total_amount: string;
  interest_rate: string | null;
  minimum_payment: string | null;
  created_at: string;
};

export type DebtPayload = {
  bank_name: string;
  total_amount: string;
  interest_rate?: string | null;
  minimum_payment?: string | null;
};

export const debtsQueryKey = ["debts"] as const;

function invalidateAll(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: debtsQueryKey });
  qc.invalidateQueries({ queryKey: dashboardQueryKey });
}

export function useDebts() {
  return useQuery({
    queryKey: debtsQueryKey,
    queryFn: async () => {
      const res = await api.get<DebtOut[]>("/debts");
      return res.data;
    },
  });
}

export function useCreateDebt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: DebtPayload) => {
      const res = await api.post<DebtOut>("/debts", payload);
      return res.data;
    },
    onSuccess: () => invalidateAll(qc),
  });
}

export function useUpdateDebt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, payload }: { id: string; payload: Partial<DebtPayload> }) => {
      const res = await api.patch<DebtOut>(`/debts/${id}`, payload);
      return res.data;
    },
    onSuccess: () => invalidateAll(qc),
  });
}

export function useDeleteDebt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/debts/${id}`);
    },
    onSuccess: () => invalidateAll(qc),
  });
}
```

- [ ] **Step 4: Typecheck**

Run: `npx tsc --noEmit` from `mobile/`. Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add mobile/src/services/queries/
git commit -m "feat(mobile): add react-query hooks for dashboard/transactions/debts"
```

---

### Task 5: TransactionRow + DebtCard components

**Files:**
- Create: `mobile/src/components/TransactionRow.tsx`
- Create: `mobile/src/components/DebtCard.tsx`

- [ ] **Step 1: Create `TransactionRow.tsx`**

```tsx
// mobile/src/components/TransactionRow.tsx
import { StyleSheet, Text, View } from "react-native";

import { colors } from "../theme/colors";
import { getCategory } from "../utils/categories";
import CategoryIcon from "./CategoryIcon";
import MoneyText from "./MoneyText";

type Props = {
  merchant: string | null;
  category: string | null;
  amount: string;
  type: "debit" | "credit";
};

export default function TransactionRow({ merchant, category, amount, type }: Props) {
  const cat = getCategory(category);
  const isIncome = type === "credit";
  return (
    <View style={styles.row}>
      <CategoryIcon categoryKey={category} />
      <View style={styles.body}>
        <Text style={styles.merchant} numberOfLines={1}>
          {merchant ?? "—"}
        </Text>
        <Text style={styles.cat}>{cat.label}</Text>
      </View>
      <MoneyText
        value={amount}
        signed={isIncome}
        positive={isIncome}
        size="md"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 12,
    marginBottom: 8,
    gap: 12,
  },
  body: { flex: 1 },
  merchant: { color: colors.textPrimary, fontSize: 14, fontWeight: "600" },
  cat: { color: colors.textSecondary, fontSize: 11, marginTop: 2 },
});
```

- [ ] **Step 2: Create `DebtCard.tsx`**

```tsx
// mobile/src/components/DebtCard.tsx
import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors } from "../theme/colors";
import type { DebtOut } from "../services/queries/debts";
import MoneyText from "./MoneyText";

type Props = {
  debt: DebtOut;
  onPress: (debt: DebtOut) => void;
};

export default function DebtCard({ debt, onPress }: Props) {
  const rate = debt.interest_rate ? `${Number(debt.interest_rate)}% EA` : null;
  const min = debt.minimum_payment ? `Pago mín ${Number(debt.minimum_payment).toLocaleString("es-CO")}` : null;
  return (
    <Pressable style={styles.card} onPress={() => onPress(debt)}>
      <View style={styles.left}>
        <View style={styles.titleRow}>
          <Text style={styles.bank} numberOfLines={1}>{debt.bank_name}</Text>
          {rate ? (
            <View style={styles.pill}>
              <Text style={styles.pillText}>{rate}</Text>
            </View>
          ) : null}
        </View>
        {min ? <Text style={styles.meta}>{min}</Text> : null}
      </View>
      <MoneyText value={debt.total_amount} size="md" />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 12,
    marginBottom: 8,
    borderLeftWidth: 3,
    borderLeftColor: colors.danger,
    gap: 12,
  },
  left: { flex: 1 },
  titleRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  bank: { color: colors.textPrimary, fontSize: 14, fontWeight: "600" },
  pill: {
    backgroundColor: colors.surfaceMuted,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
  },
  pillText: { color: colors.textSecondary, fontSize: 10 },
  meta: { color: colors.textSecondary, fontSize: 11, marginTop: 3 },
});
```

- [ ] **Step 3: Typecheck**

Run: `npx tsc --noEmit` from `mobile/`. Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add mobile/src/components/TransactionRow.tsx mobile/src/components/DebtCard.tsx
git commit -m "feat(mobile): add TransactionRow and DebtCard components"
```

---

### Task 6: DebtFormSheet bottom sheet

**Files:**
- Create: `mobile/src/components/DebtFormSheet.tsx`

- [ ] **Step 1: Create `DebtFormSheet.tsx`**

```tsx
// mobile/src/components/DebtFormSheet.tsx
import BottomSheet, { BottomSheetTextInput, BottomSheetView } from "@gorhom/bottom-sheet";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Keyboard,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import type { DebtOut, DebtPayload } from "../services/queries/debts";
import {
  useCreateDebt,
  useDeleteDebt,
  useUpdateDebt,
} from "../services/queries/debts";
import { colors } from "../theme/colors";
import { parseCOP } from "../utils/currency";

type Props = {
  isVisible: boolean;
  debt?: DebtOut;
  onClose: () => void;
};

type FormState = {
  bank: string;
  amount: string;
  rate: string;
  min: string;
};

const EMPTY: FormState = { bank: "", amount: "", rate: "", min: "" };

function fromDebt(d?: DebtOut): FormState {
  if (!d) return EMPTY;
  return {
    bank: d.bank_name,
    amount: d.total_amount ? Number(d.total_amount).toString() : "",
    rate: d.interest_rate ? Number(d.interest_rate).toString() : "",
    min: d.minimum_payment ? Number(d.minimum_payment).toString() : "",
  };
}

export default function DebtFormSheet({ isVisible, debt, onClose }: Props) {
  const sheetRef = useRef<BottomSheet>(null);
  const snapPoints = useMemo(() => ["80%"], []);
  const [form, setForm] = useState<FormState>(fromDebt(debt));
  const isEdit = !!debt;

  useEffect(() => {
    setForm(fromDebt(debt));
  }, [debt]);

  useEffect(() => {
    if (isVisible) sheetRef.current?.expand();
    else sheetRef.current?.close();
  }, [isVisible]);

  const createMut = useCreateDebt();
  const updateMut = useUpdateDebt();
  const deleteMut = useDeleteDebt();
  const busy = createMut.isPending || updateMut.isPending || deleteMut.isPending;

  function buildPayload(): DebtPayload | null {
    const bank = form.bank.trim();
    const amount = parseCOP(form.amount);
    if (bank.length === 0) {
      Alert.alert("Falta el banco", "El nombre del banco es obligatorio.");
      return null;
    }
    if (amount <= 0) {
      Alert.alert("Monto inválido", "El monto debe ser mayor a 0.");
      return null;
    }
    const rate = form.rate.trim() === "" ? null : Number(form.rate.replace(",", "."));
    const min = form.min.trim() === "" ? null : parseCOP(form.min);
    return {
      bank_name: bank,
      total_amount: amount.toString(),
      interest_rate: rate !== null && !Number.isNaN(rate) ? rate.toString() : null,
      minimum_payment: min !== null ? min.toString() : null,
    };
  }

  function handleSave() {
    const payload = buildPayload();
    if (!payload) return;
    Keyboard.dismiss();
    const onError = (e: unknown) => {
      const message = e instanceof Error ? e.message : "Error al guardar.";
      Alert.alert("Error", message);
    };
    if (isEdit && debt) {
      updateMut.mutate(
        { id: debt.id, payload },
        { onSuccess: onClose, onError },
      );
    } else {
      createMut.mutate(payload, { onSuccess: onClose, onError });
    }
  }

  function handleDelete() {
    if (!debt) return;
    Alert.alert(
      "Eliminar deuda",
      `¿Eliminar la deuda con ${debt.bank_name}?`,
      [
        { text: "Cancelar", style: "cancel" },
        {
          text: "Eliminar",
          style: "destructive",
          onPress: () =>
            deleteMut.mutate(debt.id, {
              onSuccess: onClose,
              onError: (e) =>
                Alert.alert("Error", e instanceof Error ? e.message : "Error al eliminar."),
            }),
        },
      ],
    );
  }

  return (
    <BottomSheet
      ref={sheetRef}
      index={-1}
      snapPoints={snapPoints}
      enablePanDownToClose
      onClose={onClose}
      backgroundStyle={styles.bg}
      handleIndicatorStyle={styles.handle}
    >
      <BottomSheetView style={styles.body}>
        <Text style={styles.title}>{isEdit ? "Editar deuda" : "Nueva deuda"}</Text>

        <Field label="Banco / Entidad">
          <BottomSheetTextInput
            style={styles.input}
            placeholder="p.ej. Falabella"
            placeholderTextColor={colors.textSecondary}
            value={form.bank}
            onChangeText={(v) => setForm((f) => ({ ...f, bank: v }))}
            autoCapitalize="words"
          />
        </Field>

        <Field label="Monto total (COP)">
          <BottomSheetTextInput
            style={styles.input}
            placeholder="0"
            placeholderTextColor={colors.textSecondary}
            value={form.amount}
            onChangeText={(v) => setForm((f) => ({ ...f, amount: v }))}
            keyboardType="numeric"
          />
        </Field>

        <Field label="Tasa interés % EA">
          <BottomSheetTextInput
            style={styles.input}
            placeholder="0"
            placeholderTextColor={colors.textSecondary}
            value={form.rate}
            onChangeText={(v) => setForm((f) => ({ ...f, rate: v }))}
            keyboardType="decimal-pad"
          />
        </Field>

        <Field label="Pago mínimo mensual (COP)">
          <BottomSheetTextInput
            style={styles.input}
            placeholder="0"
            placeholderTextColor={colors.textSecondary}
            value={form.min}
            onChangeText={(v) => setForm((f) => ({ ...f, min: v }))}
            keyboardType="numeric"
          />
        </Field>

        <Pressable
          style={[styles.saveBtn, busy && { opacity: 0.5 }]}
          disabled={busy}
          onPress={handleSave}
        >
          <Text style={styles.saveText}>{busy ? "Guardando..." : "Guardar"}</Text>
        </Pressable>

        {isEdit ? (
          <Pressable style={styles.deleteBtn} disabled={busy} onPress={handleDelete}>
            <Text style={styles.deleteText}>Eliminar deuda</Text>
          </Pressable>
        ) : null}
      </BottomSheetView>
    </BottomSheet>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  bg: { backgroundColor: colors.surface },
  handle: { backgroundColor: colors.border },
  body: { padding: 16, gap: 4 },
  title: { color: colors.textPrimary, fontSize: 16, fontWeight: "600", marginBottom: 8 },
  field: { marginBottom: 12 },
  label: {
    color: colors.textSecondary,
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  input: {
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    padding: 12,
    fontSize: 14,
    color: colors.textPrimary,
  },
  saveBtn: {
    backgroundColor: colors.primary,
    padding: 14,
    borderRadius: 8,
    alignItems: "center",
    marginTop: 8,
  },
  saveText: { color: "#fff", fontWeight: "600", fontSize: 14 },
  deleteBtn: {
    borderWidth: 1,
    borderColor: colors.danger,
    padding: 12,
    borderRadius: 8,
    alignItems: "center",
    marginTop: 12,
  },
  deleteText: { color: colors.danger, fontWeight: "600", fontSize: 13 },
});
```

- [ ] **Step 2: Typecheck**

Run: `npx tsc --noEmit` from `mobile/`. Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add mobile/src/components/DebtFormSheet.tsx
git commit -m "feat(mobile): add DebtFormSheet bottom sheet for create/edit/delete"
```

---

### Task 7: DebtTrackerScreen (rewrite)

**Files:**
- Modify: `mobile/src/screens/DebtTrackerScreen.tsx` (full rewrite)

- [ ] **Step 1: Replace file with full implementation**

```tsx
// mobile/src/screens/DebtTrackerScreen.tsx
import { useMemo, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";

import DebtCard from "../components/DebtCard";
import DebtFormSheet from "../components/DebtFormSheet";
import MoneyText from "../components/MoneyText";
import { useDebts, type DebtOut } from "../services/queries/debts";
import { colors } from "../theme/colors";

export default function DebtTrackerScreen() {
  const { data, isLoading, isError, refetch, isRefetching } = useDebts();
  const [sheetOpen, setSheetOpen] = useState(false);
  const [editing, setEditing] = useState<DebtOut | undefined>(undefined);

  const { totalDebt, totalMin, count } = useMemo(() => {
    const list = data ?? [];
    return {
      totalDebt: list.reduce((s, d) => s + Number(d.total_amount || 0), 0),
      totalMin: list.reduce((s, d) => s + Number(d.minimum_payment || 0), 0),
      count: list.length,
    };
  }, [data]);

  function openCreate() {
    setEditing(undefined);
    setSheetOpen(true);
  }

  function openEdit(debt: DebtOut) {
    setEditing(debt);
    setSheetOpen(true);
  }

  if (isLoading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  if (isError) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>No pudimos cargar tus deudas.</Text>
        <Pressable style={styles.retryBtn} onPress={() => refetch()}>
          <Text style={styles.retryText}>Reintentar</Text>
        </Pressable>
      </View>
    );
  }

  const debts = data ?? [];

  return (
    <View style={styles.root}>
      <FlatList
        data={debts}
        keyExtractor={(d) => d.id}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={isRefetching}
            onRefresh={refetch}
            tintColor={colors.primary}
          />
        }
        ListHeaderComponent={
          <View style={styles.hero}>
            <Text style={styles.heroLabel}>DEUDA TOTAL</Text>
            <MoneyText value={totalDebt} size="xl" style={styles.heroMoney} />
            <Text style={styles.heroSub}>
              {count} {count === 1 ? "deuda" : "deudas"} · pago mínimo {" "}
              <MoneyText value={totalMin} size="sm" style={styles.heroSubMoney} />
              /mes
            </Text>
          </View>
        }
        ListEmptyComponent={
          <View style={styles.emptyBox}>
            <Text style={styles.emptyEmoji}>🎉</Text>
            <Text style={styles.emptyText}>Sin deudas registradas</Text>
            <Pressable style={styles.emptyBtn} onPress={openCreate}>
              <Text style={styles.emptyBtnText}>Agregar primera deuda</Text>
            </Pressable>
          </View>
        }
        renderItem={({ item }) => <DebtCard debt={item} onPress={openEdit} />}
      />

      {debts.length > 0 ? (
        <Pressable style={styles.fab} onPress={openCreate}>
          <Text style={styles.fabPlus}>+</Text>
        </Pressable>
      ) : null}

      <DebtFormSheet
        isVisible={sheetOpen}
        debt={editing}
        onClose={() => {
          setSheetOpen(false);
          setEditing(undefined);
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  centered: {
    flex: 1,
    backgroundColor: colors.background,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
    gap: 12,
  },
  errorText: { color: colors.textSecondary, fontSize: 14 },
  retryBtn: {
    backgroundColor: colors.primary,
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
  },
  retryText: { color: "#fff", fontWeight: "600" },
  list: { padding: 16, paddingBottom: 96 },
  hero: {
    backgroundColor: colors.danger,
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
  },
  heroLabel: {
    color: "rgba(255,255,255,0.75)",
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  heroMoney: { color: "#fff", marginTop: 4 },
  heroSub: { color: "rgba(255,255,255,0.75)", fontSize: 11, marginTop: 6 },
  heroSubMoney: { color: "#fff", fontWeight: "600" },
  emptyBox: { alignItems: "center", paddingVertical: 40, gap: 12 },
  emptyEmoji: { fontSize: 40 },
  emptyText: { color: colors.textSecondary, fontSize: 14 },
  emptyBtn: {
    marginTop: 8,
    backgroundColor: colors.primary,
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 8,
  },
  emptyBtnText: { color: "#fff", fontWeight: "600", fontSize: 14 },
  fab: {
    position: "absolute",
    right: 16,
    bottom: 24,
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 6,
  },
  fabPlus: { color: "#fff", fontSize: 28, fontWeight: "300", marginTop: -2 },
});
```

- [ ] **Step 2: Typecheck**

Run: `npx tsc --noEmit` from `mobile/`. Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add mobile/src/screens/DebtTrackerScreen.tsx
git commit -m "feat(mobile): rewrite DebtTrackerScreen with CRUD via bottom sheet"
```

---

### Task 8: TrendChart wrapper + DashboardScreen

**Files:**
- Create: `mobile/src/components/TrendChart.tsx`
- Modify: `mobile/src/screens/DashboardScreen.tsx` (full rewrite)

- [ ] **Step 1: Create `TrendChart.tsx`**

```tsx
// mobile/src/components/TrendChart.tsx
import { Dimensions } from "react-native";
import { BarChart } from "react-native-chart-kit";

import { colors } from "../theme/colors";

type Props = {
  months: string[];        // ["2026-02", ..., "2026-07"]
  totals: number[];        // aligned with months
};

const chartConfig = {
  backgroundGradientFrom: colors.surface,
  backgroundGradientTo: colors.surface,
  decimalPlaces: 0,
  color: (opacity = 1) => `rgba(91, 141, 239, ${opacity})`,
  labelColor: (opacity = 1) => `rgba(163, 168, 179, ${opacity})`,
  propsForBackgroundLines: { stroke: colors.border },
  barPercentage: 0.6,
};

const MES_ABREV = [
  "ene","feb","mar","abr","may","jun",
  "jul","ago","sep","oct","nov","dic",
];

function labelOf(yyyymm: string): string {
  const m = Number(yyyymm.split("-")[1]);
  return MES_ABREV[m - 1] ?? yyyymm;
}

export default function TrendChart({ months, totals }: Props) {
  const width = Dimensions.get("window").width - 32;
  return (
    <BarChart
      data={{
        labels: months.map(labelOf),
        datasets: [{ data: totals.length > 0 ? totals : [0] }],
      }}
      width={width}
      height={200}
      chartConfig={chartConfig}
      fromZero
      showValuesOnTopOfBars={false}
      withInnerLines
      yAxisLabel=""
      yAxisSuffix=""
      style={{ borderRadius: 12 }}
    />
  );
}
```

- [ ] **Step 2: Rewrite `DashboardScreen.tsx`**

```tsx
// mobile/src/screens/DashboardScreen.tsx
import { useMemo } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import CategoryIcon from "../components/CategoryIcon";
import MoneyText from "../components/MoneyText";
import TrendChart from "../components/TrendChart";
import { useDashboard, type DashboardResponse } from "../services/queries/dashboard";
import { colors } from "../theme/colors";
import { getCategory } from "../utils/categories";
import { humanizeMonth } from "../utils/dates";

export default function DashboardScreen() {
  const { data, isLoading, isError, refetch, isRefetching } = useDashboard();

  if (isLoading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  if (isError || !data) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>No pudimos cargar el dashboard.</Text>
        <Pressable style={styles.retryBtn} onPress={() => refetch()}>
          <Text style={styles.retryText}>Reintentar</Text>
        </Pressable>
      </View>
    );
  }

  return <DashboardContent data={data} refetch={refetch} isRefetching={isRefetching} />;
}

function DashboardContent({
  data,
  refetch,
  isRefetching,
}: {
  data: DashboardResponse;
  refetch: () => void;
  isRefetching: boolean;
}) {
  const { current_month, debts, monthly_trend } = data;

  const sortedCategories = useMemo(() => {
    return [...current_month.by_category].sort(
      (a, b) => Number(b.total) - Number(a.total),
    );
  }, [current_month.by_category]);

  const trendMonths = monthly_trend.map((m) => m.month);
  const trendTotals = monthly_trend.map((m) => Number(m.total_spent));

  return (
    <ScrollView
      style={styles.root}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl
          refreshing={isRefetching}
          onRefresh={refetch}
          tintColor={colors.primary}
        />
      }
    >
      {/* Dual hero */}
      <View style={styles.heroRow}>
        <View style={[styles.hero, styles.heroSpend]}>
          <Text style={styles.heroLabel}>Gastado en {humanizeMonth(current_month.month)}</Text>
          <MoneyText value={current_month.total_spent} size="lg" />
          <Text style={styles.heroMeta}>
            {current_month.transaction_count} transacciones
          </Text>
        </View>
        <View style={[styles.hero, styles.heroDebt]}>
          <Text style={styles.heroLabel}>Deuda total</Text>
          {debts.debt_count === 0 ? (
            <Text style={styles.noDebt}>Sin deudas</Text>
          ) : (
            <>
              <MoneyText value={debts.total_debt} size="lg" />
              <Text style={styles.heroMeta}>
                {debts.debt_count} · mín <MoneyText value={debts.total_minimum_payment} size="sm" style={{ color: colors.textSecondary, fontWeight: "600" }} />/mes
              </Text>
            </>
          )}
        </View>
      </View>

      {/* Trend */}
      <Text style={styles.sectionLabel}>Tendencia 6 meses</Text>
      <TrendChart months={trendMonths} totals={trendTotals} />

      {/* Categories */}
      <Text style={styles.sectionLabel}>Por categoría</Text>
      {sortedCategories.length === 0 ? (
        <Text style={styles.emptyCat}>Sin gastos este mes</Text>
      ) : (
        sortedCategories.map((c, i) => {
          const cat = getCategory(c.category);
          return (
            <View key={`${c.category ?? "null"}-${i}`} style={styles.catRow}>
              <CategoryIcon categoryKey={c.category} />
              <View style={styles.catBody}>
                <Text style={styles.catLabel}>{cat.label}</Text>
                <Text style={styles.catCount}>{c.count} {c.count === 1 ? "tx" : "txs"}</Text>
              </View>
              <MoneyText value={c.total} size="md" />
            </View>
          );
        })
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  content: { padding: 16, paddingBottom: 32 },
  centered: {
    flex: 1,
    backgroundColor: colors.background,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
    gap: 12,
  },
  errorText: { color: colors.textSecondary, fontSize: 14 },
  retryBtn: {
    backgroundColor: colors.primary,
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
  },
  retryText: { color: "#fff", fontWeight: "600" },
  heroRow: { flexDirection: "row", gap: 8, marginBottom: 16 },
  hero: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 14,
  },
  heroSpend: {},
  heroDebt: { borderLeftWidth: 3, borderLeftColor: colors.danger },
  heroLabel: {
    color: colors.textSecondary,
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  heroMeta: { color: colors.textSecondary, fontSize: 11, marginTop: 4 },
  noDebt: { color: colors.success, fontSize: 16, fontWeight: "700", marginTop: 4 },
  sectionLabel: {
    color: colors.textSecondary,
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginTop: 20,
    marginBottom: 8,
  },
  catRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 12,
    marginBottom: 6,
    gap: 12,
  },
  catBody: { flex: 1 },
  catLabel: { color: colors.textPrimary, fontSize: 14, fontWeight: "600" },
  catCount: { color: colors.textSecondary, fontSize: 11, marginTop: 2 },
  emptyCat: { color: colors.textSecondary, fontSize: 13, padding: 16, textAlign: "center" },
});
```

- [ ] **Step 3: Typecheck**

Run: `npx tsc --noEmit` from `mobile/`. Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add mobile/src/components/TrendChart.tsx mobile/src/screens/DashboardScreen.tsx
git commit -m "feat(mobile): rewrite DashboardScreen with dual hero + trend chart"
```

---

### Task 9: TransactionsScreen (rewrite)

**Files:**
- Modify: `mobile/src/screens/TransactionsScreen.tsx` (full rewrite)

- [ ] **Step 1: Rewrite `TransactionsScreen.tsx`**

```tsx
// mobile/src/screens/TransactionsScreen.tsx
import { useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  SectionList,
  StyleSheet,
  Text,
  View,
} from "react-native";

import TransactionRow from "../components/TransactionRow";
import {
  useTransactions,
  type TransactionOut,
} from "../services/queries/transactions";
import { colors } from "../theme/colors";
import { CATEGORIES } from "../utils/categories";
import {
  currentMonthYYYYMM,
  dayKey,
  formatDayHeader,
  humanizeMonth,
  shiftMonth,
} from "../utils/dates";

type Section = { title: string; sortKey: string; data: TransactionOut[] };

const FILTERABLE = CATEGORIES.filter(
  (c) => !["transfer", "cash_withdrawal"].includes(c.key),
);

export default function TransactionsScreen() {
  const [month, setMonth] = useState<string>(currentMonthYYYYMM());
  const [category, setCategory] = useState<string | null>(null);

  const query = useTransactions({ month, category, limit: 200 });

  const sections: Section[] = useMemo(() => {
    const items = query.data?.items ?? [];
    const map = new Map<string, TransactionOut[]>();
    for (const tx of items) {
      const key = dayKey(tx.occurred_at);
      const bucket = map.get(key) ?? [];
      bucket.push(tx);
      map.set(key, bucket);
    }
    const result: Section[] = [];
    for (const [key, data] of map.entries()) {
      const first = data[0];
      result.push({ title: formatDayHeader(first.occurred_at), sortKey: key, data });
    }
    result.sort((a, b) => b.sortKey.localeCompare(a.sortKey));
    return result;
  }, [query.data]);

  return (
    <View style={styles.root}>
      <View style={styles.header}>
        <Pressable onPress={() => setMonth((m) => shiftMonth(m, -1))} hitSlop={12}>
          <Text style={styles.navArrow}>‹</Text>
        </Pressable>
        <Text style={styles.headerTitle}>{humanizeMonth(month)}</Text>
        <Pressable onPress={() => setMonth((m) => shiftMonth(m, +1))} hitSlop={12}>
          <Text style={styles.navArrow}>›</Text>
        </Pressable>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.chipsRow}
      >
        <Chip label="Todas" active={category === null} onPress={() => setCategory(null)} />
        {FILTERABLE.map((c) => (
          <Chip
            key={c.key}
            label={c.label}
            active={category === c.key}
            onPress={() => setCategory(c.key)}
          />
        ))}
      </ScrollView>

      {query.isLoading ? (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      ) : query.isError ? (
        <View style={styles.centered}>
          <Text style={styles.errorText}>No pudimos cargar las transacciones.</Text>
          <Pressable style={styles.retryBtn} onPress={() => query.refetch()}>
            <Text style={styles.retryText}>Reintentar</Text>
          </Pressable>
        </View>
      ) : sections.length === 0 ? (
        <View style={styles.centered}>
          <Text style={styles.emptyText}>Sin transacciones en este período</Text>
        </View>
      ) : (
        <SectionList
          sections={sections}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl
              refreshing={query.isRefetching}
              onRefresh={query.refetch}
              tintColor={colors.primary}
            />
          }
          renderSectionHeader={({ section }) => (
            <Text style={styles.sectionHeader}>{section.title}</Text>
          )}
          renderItem={({ item }) => (
            <TransactionRow
              merchant={item.merchant}
              category={item.category}
              amount={item.amount}
              type={item.transaction_type}
            />
          )}
        />
      )}
    </View>
  );
}

function Chip({
  label,
  active,
  onPress,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={[styles.chip, active && styles.chipActive]}
    >
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 24,
    paddingTop: 12,
    paddingBottom: 8,
  },
  navArrow: { color: colors.primary, fontSize: 24, paddingHorizontal: 8 },
  headerTitle: { color: colors.textPrimary, fontSize: 15, fontWeight: "600" },
  chipsRow: { paddingHorizontal: 16, paddingBottom: 8, gap: 8 },
  chip: {
    backgroundColor: colors.surfaceMuted,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 14,
  },
  chipActive: { backgroundColor: colors.primary },
  chipText: { color: colors.textSecondary, fontSize: 11 },
  chipTextActive: { color: "#fff", fontWeight: "600" },
  centered: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
    gap: 12,
  },
  errorText: { color: colors.textSecondary, fontSize: 14 },
  emptyText: { color: colors.textSecondary, fontSize: 14 },
  retryBtn: {
    backgroundColor: colors.primary,
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
  },
  retryText: { color: "#fff", fontWeight: "600" },
  listContent: { padding: 16, paddingBottom: 32 },
  sectionHeader: {
    color: colors.textSecondary,
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginTop: 12,
    marginBottom: 6,
  },
});
```

- [ ] **Step 2: Typecheck**

Run: `npx tsc --noEmit` from `mobile/`. Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add mobile/src/screens/TransactionsScreen.tsx
git commit -m "feat(mobile): rewrite TransactionsScreen with month nav + category chips + day sections"
```

---

### Task 10: End-to-end verification (manual walkthrough)

**Files:** none (verification only)

- [ ] **Step 1: Final typecheck**

Run from `mobile/`:
```bash
npx tsc --noEmit
```
Expected: exit 0.

- [ ] **Step 2: Start backend + start Expo**

If not already running:
```bash
docker compose up -d db backend
cd mobile && npx expo start --clear
```

- [ ] **Step 3: Manual walkthrough (Expo device via ngrok, or web)**

Verify each step below. If anything fails, do NOT proceed — fix and re-verify.

1. Login flow works and lands on `Dashboard`.
2. `Dashboard`:
   - Both hero cards render with data.
   - If backend has no debts, right hero shows "Sin deudas" in green.
   - Trend chart renders 6 months (may be zeros).
   - Categories list ordered desc by total.
   - Pull down → spinner appears → data refetches.
3. Tap `Transactions` tab:
   - Month header shows current month.
   - `‹` / `›` shift the month; data refetches with the new month.
   - Chips filter by category (tap "Comida", list updates).
   - Sections grouped by day: today = "Hoy", yesterday = "Ayer".
   - Income rows (credit) show green amount with `+` prefix.
   - Empty period shows "Sin transacciones en este período".
4. Tap `Debts` tab:
   - Empty state renders with CTA if no debts.
   - Tap CTA (or FAB) → bottom sheet opens at 80% height.
5. Create a debt in the sheet:
   - Enter "Falabella", "5200000", "32.5", "280000" → "Guardar".
   - Sheet closes. Card appears in the list.
   - Hero total updates.
   - Switch to `Dashboard` — right hero total updates too (cross-screen invalidation confirmed).
6. Tap the debt card → sheet opens in edit mode with values prefilled.
   - Change monto to "5100000" → "Guardar" → sheet closes, card updates.
7. Tap card → "Eliminar deuda" → confirm alert → yes → card disappears, hero updates.
8. Force an error (e.g., stop backend) → pull-to-refresh on any screen → red error message + "Reintentar" button appears. Restart backend → retry → succeeds.

- [ ] **Step 4: Commit any last polish fixes (if any)**

If manual verification uncovered small fixes:
```bash
git add <changed-files>
git commit -m "fix(mobile): <specific issue>"
```

If everything passes without changes, no commit here.

---

## Verification summary

- Task 1–9: `npx tsc --noEmit` from `mobile/` exits 0 after each task.
- Task 10: full manual walkthrough passes on device.

## Risks + rollback

- **Reanimated plugin missing**: if bottom sheet renders empty, verify `mobile/babel.config.js` has `react-native-reanimated/plugin` as the last plugin, then restart with `npx expo start --clear`.
- **Category key mismatch**: if the backend emits a key not in `CATEGORIES`, `getCategory` returns fallback `{ label: <key>, emoji: 📦 }`. UI still renders — visual regression only. Fix by adding the key to `mobile/src/utils/categories.ts`.
- **Chart-kit + SVG install**: on Expo managed workflow, `npx expo install react-native-svg` picks the SDK-compatible version. If `react-native-chart-kit` errors, verify the peer versions with `npx expo doctor`.
- **Rollback per task**: each task is a single commit. `git revert <hash>` cleanly rolls back an individual task.
