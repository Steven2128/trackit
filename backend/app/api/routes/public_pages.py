"""Static public pages: home + privacy policy.

Google's OAuth consent screen requires a homepage and a privacy policy URL
before the app can leave "Testing" (where refresh tokens expire after 7
days). Serving them from the API itself keeps everything on the Render
domain that's already listed as an authorized domain.
"""

from __future__ import annotations

import html

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.core.config import settings

router = APIRouter(tags=["public"], include_in_schema=False)

_STYLE = """
<style>
  :root { color-scheme: light dark; }
  body { font-family: system-ui, sans-serif; max-width: 680px; margin: 0 auto;
         padding: 32px 16px; line-height: 1.6; }
  h1 { margin-bottom: 4px; }
  .muted { opacity: .7; }
</style>
"""


def _page(title: str, body: str) -> HTMLResponse:
    # Google Search Console ownership proof (URL-prefix property, HTML tag
    # method) — needed for OAuth brand verification of the home page URL.
    verification = (
        f"<meta name='google-site-verification' "
        f"content='{html.escape(settings.google_site_verification, quote=True)}'>"
        if settings.google_site_verification
        else ""
    )
    return HTMLResponse(
        "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"{verification}<title>{title}</title>{_STYLE}</head><body>{body}</body></html>"
    )


@router.get("/", response_class=HTMLResponse)
async def home() -> HTMLResponse:
    return _page(
        "TrackIt",
        """
        <h1>TrackIt</h1>
        <p class="muted">Finanzas personales</p>
        <p>TrackIt lee las notificaciones de movimientos que tu banco te envía por
        email y las convierte en un resumen de gastos, ingresos, presupuestos y
        deudas dentro de una app móvil.</p>
        <p><a href="/privacy">Política de privacidad</a></p>
        """,
    )


@router.get("/privacy", response_class=HTMLResponse)
async def privacy() -> HTMLResponse:
    return _page(
        "TrackIt — Privacidad",
        """
        <h1>Política de privacidad</h1>
        <p class="muted">Última actualización: 1 de octubre de 2026</p>

        <h2>Qué datos usamos</h2>
        <ul>
          <li><strong>Cuenta de Google</strong>: nombre, email y foto, para
          identificarte al iniciar sesión.</li>
          <li><strong>Gmail (solo lectura)</strong>: únicamente los emails de
          notificación de los bancos soportados. De cada uno se extrae monto,
          fecha, comercio y tipo de movimiento. No se leen ni se guardan otros
          emails.</li>
        </ul>

        <h2>Cómo los guardamos</h2>
        <p>Los movimientos extraídos se guardan en una base de datos privada. Los
        tokens de acceso a Google se almacenan encriptados y nunca se muestran ni
        se comparten.</p>

        <h2>Con quién los compartimos</h2>
        <p>Con nadie. Los datos no se venden, no se usan para publicidad ni se
        transfieren a terceros. El uso de la información recibida de las APIs de
        Google cumple la
        <a href="https://developers.google.com/terms/api-services-user-data-policy">
        Google API Services User Data Policy</a>, incluidos los requisitos de uso
        limitado.</p>

        <h2>Cómo borrarlos</h2>
        <p>Podés revocar el acceso en cualquier momento desde
        <a href="https://myaccount.google.com/permissions">myaccount.google.com/permissions</a>
        y pedir el borrado de tus datos escribiendo al email de soporte que
        aparece en la pantalla de consentimiento de Google.</p>
        """,
    )
