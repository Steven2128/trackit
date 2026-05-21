# Architecture Decision Records

Decisiones técnicas con su contexto y consecuencias. Cuando agarres el código
dentro de seis meses y te preguntes "¿por qué hice esto así?", la respuesta
debería estar acá.

Formato: cada ADR tiene un número, un título corto, fecha, estado, y secciones
**Contexto** (qué problema resolvía), **Decisión** (qué se hizo),
**Consecuencias** (qué se gana / qué se sacrifica), **Alternativas
descartadas** (lo que NO se hizo y por qué).

Estados: `Aceptado` | `Reemplazado por ADR-NNN` | `Deprecado`.

---

## ADR-001: Flujo OAuth de Google manejado por el backend

**Fecha:** 2026-05-20
**Estado:** Aceptado

### Contexto

El plan original era usar `expo-auth-session/providers/google` para el sign-in
nativo en el mobile. Al probarlo, `Google.useAuthRequest({ useProxy: true })`
devolvía la URI nativa de Expo Go (`exp://192.168.x.x:8081`) y Google la
rechazaba con `redirect_uri_mismatch`. Investigación: el proxy
`auth.expo.io` fue **deprecado y apagado** por Expo a partir de SDK 48+. En
SDK 54 la opción `useProxy` ya no existe ni siquiera en el tipado.

### Decisión

Implementar el flujo OAuth completo en el backend FastAPI:

1. Mobile abre `${API}/auth/google/start` con `WebBrowser.openAuthSessionAsync`.
2. Backend redirige a Google con state JWT firmado.
3. Google callback al backend (`/auth/google/callback`).
4. Backend intercambia code, verifica id_token, upserta `User`, emite JWTs.
5. Backend redirige al deep-link `trackit://auth?access_token=...&refresh_token=...`.
6. Mobile captura el deep-link, persiste sesión, llama `/auth/me`.

Mismo patrón para `/gmail/connect` (con state bound al `user_id` autenticado).

### Consecuencias

**Ganamos:**
- Los Google Client ID / Secret viven solo en el backend, no en el bundle del cliente.
- Funciona en Expo Go sin necesidad de dev build.
- El backend tiene control completo del lifecycle del token (puede refrescar Gmail tokens server-side).
- Un solo lugar donde se hace OAuth; mismo código sirve para web/iOS/Android.

**Pagamos:**
- El backend tiene que ser accesible públicamente para que Google le hable. Para dev en device físico necesitamos un túnel HTTPS (ngrok) — Google no acepta redirect URIs HTTP no-localhost.
- Si rotamos la URL del backend (ngrok dinámico) hay que actualizar Cloud Console.

### Alternativas descartadas

- **Dev client + Google iOS/Android Client IDs**: requiere `eas build`, configurar URL schemes en `Info.plist`/`AndroidManifest`. Más fricción para dev y para los usuarios que tendrían que instalar un APK custom en vez de Expo Go.
- **Esperar a que Expo reactive el proxy**: no va a pasar (declarado deprecado oficialmente).

---

## ADR-002: SQLAlchemy 2.0 async + asyncpg en toda la app

**Fecha:** 2026-05-20
**Estado:** Aceptado

### Contexto

FastAPI es async-first. Las consultas a Postgres pueden bloquear el event loop
si se hacen sync.

### Decisión

Toda la capa de DB es async: engine `create_async_engine`, sessionmaker
`async_sessionmaker`, sesiones `AsyncSession`, queries con `await db.execute(...)`.
Alembic se configura en modo async también (`alembic init -t async`).

### Consecuencias

**Ganamos:**
- Mejor throughput cuando lleguen workers de sync de Gmail (operación con I/O bound).
- Coherencia: todos los endpoints son `async def`.

**Pagamos:**
- Sintaxis menos familiar para quien viene de SQLAlchemy 1.x sync.
- Algunas librerías que esperan engines sync (ej. `Flow` de google-auth-oauthlib) no se pueden usar con la sesión directamente; por eso el token exchange con Google se hace con `httpx.AsyncClient`, no con `Flow`.

### Alternativas descartadas

- **SQLAlchemy 1.x sync con `run_in_executor`**: pierde la ergonomía async y agrega complejidad sin ganancia clara.
- **SQLModel**: capa de azúcar sobre SQLAlchemy; no aporta nada y agrega una dependencia más.

---

## ADR-003: Encriptación de tokens OAuth con Fernet (envelope simétrico)

**Fecha:** 2026-05-20
**Estado:** Aceptado

### Contexto

Los `access_token` y `refresh_token` de Google que almacenamos en
`provider_connections` son credenciales sensibles: con el refresh_token
alguien puede leer mi Gmail indefinidamente. Si la DB se filtra, no quiero
que esos tokens viajen en plano.

### Decisión

Encriptar `access_token_encrypted` y `refresh_token_encrypted` con
**Fernet** (AES-128-CBC + HMAC, key simétrica de 32 bytes). La key vive en
`FERNET_KEY` (env var). Helpers `encrypt_token` / `decrypt_token` centralizan
en `app/core/security.py`; nadie debe usar `cryptography.fernet.Fernet`
directamente.

### Consecuencias

**Ganamos:**
- Defensa en profundidad: si alguien dumpea la DB pero no tiene la `FERNET_KEY`, los tokens son inservibles.
- Encriptación at-rest sin depender de configuración de Postgres (TDE, pgcrypto).

**Pagamos:**
- Rotar `FERNET_KEY` rompe todos los tokens existentes — hay que re-conectar Gmail después de rotar. Procedimiento debería estar en `SECURITY.md` (si algún día se crea).
- La key está en el `.env` del backend, así que si se filtra la `.env`, se filtran los tokens. Esto es aceptable para una app personal de un único usuario; en producción real iría a un KMS.

### Alternativas descartadas

- **Plaintext en DB**: descartado por riesgo si la DB se filtra.
- **AES-GCM crudo**: Fernet ya hace lo correcto (IV random, HMAC, versionado) — no vale la pena re-implementar.
- **Encriptación a nivel de columna en Postgres (pgcrypto)**: agrega configuración a la migración y obliga a SQL crudo; menos portable.

---

## ADR-004: JWT (HS256) con par access + refresh, sin sesiones server-side

**Fecha:** 2026-05-20
**Estado:** Aceptado

### Contexto

La app es de un solo usuario y mono-cliente (mobile). Necesitamos autenticar
requests sin obligar al usuario a re-loguearse cada media hora.

### Decisión

- Access token JWT corto (`ACCESS_TOKEN_EXPIRE_MINUTES`, default 30).
- Refresh token JWT largo (`REFRESH_TOKEN_EXPIRE_DAYS`, default 30).
- Algoritmo HS256, firmado con `SECRET_KEY`.
- Sin almacén de sesiones / refresh tokens en DB — la firma del JWT es la única prueba.
- Endpoint `POST /auth/refresh` que emite un access token nuevo a partir de un refresh válido.

### Consecuencias

**Ganamos:**
- Stateless: cada request se valida con la firma del JWT, sin hit a DB.
- Refresh automático en el cliente (`mobile/src/services/api.ts` lo hace en el interceptor 401).

**Pagamos:**
- No podemos revocar un refresh token sin rotar el `SECRET_KEY` global. Para una app personal no es crítico, pero para algo serio querríamos una blacklist o pasar a sesiones.
- Si se filtra el `SECRET_KEY`, cualquiera puede emitir JWTs válidos por todos los usuarios. Mismo trade-off que con Fernet.

### Alternativas descartadas

- **Sesiones server-side (Redis)**: para 1 usuario es overkill.
- **OAuth tokens de Google directamente como auth de app**: no, porque queremos un identificador estable propio (`user.id` UUID) que no dependa de Google.

---

## ADR-005: Mono-repo backend + mobile en el mismo repositorio

**Fecha:** 2026-05-20
**Estado:** Aceptado

### Contexto

Backend y mobile evolucionan juntos: cuando agrego un campo en `transactions`, casi siempre toca actualizar el cliente.

### Decisión

Un solo repo, dos directorios: `backend/` y `mobile/`. Sin tooling de
mono-repo (Nx, Turborepo): el cambio es manual entre carpetas. Docker
Compose en la raíz para el stack de dev.

### Consecuencias

**Ganamos:**
- Un commit que cambia API + cliente queda en un solo PR/commit.
- Setup más simple — `docker compose up` levanta backend y DB en uno solo.

**Pagamos:**
- Las dependencias de Python y Node coexisten; CI tendría que orquestar ambos.
- No tenemos compartido de tipos (schemas Pydantic ↔ tipos TS). Cada lado define los suyos. Para un proyecto chico es aceptable; si crece, OpenAPI client generation lo arreglaría.

### Alternativas descartadas

- **Dos repos separados**: más fricción para un proyecto de una persona.
- **Mono-repo con Turborepo**: agrega un layer de tooling que no necesitamos hoy.

---

## ADR-006: State CSRF para OAuth como JWT corto, no como server-side store

**Fecha:** 2026-05-20
**Estado:** Aceptado

### Contexto

El parámetro `state` del flujo OAuth es nuestra defensa contra CSRF (que
alguien nos haga completar el flujo con un code de otro). Además, para
`/gmail/connect`, necesitamos saber a qué `user_id` pertenece el flujo
cuando vuelve el callback (que no lleva JWT del usuario).

### Decisión

`state` es un JWT firmado con `SECRET_KEY`, TTL 10 min, con claims:
`purpose` (`"auth"` o `"gmail"`), `nonce` random, `return_scheme`, y para
`gmail` también `user_id`. Helpers `create_state_token` /
`decode_state_token` en `app/core/security.py`.

### Consecuencias

**Ganamos:**
- Sin tabla de states en DB, sin Redis, sin cleanup de expirados.
- El callback puede recuperar `user_id` sin tener sesión activa.

**Pagamos:**
- Si alguien intercepta el state JWT mientras el flujo está en curso (10 min) podría intentar completar el flujo. La mitigación es el `nonce` random + el TTL corto.

### Alternativas descartadas

- **Store en DB**: cleanup adicional, una migración más, no aporta nada.
- **State opaco (UUID) + lookup en cache**: requiere Redis o equivalente.

---

## ADR-007: Pydantic v2 para schemas, modelos ORM separados

**Fecha:** 2026-05-20
**Estado:** Aceptado

### Contexto

Hay que decidir cómo modelar la frontera entre HTTP y DB.

### Decisión

- Modelos SQLAlchemy en `app/models/` representan la DB. Nunca se devuelven directamente desde un endpoint.
- Schemas Pydantic v2 en `app/schemas/` representan los payloads HTTP. Cada response usa `ConfigDict(from_attributes=True)` y se valida con `model_validate(orm_obj)`.

### Consecuencias

**Ganamos:**
- Capa clara de validación de input/output.
- Cambios internos a la tabla no rompen contratos del API si el schema queda igual.

**Pagamos:**
- Duplicación: el `User` aparece en `models/user.py` y en `schemas/user.py`. Para un proyecto chico es manejable.

### Alternativas descartadas

- **SQLModel**: junta ambos pero pierde el control fino sobre qué se serializa.
- **Devolver dicts manuales**: pierde tipado y validación en runtime.
