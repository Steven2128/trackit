# Email Parsers — Estado por banco

Registro vivo de los parsers de emails bancarios. Cada parser es una subclase
de `EmailParser` (`backend/app/parsers/base.py`) que toma el payload crudo
de un mensaje de Gmail y devuelve un `ParsedTransaction` (o `None`).

Cuando agregues un banco nuevo:
1. Agregalo a la tabla de abajo con estado `Backlog`.
2. Guardá 3-5 emails reales anonimizados en `backend/tests/fixtures/<banco>/`.
3. Llená la sección detallada (sender, subject típico, campos, gotchas).
4. Implementá `app/parsers/<banco>.py` y registralo en el dispatcher.
5. Cuando pase los tests, marcalo como `Done`.

## Estado

| Banco / Proveedor      | País | Estado     | Sender                              | Parser                                |
|------------------------|------|------------|-------------------------------------|---------------------------------------|
| Itaú                   | CO   | Done       | `notificaciones@clienteitau.co`     | `app/parsers/itau_co.py`              |
| Nequi                  | CO   | Done       | `notificaciones@nequi.com.co`, `somos@nequi.com.co` | `app/parsers/nequi.py` |
| Davivienda             | CO   | Done       | `BANCO_DAVIVIENDA@davivienda.com`   | `app/parsers/davivienda.py`           |
| Daviplata              | CO   | Backlog    | Sin notificaciones por email (0 hits en 90 días) | `app/parsers/daviplata.py` (TBD) |
| Banco Falabella        | CO   | Backlog    | Solo marketing observado (`contacto@co.bancofalabella.com`) | `app/parsers/falabella_co.py` (TBD) |

> **Por qué parseamos los tres "destinos"**: Itaú no incluye el destinatario
> cuando hacés una transferencia (solo dice "Débito · Canal: Portal Internet").
> Para marcar correctamente esos débitos como `category="transfer"` y no
> contarlos como gasto, capturamos también las notificaciones entrantes de
> Nequi/Daviplata/Falabella y las **emparejamos** por monto y ventana de
> tiempo. Detalle en la sección "Pareo de transferencias" abajo.

Leyenda: `Backlog` (planeado) · `WIP` (en desarrollo) · `Done` (tests pasan, integrado) · `Broken` (formato cambió, requiere atención).

---

## Itaú Colombia

- **País**: Colombia
- **Sender**: `notificaciones@clienteitau.co`
- **Estado**: Done (11/11 tests pasan, `tests/parsers/test_itau_co.py`)
- **Parser**: `backend/app/parsers/itau_co.py`
- **Fixtures**: `backend/tests/fixtures/itau_co/` (5 emails reales anonimizados)

### Tipos de notificación a soportar

1. **Compra con tarjeta débito/crédito** — el "core" del MVP.
2. **Transferencia enviada** a otra cuenta del usuario (débito; ver sección "Cuentas destino de transferencias propias" — se marca como `category="transfer"` y no cuenta como gasto).
3. **Transferencia enviada a un tercero** (débito; sí cuenta como gasto).
4. **Transferencia recibida** a la cuenta (crédito; incluye depósito de nómina).
5. **Retiro en cajero** (débito; tratado también como transferencia a "Efectivo").

### Campos a extraer

| Campo                       | Origen típico                                     |
|----------------------------|----------------------------------------------------|
| `amount`                   | Cuerpo del mail — formato colombiano `$1.234.567,89` |
| `currency`                 | Casi siempre `COP`                                 |
| `transaction_type`         | `debit` para compras/transferencias enviadas; `credit` para recibidas |
| `merchant`                 | Comercio (compra) o concepto (transferencia)       |
| `card_last_digits`         | Últimos 4 si la operación fue con tarjeta          |
| `occurred_at`              | Fecha/hora dentro del cuerpo, parseable a UTC      |
| `raw_email_reference`      | Gmail message ID — para dedupe                     |
| `category`                 | Inicialmente null; se completa post-process        |

### Gotchas conocidos

- **Formato de monto solo soportado: gringo (`$18,800`).** Los fixtures reales que tenemos vienen así (coma = miles, punto = decimal opcional). El regex `_AMOUNT_RE` en `itau_co.py:47` y el `replace(",", "")` solo manejan ese formato. Si en algún momento Itaú manda un email con formato colombiano (`$1.234.567,89` — punto = miles, coma = decimal), el parser va a leer mal el monto. Pendiente: confirmar con más fixtures si ese formato existe; si aparece, agregar branch en `_extract_amount`.
- Los emails de transferencia saliente NO incluyen destinatario (solo dicen `Canal: Portal Internet`). Se resuelve por pareo con notificaciones entrantes de Nequi/Daviplata/Falabella — ver "Pareo de transferencias" abajo.
- Notificaciones "informativas" (cambio de plan, vencimiento de tarjeta) no generan transacción — el parser devuelve `None` cuando ningún template matchea. Cubierto por `test_no_recognized_template_returns_none`.
- **Falta fixture de retiro en cajero**: el template 5 de PARSERS.md ("Retiro en cajero") aún no está cubierto por fixture ni test. Cuando aparezca un email real, hay que agregarlo y verificar si cae en `_DEBIT_RE` con `Canal: Cajero` o si requiere un template propio.

---

## Nequi

- **País**: Colombia
- **Senders transaccionales**: `notificaciones@nequi.com.co` (Bre-B) y `somos@nequi.com.co` (pagos PSE y facturas; también manda avisos de acceso y onboarding, que no matchean ningún template → `None`). El marketing de `somos@notificaciones.nequi.com.co` lo rechaza `can_parse`. Un parser puede declarar varios `sender_filter` (tupla) y `build_query` los suma al `from:` de Gmail.
- **Estado**: Done (`tests/parsers/test_nequi.py`)
- **Parser**: `backend/app/parsers/nequi.py`
- **Fixtures**: `backend/tests/fixtures/nequi/` (anonimizados de emails reales; `recibiste_otro_banco.eml` es **sintético** — construido para fijar el comportamiento de no-candidato, no se observó un email real de otro banco).

### Templates

1. **"¡Recibiste plata por Bre-B!"** → `credit`, `merchant="Nequi"`,
   `category="transfer"` **siempre** (Nequi es destino de parqueo: lo que
   entra ahí nunca suma al "Recibido" de la app, pareado o no — decisión del
   usuario 2026-07). Dice el banco origen ("desde el banco Itau") — si es
   Itaú se marca `is_pairing_candidate=True` (autotransferencia a emparejar);
   cualquier otro banco queda como transfer sin candidato.
2. **"¡Enviaste plata por Bre-B!"** → `debit`, `merchant=<destinatario>`.
   Gasto real desde el saldo Nequi, no candidato.
3. **"¡Pago exitoso!"** (PSE desde Nequi, `somos@`): "Hiciste un pago en
   <COMERCIO> por $92.990 Fecha: El 6 de abril de 2026 Hora: 2:28 p. m." →
   `debit`, `merchant=<COMERCIO>`.
4. **Comprobante de factura** ("Comprobante de pago Enel", "Tu comprobante de
   pago Claro Hogar"): "Listo tu pago en <EMPRESA> Pagaste con Nequi tu
   factura por $92.670" → `debit`, `merchant=<EMPRESA>`. El cuerpo no trae
   hora, solo "Fecha del pago: 06/Ago/2026": `occurred_at` = hora de llegada
   del email.

### Gotchas

- **Monto en formato colombiano**: `1.647.000` (punto = miles, coma = decimal opcional) — al revés de Itaú que usa formato gringo. Bre-B va sin `$`, los pagos con `$`.
- Los pagos PSE a bancos ("Banco Davivienda SA", "BBVA Colombia") pueden ser abonos a tarjeta o crédito, y los pagos a fondos de inversión pueden ser ahorro. Se guardan como gasto sin categoría y el usuario los recategoriza.
- **Fecha en español largo hora Bogotá**: "el 3 de julio de 2026 a las 3:07 p.m". Con la 1 en singular: "a la 1:55 p.m" — el regex acepta `a las?`.
- Notificaciones de acceso ("Notificación de acceso a tu Nequi") no matchean ningún template → `None`.

---

## Davivienda

- **País**: Colombia
- **Sender transaccional**: `BANCO_DAVIVIENDA@davivienda.com` (asunto siempre "DAVIVIENDA"). `ServicioNotificaciones@davivienda.com` manda avisos de registro/actualización de datos y `can_parse` lo rechaza.
- **Estado**: Done (`tests/parsers/test_davivienda.py`)
- **Parser**: `backend/app/parsers/davivienda.py`
- **Fixtures**: `backend/tests/fixtures/davivienda/` (6 emails reales anonimizados, guardados en Latin-1 como llegan)
- **Rol**: desde 2026-09 es la cuenta de nómina y reemplaza a Itaú como cuenta principal. El parser de Itaú queda registrado para el histórico.

### Template único

"se ha registrado el siguiente movimiento de su Cta de Ahorros terminada (o) en ****NNNN: Fecha · Hora · Valor Transacción · Clase de Movimiento · Lugar de Transacción". La **clase** decide:

| Clase de Movimiento | Resultado |
|---|---|
| `Abono …` (Pago de Nomina, de Proveedores, A Otros Bancos en Linea Transfiya) | `credit`, merchant = Lugar |
| `Descuento Transferencia a una llave` | `debit`, merchant = `Transferencia llave Davivienda`, `category="transfer"`, pairing candidate |
| Cualquier otra con valor (Compra en Establecimiento, Descuento en Internet/PSE) | `debit`, merchant = Lugar |
| Sin "Valor Transacción" (Cambio de Clave) | `None` |

### Gotchas

- **"Abono A Otros Bancos en Linea Transfiya" es una entrada**, no una salida (confirmado por el usuario: es nómina). Toda clase que empieza con "Abono" es un crédito.
- **Transferencias a llave = puente a Nequi**: el usuario las usa para pasar plata a su Nequi y pagar desde ahí. Se marcan `transfer` de entrada (pareadas o no) y el gasto real lo registra el "Enviaste" de Nequi. Si alguna va a un tercero, hay que recategorizarla a mano desde la app.
- **Charset**: el cuerpo viene en Latin-1 aunque el `<meta>` dice UTF-8. `app/integrations/gmail.py::_decode_part_body` respeta el charset del header y cae a cp1252 si UTF-8 falla. Además, los regex usan `.` en las letras acentuadas por si el acento llega roto.
- **Monto en formato gringo** (`$1,186,548`), igual que Itaú.
- Las clases vienen con espacios de relleno ("Compra       en Establecimiento,") y a veces con coma final.

---

## Pareo de transferencias (Itaú → Nequi/Daviplata/Falabella)

**El problema**: cuando hacés una transferencia desde Itaú a Nequi/Daviplata/
Falabella, Itaú te manda un email que dice "Débito · Canal: Portal Internet"
sin decir el destinatario. No podemos distinguir automáticamente entre:

- Una transferencia a tu Nequi (no es gasto, es movimiento interno).
- Un pago de servicio online (sí es gasto).
- Una transferencia a un amigo (sí es gasto).

**La solución** (Opción 2 elegida por el usuario): capturar también los
emails entrantes de Nequi/Daviplata/Falabella ("recibiste $X") y emparejarlos
con los débitos genéricos de Itaú.

### Flujo del pareo

1. Itaú parsea el "Débito · Canal Portal Internet" como `debit` con
   `merchant="Portal Internet"`, `category=None`. La guarda con
   `is_pairing_candidate=True` (flag a agregar al modelo).
2. Parser de Nequi (o Daviplata/Falabella) parsea el email entrante como
   `credit` con `merchant="Nequi"` (o el banco que corresponda), también
   marcado como pairing candidate.
3. Después del sync, `app/services/transfer_matcher.py` (**implementado** — corre automáticamente al final de cada `sync_provider_connection`, manual y cron):
   - Toma todos los débitos sin emparejar con `merchant="Portal Internet"` de los últimos 7 días.
   - Toma todos los créditos sin emparejar con `merchant in ("Nequi", "Daviplata", "Banco Falabella")` del mismo período.
   - Empareja por **monto exacto** y **ventana de tiempo ±10 min**.
   - Si encuentra pareja: ambas filas reciben `category="transfer"` y un mismo `transfer_pair_id` (UUID nuevo).
4. Los débitos que **no** encuentran pareja después de 7 días pueden:
   - Quedar como gasto normal (asumiendo que fue un pago real).
   - O ser reclasificados manualmente desde la UI (post-MVP).

### Cambios al modelo de DB que esto requiere

Va a hacer falta una migración nueva que agregue a `transactions`:

```sql
ALTER TABLE transactions
  ADD COLUMN is_pairing_candidate BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN transfer_pair_id UUID NULL;

CREATE INDEX ix_transactions_transfer_pair_id ON transactions(transfer_pair_id);
CREATE INDEX ix_transactions_pairing_candidate ON transactions(user_id, is_pairing_candidate, occurred_at)
  WHERE is_pairing_candidate IS TRUE AND transfer_pair_id IS NULL;
```

**Hecho** — migración `31074b1ae88b` (incluye backfill de débitos Portal
Internet pre-existentes). El matcher está en
`app/services/transfer_matcher.py` con la lógica de pareo pura
(`pair_transfers`) testeada en `tests/services/test_transfer_matcher.py`.

**Estado actual del pareo**: lado débito (Itaú `Portal Internet` y
Davivienda `Transferencia llave Davivienda`) y lado crédito **Nequi**
completos — Itaú→Nequi y Davivienda→Nequi activos end-to-end. Nequi marca
como candidato el "Recibiste" que viene "desde el banco" Itaú o Davivienda. Daviplata no manda
notificaciones por email y de Falabella solo se observó marketing; esos dos
lados crédito siguen pendientes de emails reales.

### Efectivo (caso especial)

Los retiros en cajero también producen un débito de Itaú, pero el canal
probablemente sea `"Cajero"` o similar (a confirmar con un fixture). El
parser puede marcarlos directamente con `category="cash_withdrawal"` (no
necesitan pareo). El gasto real en efectivo posterior queda fuera del
tracking automático — sería feature de entry manual, post-MVP.

### Resumen exclusión

El endpoint `GET /transactions/summary` debe **excluir** del total de gasto
del mes:

- Filas con `category="transfer"` (transferencias entre cuentas propias, ya emparejadas).
- Filas con `category="cash_withdrawal"` si querés que el cajón sea aparte.

Sí muestra todo en la lista cruda de transacciones — el usuario quiere ver
los movimientos, solo que no inflen el total de gasto.

---

## Extracto mensual Itaú (reconciliación automática)

- **Sender**: `extractos@clienteitau.co`. **Asunto**: "Extractos Itaú" (no
  confirmado el texto exacto — se detecta solo por sender).
- **Estado**: Done. `app/parsers/itau_statement.py` (extracción del PDF) +
  `app/services/statement_reconciler.py` (cruce/inserción, compartido con el
  CLI manual) + `app/services/statement_sync.py` (orquestación email→PDF) +
  endpoint `POST /gmail/sync-statements`.
- **Adjunto**: PDF "Multiextracto de Ahorros", protegido con contraseña =
  cédula del usuario (`ITAU_STATEMENT_PDF_PASSWORD` en `.env`, nunca en el repo/chat).
  Un solo PDF trae **todas** las cuentas de ahorro del usuario (en el fixture
  real: 3 cuentas, solo 1 con movimientos); se reconcilian todas las que
  tengan filas.

### Gotchas conocidos

- **Las páginas de encabezado del PDF (número de cuenta, "Fecha inicio/fin")
  usan una fuente embebida con ToUnicode CMap roto** — `pdfplumber` solo ve
  glifos `(cid:NN)` ahí, no texto legible. Por eso el extractor **no** lee
  cuenta/periodo de esas páginas:
  - **Cuenta**: se toma de la página resumen (página 1), que sí tiene texto
    legible y lista las cuentas en el mismo orden en que aparecen las
    secciones de tabla más adelante.
  - **Periodo (mes/año)**: no es recuperable del PDF. Se asume que el
    extracto de cierre del mes M llega por email a comienzos del mes M+1
    (confirmado por el usuario: extracto de junio llegó el 02 de julio) —
    `app/services/statement_sync.py::_statement_period` resta un mes a la
    fecha de recepción del email. Si Itaú cambia el timing de envío, esto
    hay que ajustarlo.
- Encabezados de la tabla ("Retiros", "Depósitos", etc.) a veces se
  renderizan con cada carácter duplicado (falso-negrita, ej.
  `"RReettiirrooss"`) en la primera página de cada sección; páginas de
  continuación los renderizan planos. El extractor matchea ambas formas.
- Columna Retiros/Depósitos: el monto no lleva signo, se clasifica por
  **posición x** relativa al punto medio entre ambos headers. Verificado
  contra los totales oficiales del extracto (saldo anterior + créditos −
  débitos = saldo final, al centavo) sobre el fixture real de junio 2026.
- Asume exactamente un token de "Número de Documento" por fila (siempre `"0"`
  en los fixtures observados) — si algún día viene poblado con texto real,
  la heurística de columna de descripción (`line[2:]`) se rompe.
- El fixture PDF real tiene PII (nombre, email, cuentas) — está gitignoreado
  (`backend/tests/fixtures/itau_co_extracto/*.pdf`). Los tests
  (`tests/parsers/test_itau_statement.py`) generan un PDF sintético con
  `reportlab` en tiempo de test, no dependen del archivo real.

---

## Convenciones del dispatcher

El componente que despacha emails a parsers (a implementar como parte del
`POST /gmail/sync`) debe:

1. Iterar la lista de parsers registrados en orden de registro.
2. Llamar `parser.can_parse(raw_email)`; usar el primero que retorne `True`.
3. Si ninguno matchea: loggear el sender y el subject como `unknown_sender` (para que sepamos qué bancos están llegando que no soportamos), continuar.
4. Si `parse(raw_email)` devuelve `None`: loggear como `parser_skipped` (el parser decidió que no es transacción), continuar.
5. Si `parse(raw_email)` lanza excepción: loggear como `parser_error` con el message ID, continuar (no romper todo el sync por un mail malformado).

Lista canónica de parsers: a definir en `app/parsers/__init__.py` cuando
exista el primero. Algo así:

```python
from app.parsers.itau_co import ItauCoParser
# from app.parsers.nequi import NequiParser
# from app.parsers.daviplata import DaviplataParser
# from app.parsers.falabella_co import FalabellaCoParser

REGISTERED_PARSERS = [
    ItauCoParser(),
    # NequiParser(),
    # DaviplataParser(),
    # FalabellaCoParser(),
]
```
