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
- [ ] Parser de emails Itaú
- [ ] Categorización automática
- [ ] Dashboard mensual
- [ ] Tracker de deudas

## Fase 1 — MVP (mes 1) 🚧

### Sprint 3 — Parser + Categorización

- [ ] Parser modular de emails Itaú Colombia
- [ ] Extracción: monto, comercio, fecha, últimos dígitos de tarjeta, tipo (débito/crédito)
- [ ] Categorización por reglas (supermercado → Food, Uber → Transport, etc.)
- [ ] Endpoint GET /transactions con filtros por mes y categoría
- [ ] Endpoint GET /transactions/summary

### Sprint 4 — Dashboard + Deudas

- [ ] Dashboard: total gastado el mes, por categoría, tendencia
- [ ] CRUD de deudas: banco, monto, tasa de interés, pago mínimo
- [ ] Pantallas mobile: Dashboard, Transactions, DebtTracker
- [ ] Sync automático con cron (cada 6 horas)

## Fase 2 — Entender patrones (mes 2)

- [ ] Presupuesto por categoría con alertas al 80% y 100%
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
