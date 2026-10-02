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
- [x] Edición manual de transacciones — `PATCH /transactions/{id}` parcial (categoría y/o nombre/merchant; `null` limpia); mobile: tap en cualquier transacción abre sheet de edición (renombrar + categorizar), refresca barras de presupuesto/dashboard/insights
- [x] Categorías de presupuesto personalizadas — sin tabla nueva: una categoría custom es un slug libre (`^[a-z0-9_]{1,64}$`) que vive en `budgets`/`transactions` que la referencian. Mobile: botón "Agregar categoría" en Presupuesto, aparecen en picker de edición y chips de Movimientos; `getCategory` renderiza fallback (label capitalizado, ícono pricetag). Eliminar el presupuesto de una categoría custom elimina la categoría: sus transacciones vuelven a "Otros" (`category=NULL`); en categorías del sistema solo quita el límite.
- [x] Nota/descripción libre en transacciones — columna `note` (migración `7060b3ffdf44`), editable en el mismo sheet de edición, visible en la fila de Movimientos (itálica, 1 línea)
- [x] Créditos Nequi excluidos de "Recibido" — el parser tagea todo "Recibiste por Bre-B" como `category="transfer"` de entrada (pareado o no); backfill hecho sobre filas existentes sin categoría
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

- [x] Reconciliación con extracto mensual Itaú: parser del email de cierre mensual + job que cruza contra la DB, marca diferencias y agrega lo que solo aparece ahí (intereses, comisiones, cuotas de manejo). Las notificaciones por transacción siguen siendo la fuente de tiempo real; el extracto es backfill autoritativo.
  - [x] Versión CLI manual: `python -m app.scripts.reconcile_statement <csv> --account <n>` — cruza CSV del extracto por (fecha local ±1 día, monto, tipo), inserta faltantes con ref idempotente `statement:*`. CSVs en `backend/statements/` (gitignoreado).
  - [x] Parser automático: `POST /gmail/sync-statements` detecta el email de `extractos@clienteitau.co`, baja el PDF adjunto (protegido con cédula vía `ITAU_STATEMENT_PDF_PASSWORD`), extrae movimientos (`app/parsers/itau_statement.py`) y reconcilia (`app/services/statement_reconciler.py`, compartido con el CLI). Ver "Extracto mensual Itaú" en `PARSERS.md` para gotchas (fuente CID rota en páginas de encabezado, periodo inferido de la fecha del email).
- [x] Presupuesto por categoría con alertas al 80% y 100% — tabla `budgets` (unique user+category), `PUT/DELETE /budgets/{category}` + `GET /budgets/status` (spent/pct/estado por mes local), tab mobile "Presupuesto" con barras de progreso y sheet de edición, badges ⚠️/🔴 en Dashboard. Alertas son in-app; push queda con "Resumen semanal". Sección "Presupuesto del mes" en Dashboard (`BudgetOverview`): barra total + barras por categoría con gastado/límite y %, tap navega al tab Presupuesto.
- [x] Detector de suscripciones recurrentes — `GET /subscriptions` (sin tabla nueva, calculado al vuelo como `/dashboard`): agrupa por comercio normalizado, clusteriza por monto (±10%) y detecta cadencia (semanal/quincenal/mensual/anual) solo si todos los gaps entre ocurrencias caen en la misma ventana (`app/services/subscription_detector.py`, lógica pura testeada). Tab mobile "Suscripciones" con total mensualizado estimado y próximo cobro por comercio.
- [x] Resumen semanal automático (email) — cron `CronTrigger` lunes 8am hora local (`app/services/scheduler.py::send_weekly_summaries_job`), envía por usuario el resumen de la semana Mon-Sun anterior (gastado, recibido, breakdown por categoría) vía Resend (`app/services/email_sender.py`). Sin tabla nueva — se calcula al vuelo igual que dashboard/subscriptions. Salta usuarios sin actividad en la semana (no manda email vacío). Requiere `RESEND_API_KEY` en `.env`.
- [x] Estrategia de pago de deudas: modo avalancha vs bola de nieve — `GET /debts/strategy?extra_monthly=N` (sin tabla nueva, simulación pura en `app/services/debt_strategy.py`: interés EA→mensual, presupuesto total constante con rollover de mínimos, cap 600 meses si no converge). Compara ambas estrategias (meses hasta libre, intereses totales, orden de pago) y recomienda: avalancha si ahorra intereses, bola de nieve si empatan. Mobile: botón "Estrategia de pago" en Deudas abre sheet con input de abono extra y comparación.

## Fase 3 — Construir hábitos (mes 3) ✅

- [x] Metas de ahorro con fecha y progreso visual — tabla `savings_goals` (monto objetivo, `current_amount` reportado por el usuario — TrackIt no ve saldos, solo emails), CRUD `/goals` con `pct` calculado. Pantalla mobile "Metas de ahorro" (stack, acceso desde Dashboard) con barras de progreso y sheet de edición.
- [x] Flujo de caja proyectado — `GET /cashflow` (calculado al vuelo desde `income_sources` + `planned_payments`, lógica pura en `app/services/cash_flow.py`): ingresos fijos − compromisos = disponible mensual, próximo ingreso esperado, vencimientos próximos y checklist. Pantalla mobile "Plan del mes".
- [x] Alertas de gasto inusual — `GET /insights/unusual-spending` (`app/services/spending_anomalies.py`, puro): mes actual vs promedio de hasta 6 meses de historia por categoría; alerta si ≥1.5× el promedio, ≥$50k y ≥2 meses de baseline. Banner en Dashboard.
- [x] Score de salud financiera — `GET /insights/health-score` (`app/services/health_score.py`, puro): 0-100 en 4 componentes explicables — deuda 30 (carga de mínimos vs ingreso mensual), presupuestos 25, metas 25 (progreso promedio), gasto inusual 20. Sin datos configurados → crédito neutral parcial. Card en Dashboard con color por rango.
- [x] Calendario de ingresos configurable — tabla `income_sources` (una fila por depósito recurrente: quincena 1, quincena 2, bonificación), CRUD `/income-sources`. "Próximo ingreso: X el día N por $Y" en la pantalla Plan. La comparación contra el depósito real queda como mejora futura.
- [x] "Apartado" / dinero comprometido — tabla `planned_payments` (una tabla sirve apartados + recordatorios + checklist): el disponible calculado del `/cashflow` resta todos los compromisos del ingreso esperado. El banco sigue siendo la fuente de verdad del saldo.
- [x] Checklist de "pagar primero" — `checklist` en `/cashflow`: pagos ordenados deudas-primero (`is_debt_payment`) y luego por vencimiento más próximo. Sección "Al cobrar, pagá en este orden" en la pantalla Plan.
- [x] Check mensual de compromisos — `paid_month` ("YYYY-MM", migración `eab7d2db244a`) en `planned_payments`: tap en el checklist del Plan tacha/destacha el pago del mes (los pagados van al fondo, contador N/M); al cambiar el mes local el check se resetea solo, sin cron.
- [x] Recordatorios de pagos con fecha límite — `due_day` + `grace_days` en `planned_payments` (ej. arriendo: corte 24 + 15 días) → `deadline` y `days_left` en `/cashflow.upcoming`; mobile colorea vencimientos ≤3 días (rojo) y ≤7 (amarillo). Push notifications quedan para futuro; hoy es in-app.

## Fase 4 — Inteligencia (futuro)

- [x] Push notifications — tabla `push_tokens` (registro vía `POST /notifications/token` post-login en mobile con `expo-notifications`) + job diario 8am (`send_push_alerts_job`): presupuestos al 80/100%, vencimientos ≤3 días y gasto inusual, con dedupe por periodo en `notification_logs` (una alerta suena una vez por mes/vencimiento, no todos los días). Envío vía Expo Push API (`app/services/push_sender.py`); tokens muertos (`DeviceNotRegistered`) se purgan solos. Nota: en Expo Go (SDK 53+) push remoto no funciona — requiere development build; el registro falla silencioso en dev.
- [ ] Análisis de patrones con IA (Claude API)
- [x] Parser Davivienda (cuenta de nómina desde 2026-09): compras, PSE, abonos, transferencias a llave → Nequi pareadas (ver PARSERS.md)
- [x] Tarjetas de crédito conectadas por email, con remitente configurable desde la app (RappiCard primero): compras = gasto + suben la deuda, pagos bajan la deuda y su débito bancario pasa a `debt_payment`, el extracto actualiza mínimo y fecha límite (ver PARSERS.md)
- [x] Patrimonio — tablas `accounts` (Davivienda, Nequi, Efectivo) + `account_adjustments`, `GET /accounts`, `PUT /accounts/{kind}`, `POST /accounts/{kind}/reconcile`, `POST /transactions/cash`. El saldo se **calcula** (saldo inicial + movimientos de esa cuenta desde entonces + ajustes) usando `transactions.source`, nunca se acumula. Patrimonio neto = cuentas − deudas. Conciliar guarda la diferencia con el saldo real como ajuste visible ("sin explicar"), no como gasto. Pantalla mobile "Patrimonio" (acceso desde Inicio). Lógica en `app/services/net_worth.py`.
- [ ] Soporte para más bancos: Bancolombia, Nu Colombia
- [ ] Reporte mensual exportable en PDF
- [ ] Modo finanzas en pareja (gastos compartidos)

## Principios de ingeniería

- Antes de implementar una feature, verificar que no bloquea features futuras del roadmap
- Parser architecture debe ser extensible (BaseBankParser)
- Nunca guardar credenciales bancarias, solo OAuth tokens encriptados con Fernet
- Mobile-first: toda feature debe tener pantalla en Expo antes de considerarse completa
- Tests para todos los parsers (casos reales de emails)
