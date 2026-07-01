# Mobile screens — Dashboard, Transactions, DebtTracker

**Date:** 2026-07-01
**Sprint:** 4 (Fase 1 — MVP)
**Scope:** Reemplaza los 3 stubs de pantalla con implementaciones que consumen los endpoints del backend ya existentes (`GET /dashboard`, `GET /transactions`, `GET/POST/PATCH/DELETE /debts`).

## Context

Backend Sprint 4 ya expone `/dashboard` (trend 6 meses + snapshot mes + resumen deudas) y CRUD completo de `/debts`. `DashboardScreen`, `TransactionsScreen` y `DebtTrackerScreen` son stubs con texto placeholder. Este spec cubre el frontend completo de esas 3 pantallas.

Cron sync y transfer matcher (los otros dos ítems de Sprint 4) quedan fuera de este spec — se abordarán después.

## Design decisions (settled)

| # | Decisión | Elegido |
|---|----------|---------|
| 1 | Charts | `react-native-chart-kit` |
| 2 | Layout Dashboard | Dual hero (gasto + deuda side-by-side) + trend + categorías |
| 3 | Layout Transactions | SectionList agrupado por día + chips categorías + nav mes |
| 4 | Layout DebtTracker | Hero degradado + lista + FAB |
| 5 | Add/edit debt | Bottom sheet (`@gorhom/bottom-sheet`) |
| 6 | Data fetching | `@tanstack/react-query` |
| 7 | Currency | Full COP (`Intl.NumberFormat('es-CO')` → `$1.234.567`) |
| 8 | Iconos categoría | Emoji |

## New dependencies

```
@tanstack/react-query
react-native-chart-kit
react-native-svg
@gorhom/bottom-sheet
react-native-reanimated
react-native-gesture-handler
```

`react-native-reanimated` requiere plugin en `babel.config.js`. Si falta, `@gorhom/bottom-sheet` no renderiza.

## Structure

```
mobile/src/
├── services/
│   ├── api.ts                     [existente]
│   └── queries/
│       ├── dashboard.ts           useDashboard()
│       ├── transactions.ts        useTransactions({ month, category, type })
│       └── debts.ts               useDebts(), useCreateDebt(), useUpdateDebt(), useDeleteDebt()
├── screens/
│   ├── DashboardScreen.tsx        [reescribir]
│   ├── TransactionsScreen.tsx    [reescribir]
│   └── DebtTrackerScreen.tsx     [reescribir]
├── components/
│   ├── MoneyText.tsx              formato COP compartido
│   ├── CategoryIcon.tsx           map categoría → emoji + fondo
│   ├── TransactionRow.tsx         row reutilizable (emoji + merchant + amt)
│   ├── DebtCard.tsx               card lista deudas
│   ├── DebtFormSheet.tsx          bottom sheet create/edit
│   └── TrendChart.tsx             wrapper de BarChart de chart-kit
└── utils/
    ├── currency.ts                formatCOP, parseCOP
    ├── categories.ts              [{ key, label, emoji }]
    └── dates.ts                   formatDayHeader (hoy/ayer/DD mes)
```

## API contracts (from backend)

### `GET /dashboard`
```typescript
type DashboardResponse = {
  monthly_trend: Array<{
    month: string;              // "2026-07"
    total_spent: string;        // decimal as string
    by_category: Array<{ category: string | null; total: string; count: number }>;
  }>;
  current_month: {
    month: string;
    total_spent: string;
    by_category: Array<{ category: string | null; total: string; count: number }>;
    transaction_count: number;
  };
  debts: {
    total_debt: string;
    total_minimum_payment: string;
    debt_count: number;
  };
};
```

### `GET /transactions?month=YYYY-MM&category=X&type=debit|credit&limit=100&offset=0`
```typescript
type TransactionListResponse = {
  items: Array<TransactionOut>;
  total: number;
  limit: number;
  offset: number;
};
type TransactionOut = {
  id: string;
  amount: string;
  merchant: string | null;
  category: string | null;
  transaction_type: "debit" | "credit";
  currency: string;              // "COP"
  card_last_digits: string | null;
  occurred_at: string;           // ISO
};
```

### `GET /debts`
```typescript
type DebtOut = {
  id: string;
  bank_name: string;
  total_amount: string;
  interest_rate: string | null;
  minimum_payment: string | null;
  created_at: string;
};
```

### `POST /debts` / `PATCH /debts/{id}` / `DELETE /debts/{id}`
Body para POST/PATCH:
```typescript
type DebtCreate = { bank_name: string; total_amount: string; interest_rate?: string; minimum_payment?: string };
type DebtUpdate = Partial<DebtCreate>;
```

## Screens

### DashboardScreen

**Data:** `useDashboard()` → `GET /dashboard`

**Layout (Dual hero):**
1. Row de 2 cards lado a lado:
   - **Izquierda**: label "Gastado en {mes}" + `MoneyText` total_spent + "142 transacciones"
   - **Derecha**: label "Deuda total" + `MoneyText` total_debt + "{n} deudas · mín {total_min}/mes" (borde-izq rojo)
2. Section "Tendencia 6 meses" — `TrendChart` (bar chart, X=mes abrev, Y=total_spent)
3. Section "Por categoría" — lista de current_month.by_category ordenada desc por total, cada row: `<CategoryIcon>` + label + `MoneyText`

**Estados:**
- Loading: `<ActivityIndicator size="large">` centrado
- Error: mensaje + botón "Reintentar" → `refetch()`
- Empty debts: hero derecho muestra "Sin deudas" en verde
- Pull-to-refresh: `RefreshControl` conectado a `refetch()`

### TransactionsScreen

**State local:** `month` (default `current_month_local()`), `category` (default null)

**Data:** `useTransactions({ month, category, limit: 200 })`

**Layout (Agrupado por día):**
1. Header: `‹ Julio 2026 ›` — botones prev/next mes
2. `ScrollView horizontal` con chips: `Todas | Comida | Transporte | Mercado | Salud | Entretenimiento | Otros`. Chip activo con `colors.primary`
3. `SectionList`:
   - Secciones agrupadas por día local (`utils/dates.formatDayHeader`)
   - Header: "Hoy · 1 jul", "Ayer · 30 jun", "28 jun"
   - `renderItem`: `<TransactionRow>` con emoji + merchant + categoría + `<MoneyText>`
   - Ingresos (`transaction_type === "credit"`): amount en verde con prefix `+`

**Estados:**
- Loading, error, empty ("Sin transacciones en este período"), pull-to-refresh

### DebtTrackerScreen

**Data:** `useDebts()`

**Layout (Hero + FAB):**
1. Hero card con gradient rojo → azul:
   - Label "Deuda total"
   - `MoneyText` total (sum de `total_amount`)
   - Subtítulo: "{count} deudas · pago mínimo {sum(minimum_payment)}/mes"
2. Lista de `<DebtCard>`. Cada card:
   - Border-left rojo 3px
   - `bank_name` + chip pill con `interest_rate`% EA
   - Meta: "Pago mín: {minimum_payment}"
   - `<MoneyText>` derecha con `total_amount`
   - Tap → abre `DebtFormSheet` en modo edit con esa deuda
3. FAB `+` flotante bottom-right (44×44, primary, box-shadow) → abre `DebtFormSheet` en modo create

**Empty state:** ilustración/emoji + "Sin deudas registradas" + botón "Agregar primera deuda"

### DebtFormSheet

**Props:** `{ isVisible: boolean; debt?: DebtOut; onClose: () => void }`

**Layout (bottom sheet 80% max-height):**
- Handle bar arriba
- Título: "Nueva deuda" o "Editar deuda"
- Fields:
  - Banco / Entidad (TextInput, required, min 1 char)
  - Monto total (TextInput numeric COP)
  - Tasa interés % EA (TextInput numeric)
  - Pago mínimo mensual (TextInput numeric COP)
- Botón "Guardar" (primary, full-width)
- Si `debt` está definido: botón "Eliminar deuda" outline rojo abajo, con `Alert.alert` de confirmación

**Mutations:**
- Create: `useCreateDebt().mutate(payload)` → invalida `['debts']` + `['dashboard']` → `onClose()`
- Update: `useUpdateDebt().mutate({ id, payload })` → mismas invalidaciones
- Delete: `useDeleteDebt().mutate(id)` → mismas invalidaciones

## Cross-screen refresh

| Acción | Invalida query keys |
|---|---|
| Create/patch/delete debt | `['debts']`, `['dashboard']` |
| (Futuro, no incluido) Gmail sync | `['dashboard']`, `['transactions']` |

## React Query config

En `App.tsx`, wrap con `QueryClientProvider`:

```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 60_000,
      refetchOnWindowFocus: false,
    },
  },
});
```

Wrap raíz también en `GestureHandlerRootView` (requerido por gorhom).

## Utilities

### `utils/currency.ts`

```typescript
const cop = new Intl.NumberFormat('es-CO', {
  style: 'currency', currency: 'COP', maximumFractionDigits: 0,
});
export const formatCOP = (n: number | string) => cop.format(typeof n === 'string' ? Number(n) : n);
export const parseCOP = (s: string): number => Number(s.replace(/[^\d]/g, ''));
```

### `utils/categories.ts`

```typescript
export type CategoryDef = { key: string; label: string; emoji: string };
export const CATEGORIES: CategoryDef[] = [
  { key: 'food', label: 'Comida', emoji: '🍽' },
  { key: 'transport', label: 'Transporte', emoji: '🚗' },
  { key: 'grocery', label: 'Mercado', emoji: '🛒' },
  { key: 'health', label: 'Salud', emoji: '🏥' },
  { key: 'entertainment', label: 'Entretenimiento', emoji: '🎬' },
  { key: 'income', label: 'Ingreso', emoji: '💰' },
  { key: 'transfer', label: 'Transferencia', emoji: '↔' },
  { key: 'cash_withdrawal', label: 'Retiro', emoji: '💵' },
  { key: 'other', label: 'Otros', emoji: '📦' },
];
```

Las keys deben coincidir con las que devuelve el backend (revisar `app/services/categorizer.py` durante implementación).

## Error handling

- Axios interceptor ya maneja 401 refresh (`services/api.ts`)
- Errores de query: bandera `isError` en cada hook → mostrar mensaje + retry button
- Errores de mutation: `Alert.alert("Error", err.message)` — no cerrar sheet en error
- Bottom sheet cerrado con swipe: descarta cambios sin confirm (form corto, riesgo bajo)

## Testing

**Sin infra de tests JS en mobile actualmente. YAGNI para este sprint.** Verificación:

1. `cd mobile && npx tsc --noEmit` — typecheck
2. Manual walkthrough en Expo device (ngrok):
   - Login → Dashboard carga con datos
   - Tab Transactions → filtra por mes, filtra por categoría, agrupa por día
   - Tab Debts → lista vacía muestra empty state
   - FAB → sheet abre → crea deuda → sheet cierra → lista actualiza → Dashboard hero derecho actualiza
   - Tap deuda → sheet en edit → cambiar campo → save → refresca
   - Tap deuda → sheet edit → eliminar → confirm → desaparece → hero actualiza

Testing infra (Jest + RNTL) queda pendiente para sprint posterior si se justifica.

## Order of implementation

1. Setup: instalar 6 deps, wrap `App.tsx` (QueryClientProvider + GestureHandlerRootView), configurar reanimated babel plugin
2. Utils base: `currency.ts`, `categories.ts`, `dates.ts`, `MoneyText.tsx`, `CategoryIcon.tsx`
3. Query hooks: `queries/dashboard.ts`, `queries/transactions.ts`, `queries/debts.ts` con tipos
4. DebtTracker + DebtFormSheet (feature end-to-end incluye mutations)
5. Dashboard (`TrendChart` wrapper + dual hero + categoría list)
6. Transactions (SectionList + month nav + category chips)
7. Verificación: `npx tsc --noEmit` + walkthrough manual en Expo

## Risks

- **Reanimated babel plugin**: si no está en `babel.config.js`, sheet no renderiza. Docs: gorhom migration guide.
- **`react-native-svg` en Expo managed**: `expo install react-native-svg` maneja la versión compatible con SDK.
- **Category keys backend vs frontend**: si el catálogo de `categorizer.py` cambia, hay que sincronizar `categories.ts`. Fallback: si backend devuelve key no mapeada → mostrar emoji `📦` y label = key.
- **Decimal como string en JSON**: backend usa `Decimal` que Pydantic serializa como string. Los helpers `formatCOP` y `parseCOP` deben aceptar `string | number`.

## Out of scope

- Cron sync automático (Sprint 4 pero separado)
- Transfer matcher (Sprint 4 pero separado)
- Jest / RNTL tests
- Skeleton loading screens
- Estrategia de pago de deudas (Fase 2)
- Presupuesto / alertas por categoría (Fase 2)
