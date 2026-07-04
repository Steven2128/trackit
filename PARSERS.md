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
| Nequi                  | CO   | Done       | `notificaciones@nequi.com.co`       | `app/parsers/nequi.py`                |
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
- **Sender transaccional**: `notificaciones@nequi.com.co` — el marketing viene de `somos@nequi.com.co` / `somos@notificaciones.nequi.com.co` y `can_parse` lo rechaza.
- **Estado**: Done (`tests/parsers/test_nequi.py`)
- **Parser**: `backend/app/parsers/nequi.py`
- **Fixtures**: `backend/tests/fixtures/nequi/` (anonimizados de emails reales; `recibiste_otro_banco.eml` es **sintético** — construido para fijar el comportamiento de no-candidato, no se observó un email real de otro banco).

### Templates

1. **"¡Recibiste plata por Bre-B!"** → `credit`, `merchant="Nequi"`.
   Dice el banco origen ("desde el banco Itau") — si es Itaú se marca
   `is_pairing_candidate=True` (autotransferencia a emparejar); cualquier
   otro banco es ingreso de tercero, no candidato.
2. **"¡Enviaste plata por Bre-B!"** → `debit`, `merchant=<destinatario>`.
   Gasto real desde el saldo Nequi, no candidato.

### Gotchas

- **Monto en formato colombiano**: `1.647.000` (punto = miles, coma = decimal opcional, sin `$`) — al revés de Itaú que usa formato gringo.
- **Fecha en español largo hora Bogotá**: "el 3 de julio de 2026 a las 3:07 p.m". Con la 1 en singular: "a la 1:55 p.m" — el regex acepta `a las?`.
- Notificaciones de acceso ("Notificación de acceso a tu Nequi") no matchean ningún template → `None`.

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

**Estado actual del pareo**: lado débito (Itaú) y lado crédito **Nequi**
completos — el pareo Itaú→Nequi está activo end-to-end. Daviplata no manda
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
