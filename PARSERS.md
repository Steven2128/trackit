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
| Itaú                   | CO   | WIP        | `notificaciones@clienteitau.co`     | `app/parsers/itau_co.py`              |
| Nequi                  | CO   | Backlog    | TBD — confirmar con email real      | `app/parsers/nequi.py` (TBD)          |
| Daviplata              | CO   | Backlog    | TBD — confirmar con email real      | `app/parsers/daviplata.py` (TBD)      |
| Banco Falabella        | CO   | Backlog    | TBD — confirmar con email real      | `app/parsers/falabella_co.py` (TBD)   |

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
- **Estado**: WIP
- **Parser**: `backend/app/parsers/itau_co.py` (por crear)
- **Fixtures**: `backend/tests/fixtures/itau_co/` (por crear)

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

### Gotchas conocidos (a confirmar con fixtures)

- El monto puede venir como `$ 1.234.567,89` o `COP 1,234,567.89` según el template. Hay que soportar ambos formatos de separador.
- Los emails de transferencia saliente incluyen el destinatario. Si matchea uno de los patrones de la tabla "Cuentas destino de transferencias propias", el parser debe marcar `category="transfer"`.
- Notificaciones "informativas" (cambio de plan, vencimiento de tarjeta) NO deben generar transacciones — el parser debe descartarlas en `can_parse` o devolver `None` en `parse`.

### Pendiente antes de empezar

- [ ] Guardar 5-7 emails reales como fixtures. Casos: compra con tarjeta, transferencia a cuenta propia (Falabella o Nequi), transferencia a un tercero, transferencia recibida (nómina), retiro en cajero, email informativo (negativo).
- [ ] Anonimizar los fixtures: reemplazar mi nombre, número de cuenta, últimos 4 dígitos con valores placeholder consistentes.

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
3. Después del sync, un job `app/services/transfer_matcher.py` (por crear):
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

(Lo hacemos cuando lleguemos al paso 3 del pareo. Por ahora el parser deja
todo listo para que el matcher trabaje después.)

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
