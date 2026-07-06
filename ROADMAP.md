# TrackIt — Roadmap

## Contexto del producto

App personal de finanzas que lee emails bancarios de Gmail, extrae transacciones automáticamente y ayuda al usuario a entender sus gastos, pagar deudas y construir hábitos financieros.

Usuario objetivo: persona con deudas activas, sin claridad de en qué gasta, sin sistema de ahorro.

Stack: FastAPI + PostgreSQL (backend) · React Native + Expo (mobile) · Gmail OAuth

## Estado actual

- [x] Setup mono-repo
- [x] Docker Compose + PostgreSQL
- [x] FastAPI boilerplate
- [x] Google OAuth (login + Gmail)
- [x] Parser de emails Itaú (3 templates: compra, depósito, débito por canal)
- [x] Gmail sync (`POST /gmail/sync` con dedupe por `raw_email_reference`)
- [x] Categorización automática (reglas — IA planeada para Fase 4)
- [x] Backfill CLI (`python -m app.scripts.recategorize`)
- [x] Dashboard mensual (backend `GET /dashboard` + pantalla mobile con dual hero y trend chart)
- [x] Tracker de deudas (backend CRUD `/debts` + pantalla mobile con bottom sheet)
- [x] Pareo de transferencias Itaú → Nequi activo end-to-end (parser Nequi Bre-B + matcher). Daviplata/Falabella pendientes de notificaciones transaccionales reales (ver PARSERS.md)

## Fase 1 — MVP (mes 1) ✅

### Sprint 3 — Parser + Categorización ✅

- [x] Parser modular de emails Itaú Colombia
- [x] Extracción: monto, comercio, fecha, últimos dígitos de tarjeta, tipo (débito/crédito)
- [x] Gmail sync end-to-end con dedupe por `message_id`
- [x] Categorización por reglas (7 categorías iniciales, case+accent-insensitive)
- [x] Backfill CLI para recategorizar filas existentes
- [x] Endpoint GET /transactions con filtros por mes y categoría
- [x] Endpoint GET /transactions/summary

### Sprint 4 — Dashboard + Deudas ✅

- [x] Dashboard backend: `GET /dashboard` — tendencia 6 meses, snapshot mes actual, totales de deuda (3 queries concurrentes)
- [x] CRUD de deudas: banco, monto, tasa de interés, pago mínimo (`GET/POST /debts`, `PATCH/DELETE /debts/{id}`)
- [x] Pantallas mobile: Dashboard, Transactions, DebtTracker (react-query + chart-kit + bottom sheet; ver `docs/superpowers/specs/2026-07-01-mobile-screens-design.md`)
- [x] Sync automático con cron (APScheduler en lifespan, `SYNC_INTERVAL_HOURS`, default 6h)
- [x] Transfer matcher (`app/services/transfer_matcher.py`) + migración `is_pairing_candidate` + `transfer_pair_id` — lado crédito inerte hasta tener parsers de Nequi/Daviplata/Falabella (ver PARSERS.md)

## Fase 2 — Entender patrones (mes 2)

- [ ] Reconciliación con extracto mensual Itaú: parser del email de cierre mensual + job que cruza contra la DB, marca diferencias y agrega lo que solo aparece ahí (intereses, comisiones, cuotas de manejo). Las notificaciones por transacción siguen siendo la fuente de tiempo real; el extracto es backfill autoritativo.
  - [x] Versión CLI manual: `python -m app.scripts.reconcile_statement <csv> --account <n>` — cruza CSV del extracto por (fecha local ±1 día, monto, tipo), inserta faltantes con ref idempotente `statement:*`. CSVs en `backend/statements/` (gitignoreado). Falta: parser automático del email de cierre.
- [x] Presupuesto por categoría con alertas al 80% y 100% — tabla `budgets` (unique user+category), `PUT/DELETE /budgets/{category}` + `GET /budgets/status` (spent/pct/estado por mes local), tab mobile "Presupuesto" con barras de progreso y sheet de edición, badges ⚠️/🔴 en Dashboard. Alertas son in-app; push queda con "Resumen semanal".
- [ ] Detector de suscripciones recurrentes
- [ ] Resumen semanal automático (push notification o email)
- [ ] Estrategia de pago de deudas: modo avalancha vs bola de nieve

## Fase 3 — Construir hábitos (mes 3)

- [ ] Metas de ahorro con fecha y progreso visual
- [ ] Flujo de caja proyectado (ingresos fijos - gastos fijos = disponible)
- [ ] Alertas de gasto inusual (vs promedio histórico por categoría)
- [ ] Score de salud financiera (0-100, sube al pagar deudas y ahorrar)

## Fase 4 — Inteligencia (futuro)

- [ ] Análisis de patrones con IA (Claude API)
- [ ] Soporte para más bancos: Bancolombia, Davivienda, Nu Colombia
- [ ] Reporte mensual exportable en PDF
- [ ] Modo finanzas en pareja (gastos compartidos)

## Principios de ingeniería

- Antes de implementar una feature, verificar que no bloquea features futuras del roadmap
- Parser architecture debe ser extensible (BaseBankParser)
- Nunca guardar credenciales bancarias, solo OAuth tokens encriptados con Fernet
- Mobile-first: toda feature debe tener pantalla en Expo antes de considerarse completa
- Tests para todos los parsers (casos reales de emails)
