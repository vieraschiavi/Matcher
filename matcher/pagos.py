"""Plataforma de pago.

Flujo completo (catálogo → checkout → confirmación → alta del plan →
historial), con **cuatro** pasarelas:

  * `demo` — confirma en el acto, no mueve plata. La usan los tests y la demo.
  * `mercadopago` — Checkout Pro (`/checkout/preferences`), la más usada en
    Latinoamérica.
  * `paypal` — Orders API v2.
  * `dlocal` — Payments API, pensada para Latinoamérica con tarjetas locales.

Ninguna pasarela recibe ni guarda un número de cuenta bancaria: la cuenta de
cobro se configura del lado del proveedor (el panel de MercadoPago, PayPal o
dLocal), no acá. El código sólo maneja **credenciales de API** (client id,
client secret, access token), que son lo único que le corresponde saber a la
aplicación — el dinero lo mueve el proveedor directo a la cuenta que vos
configuraste en su panel.

Todas las credenciales se leen de variables de entorno. Nunca se loguean, no
se guardan en la base y no se devuelven por la API.

Lo que falta antes de cobrarle a alguien de verdad, y está marcado en cada
clase: probar contra la cuenta sandbox del proveedor (acá no hay credenciales
para hacerlo), y las reglas de facturación e impuestos por país.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime

from . import planes
from .modelos import DatosInvalidos, Perfil

PERIODOS = ("mensual", "anual")


class PagoNoAcreditado(DatosInvalidos):
    """La pasarela todavía no dice que la plata entró.

    No es un error del usuario ni un dato inválido: es "esperá". Tiene clase
    propia para que la API lo traduzca a 409 y el frontend pueda ofrecer
    "reintentar" en vez de mostrar un error rojo definitivo.
    """


@dataclass
class Checkout:
    id: str
    usuario_id: str
    plan: str
    periodo: str
    monto: float
    moneda: str
    pasarela: str
    url: str
    estado: str = "pendiente"
    referencia_externa: str = ""  # id que asignó el proveedor (preference/order/payment)

    def a_dict(self) -> dict:
        return {
            "id": self.id,
            "plan": self.plan,
            "periodo": self.periodo,
            "monto": self.monto,
            "moneda": self.moneda,
            "pasarela": self.pasarela,
            "url": self.url,
            "estado": self.estado,
        }


def _pedir(url: str, *, metodo: str = "GET", datos: dict | None = None, headers: dict | None = None) -> dict:
    """POST/GET JSON con la biblioteca estándar. Mismo patrón que `oauth.py`:
    nada de dependencias nuevas para hablar HTTP con un proveedor de pago."""
    cuerpo = json.dumps(datos).encode() if datos is not None else None
    pedido = urllib.request.Request(
        url,
        data=cuerpo,
        method=metodo,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(pedido, timeout=20) as r:
            texto = r.read().decode()
            return json.loads(texto) if texto else {}
    except urllib.error.HTTPError as e:
        # No se propaga el cuerpo crudo: puede traer datos del comercio.
        detalle = ""
        try:
            detalle = json.loads(e.read().decode()).get("message", "")
        except Exception:
            pass
        raise DatosInvalidos(f"la pasarela rechazó el pedido (HTTP {e.code}) {detalle}".strip()) from e
    except urllib.error.URLError as e:
        raise DatosInvalidos("no se pudo contactar a la pasarela de pago") from e


class Pasarela:
    """Interfaz mínima. Implementala para enchufar un proveedor nuevo."""

    nombre = "abstracta"

    def crear_checkout(self, checkout: Checkout) -> Checkout:  # pragma: no cover
        raise NotImplementedError

    def verificar_webhook(self, cuerpo: bytes, cabeceras: dict) -> bool:  # pragma: no cover
        raise NotImplementedError

    def esta_pagado(self, referencia: str, referencia_externa: str) -> bool:  # pragma: no cover
        """¿La plata entró de verdad?

        LA FUNCIÓN MÁS IMPORTANTE DE ESTE ARCHIVO. Antes no existía:
        `/api/pagos/confirmar` daba el plan de alta con sólo recibir una
        referencia, sin preguntarle nada al proveedor. Con eso, cualquiera con
        una cuenta hacía esto y se quedaba con Gold gratis:

            POST /api/pagos/checkout  {"plan": "gold"}   -> referencia
            POST /api/pagos/confirmar {"referencia": …}  -> Gold activado

        Y no hacía falta ni pagar. En modo `demo` da igual —no hay plata de por
        medio— pero apenas se enchufa MercadoPago es la caja abierta.

        Ahora nadie recibe un plan sin que la pasarela diga que sí.
        """
        raise NotImplementedError

    def referencia_de_notificacion(self, datos: dict) -> str | None:  # pragma: no cover
        """Del cuerpo del webhook, sacar CUÁL de nuestros cobros es.

        Cada proveedor lo manda en un lugar distinto, y MercadoPago
        directamente no lo manda: avisa `{"data": {"id": …}}` y hay que ir a
        buscar el pago a su API para saber a qué `external_reference`
        corresponde. Por eso esto es un método de la pasarela y no un `or`
        encadenado en el handler.
        """
        raise NotImplementedError


class PasarelaDemo(Pasarela):
    """Confirma en el acto. Es la que usa la demo y los tests.

    No mueve plata y lo dice: la URL que devuelve es interna de la app, no de
    un proveedor. Nunca la dejes activa en una build de producción — por eso
    `pasarela_activa()` mira `MATCHER_PASARELA`.
    """

    nombre = "demo"

    def crear_checkout(self, checkout: Checkout) -> Checkout:
        checkout.url = f"/#/pago/{checkout.id}"
        return checkout

    def verificar_webhook(self, cuerpo: bytes, cabeceras: dict) -> bool:
        return True

    def esta_pagado(self, referencia: str, referencia_externa: str) -> bool:
        """Siempre sí, porque no hay plata que verificar. Es LEGÍTIMO acá y
        sería una catástrofe en cualquier otra pasarela: por eso la decisión
        vive en cada clase y no en un `if nombre == "demo"` suelto por ahí."""
        return True

    def referencia_de_notificacion(self, datos: dict) -> str | None:
        return datos.get("external_reference")


class PasarelaMercadoPago(Pasarela):
    """Checkout Pro. Documentación: https://www.mercadopago.com.uy/developers

    Credenciales: `MERCADOPAGO_ACCESS_TOKEN` (la del vendedor, del panel de
    MercadoPago — ahí es donde se configura a qué cuenta bancaria llega la
    plata, no acá).
    """

    nombre = "mercadopago"
    API = "https://api.mercadopago.com"

    def crear_checkout(self, checkout: Checkout) -> Checkout:
        token = os.getenv("MERCADOPAGO_ACCESS_TOKEN")
        if not token:
            raise DatosInvalidos(
                "falta MERCADOPAGO_ACCESS_TOKEN; configurá la pasarela o usá MATCHER_PASARELA=demo"
            )
        base = os.getenv("MATCHER_URL_PUBLICA", "").rstrip("/")
        r = _pedir(
            f"{self.API}/checkout/preferences",
            metodo="POST",
            headers={
                "Authorization": f"Bearer {token}",
                # Evita duplicar la preferencia si el checkout se reintenta.
                "X-Idempotency-Key": checkout.id,
            },
            datos={
                "items": [
                    {
                        "title": f"Matcher {checkout.plan.capitalize()} ({checkout.periodo})",
                        "quantity": 1,
                        "currency_id": checkout.moneda,
                        "unit_price": checkout.monto,
                    }
                ],
                "external_reference": checkout.id,
                "back_urls": {
                    "success": f"{base}/#/pago/{checkout.id}",
                    "pending": f"{base}/#/pago/{checkout.id}",
                    "failure": f"{base}/#/planes",
                },
                "auto_return": "approved",
                "notification_url": f"{base}/api/pagos/webhook/mercadopago",
            },
        )
        checkout.referencia_externa = r.get("id", "")
        # `init_point` es la URL de pago real; `sandbox_init_point` existe
        # cuando el access token es de prueba.
        checkout.url = r.get("init_point") or r.get("sandbox_init_point", "")
        if not checkout.url:
            raise DatosInvalidos("MercadoPago no devolvió una URL de pago")
        return checkout

    def verificar_webhook(self, cuerpo: bytes, cabeceras: dict) -> bool:
        """MercadoPago firma con HMAC-SHA256 sobre un manifest armado con
        `x-request-id` y `x-signature` (que trae `ts` y `v1`). Se valida la
        firma; el estado del pago se confirma después consultando la API por
        el id, nunca confiando en el cuerpo del webhook a secas."""
        secreto = os.getenv("MERCADOPAGO_WEBHOOK_SECRET")
        firma = cabeceras.get("x-signature", "")
        id_pedido = cabeceras.get("x-request-id", "")
        if not secreto or not firma:
            return False
        partes = dict(p.split("=", 1) for p in firma.split(",") if "=" in p)
        ts, v1 = partes.get("ts", ""), partes.get("v1", "")
        try:
            datos = json.loads(cuerpo or b"{}")
        except json.JSONDecodeError:
            return False
        manifest = f"id:{datos.get('data', {}).get('id', '')};request-id:{id_pedido};ts:{ts};"
        esperado = hmac.new(secreto.encode(), manifest.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(esperado, v1)

    def _buscar_pagos(self, referencia: str) -> list[dict]:
        """Los pagos de MercadoPago que apuntan a ESTE cobro nuestro.

        Se busca por `external_reference` —nuestra referencia— y no por el id
        de la preferencia: una preferencia puede terminar en varios intentos de
        pago (uno rechazado, otro aprobado), y lo que importa es si ALGUNO
        quedó aprobado.
        """
        token = os.getenv("MERCADOPAGO_ACCESS_TOKEN")
        if not token:
            raise DatosInvalidos("falta MERCADOPAGO_ACCESS_TOKEN")
        r = _pedir(
            f"{self.API}/v1/payments/search?external_reference={urllib.parse.quote(referencia)}",
            headers={"Authorization": f"Bearer {token}"},
        )
        return r.get("results") or []

    def esta_pagado(self, referencia: str, referencia_externa: str) -> bool:
        return any(p.get("status") == "approved" for p in self._buscar_pagos(referencia))

    def referencia_de_notificacion(self, datos: dict) -> str | None:
        """MercadoPago avisa `{"type": "payment", "data": {"id": "123"}}` y NO
        manda la referencia nuestra. Hay que ir a buscar ese pago a su API.

        Esto faltaba y era un agujero funcional entero: el handler no
        encontraba referencia, respondía "procesado: false" y **el plan nunca
        se activaba**. Quien pagaba y cerraba el navegador se quedaba sin nada.
        """
        directa = datos.get("external_reference")
        if directa:
            return directa
        id_pago = str(datos.get("data", {}).get("id") or "")
        if not id_pago:
            return None
        token = os.getenv("MERCADOPAGO_ACCESS_TOKEN")
        if not token:
            return None
        pago = _pedir(
            f"{self.API}/v1/payments/{urllib.parse.quote(id_pago)}",
            headers={"Authorization": f"Bearer {token}"},
        )
        return pago.get("external_reference") or None


class PasarelaPayPal(Pasarela):
    """Orders API v2. Documentación: https://developer.paypal.com/docs/api/orders/v2/

    Credenciales: `PAYPAL_CLIENT_ID` y `PAYPAL_CLIENT_SECRET`. El modo (sandbox
    o real) lo decide `PAYPAL_ENTORNO` (`sandbox` por defecto, `live` para
    cobrar de verdad) — es la forma de probar sin arriesgar un cobro real.
    """

    nombre = "paypal"

    @property
    def _base(self) -> str:
        entorno = os.getenv("PAYPAL_ENTORNO", "sandbox")
        return "https://api-m.paypal.com" if entorno == "live" else "https://api-m.sandbox.paypal.com"

    def _token(self) -> str:
        client_id = os.getenv("PAYPAL_CLIENT_ID")
        secreto = os.getenv("PAYPAL_CLIENT_SECRET")
        if not client_id or not secreto:
            raise DatosInvalidos(
                "faltan PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET; configurá la pasarela o usá "
                "MATCHER_PASARELA=demo"
            )
        credenciales = base64.b64encode(f"{client_id}:{secreto}".encode()).decode()
        cuerpo = b"grant_type=client_credentials"
        pedido = urllib.request.Request(
            f"{self._base}/v1/oauth2/token",
            data=cuerpo,
            headers={
                "Authorization": f"Basic {credenciales}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        try:
            with urllib.request.urlopen(pedido, timeout=20) as r:
                return json.loads(r.read().decode())["access_token"]
        except urllib.error.HTTPError as e:
            raise DatosInvalidos(f"PayPal rechazó las credenciales (HTTP {e.code})") from e

    def crear_checkout(self, checkout: Checkout) -> Checkout:
        token = self._token()
        base = os.getenv("MATCHER_URL_PUBLICA", "").rstrip("/")
        r = _pedir(
            f"{self._base}/v2/checkout/orders",
            metodo="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "PayPal-Request-Id": checkout.id,  # idempotencia
            },
            datos={
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "reference_id": checkout.id,
                        "description": f"Matcher {checkout.plan.capitalize()} ({checkout.periodo})",
                        "amount": {
                            "currency_code": checkout.moneda,
                            "value": f"{checkout.monto:.2f}",
                        },
                    }
                ],
                "application_context": {
                    "return_url": f"{base}/#/pago/{checkout.id}",
                    "cancel_url": f"{base}/#/planes",
                },
            },
        )
        checkout.referencia_externa = r.get("id", "")
        enlace = next((e["href"] for e in r.get("links", []) if e.get("rel") == "approve"), "")
        if not enlace:
            raise DatosInvalidos("PayPal no devolvió un enlace de aprobación")
        checkout.url = enlace
        return checkout

    def verificar_webhook(self, cuerpo: bytes, cabeceras: dict) -> bool:
        """PayPal no firma con HMAC local: hay que preguntarle a su propia API
        `/v1/notifications/verify-webhook-signature` si el evento es genuino,
        usando el `webhook_id` configurado en el panel de desarrollador."""
        webhook_id = os.getenv("PAYPAL_WEBHOOK_ID")
        if not webhook_id:
            return False
        try:
            evento = json.loads(cuerpo or b"{}")
        except json.JSONDecodeError:
            return False
        token = self._token()
        r = _pedir(
            f"{self._base}/v1/notifications/verify-webhook-signature",
            metodo="POST",
            headers={"Authorization": f"Bearer {token}"},
            datos={
                "auth_algo": cabeceras.get("paypal-auth-algo", ""),
                "cert_url": cabeceras.get("paypal-cert-url", ""),
                "transmission_id": cabeceras.get("paypal-transmission-id", ""),
                "transmission_sig": cabeceras.get("paypal-transmission-sig", ""),
                "transmission_time": cabeceras.get("paypal-transmission-time", ""),
                "webhook_id": webhook_id,
                "webhook_event": evento,
            },
        )
        return r.get("verification_status") == "SUCCESS"

    def esta_pagado(self, referencia: str, referencia_externa: str) -> bool:
        """La orden tiene que estar COMPLETED. `APPROVED` NO alcanza: quiere
        decir que la persona apretó el botón pero la plata todavía no se
        capturó, y una orden aprobada puede quedar sin capturar para siempre."""
        if not referencia_externa:
            return False
        r = _pedir(
            f"{self._base}/v2/checkout/orders/{urllib.parse.quote(referencia_externa)}",
            headers={"Authorization": f"Bearer {self._token()}"},
        )
        return r.get("status") == "COMPLETED"

    def referencia_de_notificacion(self, datos: dict) -> str | None:
        return next(
            (
                u.get("reference_id")
                for u in datos.get("resource", {}).get("purchase_units", [])
            ),
            None,
        )


class PasarelaDLocal(Pasarela):
    """Payments API de dLocal, pensada para tarjetas y medios locales de
    Latinoamérica. Documentación: https://docs.dlocal.com/

    Credenciales: `DLOCAL_X_LOGIN`, `DLOCAL_X_TRANS_KEY` y `DLOCAL_SECRET_KEY`
    (las tres las da dLocal al dar de alta el comercio).
    """

    nombre = "dlocal"
    API = "https://api.dlocal.com"

    def _firmar(self, x_login: str, x_date: str, cuerpo: str, secreto: str) -> str:
        mensaje = f"{x_login}{x_date}{cuerpo}"
        return hmac.new(secreto.encode(), mensaje.encode(), hashlib.sha256).hexdigest()

    def crear_checkout(self, checkout: Checkout) -> Checkout:
        x_login = os.getenv("DLOCAL_X_LOGIN")
        x_trans_key = os.getenv("DLOCAL_X_TRANS_KEY")
        secreto = os.getenv("DLOCAL_SECRET_KEY")
        if not (x_login and x_trans_key and secreto):
            raise DatosInvalidos(
                "faltan DLOCAL_X_LOGIN / DLOCAL_X_TRANS_KEY / DLOCAL_SECRET_KEY; configurá la "
                "pasarela o usá MATCHER_PASARELA=demo"
            )
        base = os.getenv("MATCHER_URL_PUBLICA", "").rstrip("/")
        cuerpo = {
            "amount": checkout.monto,
            "currency": checkout.moneda,
            "country": "UY",
            "payment_method_flow": "REDIRECT",
            "order_id": checkout.id,
            "description": f"Matcher {checkout.plan.capitalize()} ({checkout.periodo})",
            "notification_url": f"{base}/api/pagos/webhook/dlocal",
            "callback_url": f"{base}/#/pago/{checkout.id}",
        }
        cuerpo_json = json.dumps(cuerpo)
        x_date = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
        firma = self._firmar(x_login, x_date, cuerpo_json, secreto)
        pedido = urllib.request.Request(
            f"{self.API}/payments",
            data=cuerpo_json.encode(),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Login": x_login,
                "X-Trans-Key": x_trans_key,
                "X-Date": x_date,
                "X-Version": "2.1",
                "Authorization": f"V2-HMAC-SHA256, Signature: {firma}",
            },
        )
        try:
            with urllib.request.urlopen(pedido, timeout=20) as r:
                r = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raise DatosInvalidos(f"dLocal rechazó el pedido (HTTP {e.code})") from e
        checkout.referencia_externa = r.get("id", "")
        checkout.url = r.get("redirect_url", "")
        if not checkout.url:
            raise DatosInvalidos("dLocal no devolvió una URL de pago")
        return checkout

    def verificar_webhook(self, cuerpo: bytes, cabeceras: dict) -> bool:
        secreto = os.getenv("DLOCAL_SECRET_KEY")
        firma = cabeceras.get("authorization", "")
        if not secreto or not firma:
            return False
        esperado = hmac.new(secreto.encode(), cuerpo or b"", hashlib.sha256).hexdigest()
        return hmac.compare_digest(esperado, firma.replace("hmac ", "").strip())

    def esta_pagado(self, referencia: str, referencia_externa: str) -> bool:
        """dLocal marca `PAID` cuando la plata está. `AUTHORIZED` es sólo una
        retención sobre la tarjeta: todavía se puede caer."""
        x_login = os.getenv("DLOCAL_X_LOGIN")
        x_trans_key = os.getenv("DLOCAL_X_TRANS_KEY")
        secreto = os.getenv("DLOCAL_SECRET_KEY")
        if not (x_login and x_trans_key and secreto and referencia_externa):
            return False
        x_date = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
        firma = self._firmar(x_login, x_date, "", secreto)
        pedido = urllib.request.Request(
            f"{self.API}/payments/{urllib.parse.quote(referencia_externa)}",
            method="GET",
            headers={
                "X-Date": x_date,
                "X-Login": x_login,
                "X-Trans-Key": x_trans_key,
                "X-Version": "2.1",
                "Authorization": f"V2-HMAC-SHA256, Signature: {firma}",
            },
        )
        try:
            with urllib.request.urlopen(pedido, timeout=20) as r:
                datos = json.loads(r.read().decode() or "{}")
        except (urllib.error.HTTPError, urllib.error.URLError):
            return False
        return datos.get("status") == "PAID"

    def referencia_de_notificacion(self, datos: dict) -> str | None:
        return datos.get("order_id")


class PasarelaStripe(Pasarela):
    """Esqueleto, no pedido para este lanzamiento pero se deja enchufable.
    Requiere `STRIPE_API_KEY`; sin eso levanta un error explícito en vez de
    fingir que cobró."""

    nombre = "stripe"

    def crear_checkout(self, checkout: Checkout) -> Checkout:
        if not os.getenv("STRIPE_API_KEY"):
            raise DatosInvalidos(
                "falta STRIPE_API_KEY; configurá la pasarela o usá MATCHER_PASARELA=demo"
            )
        raise NotImplementedError(
            "Integración de Stripe pendiente: crear la Checkout Session y devolver su URL."
        )

    def verificar_webhook(self, cuerpo: bytes, cabeceras: dict) -> bool:
        raise NotImplementedError("Verificar con stripe.Webhook.construct_event")


_PASARELAS: dict[str, type[Pasarela]] = {
    "demo": PasarelaDemo,
    "mercadopago": PasarelaMercadoPago,
    "paypal": PasarelaPayPal,
    "dlocal": PasarelaDLocal,
    "stripe": PasarelaStripe,
}


def pasarela_activa() -> Pasarela:
    nombre = os.getenv("MATCHER_PASARELA", "demo").lower()
    clase = _PASARELAS.get(nombre)
    if not clase:
        raise DatosInvalidos(f"pasarela desconocida: {nombre}")
    return clase()


def pasarela_por_nombre(nombre: str) -> Pasarela:
    clase = _PASARELAS.get(nombre)
    if not clase:
        raise DatosInvalidos(f"pasarela desconocida: {nombre}")
    return clase()


def precio(plan_codigo: str, periodo: str) -> float:
    if periodo not in PERIODOS:
        raise DatosInvalidos(f"periodo inválido: {periodo} (mensual | anual)")
    plan = planes.PLANES.get(plan_codigo)
    if not plan or plan.codigo == "gratis":
        raise DatosInvalidos(f"plan no comprable: {plan_codigo}")
    return plan.precio_anual if periodo == "anual" else plan.precio_mes


def iniciar(almacen, perfil: Perfil, plan_codigo: str, periodo: str) -> Checkout:
    monto = precio(plan_codigo, periodo)
    pasarela = pasarela_activa()
    checkout = Checkout(
        id=uuid.uuid4().hex[:16],
        usuario_id=perfil.id,
        plan=plan_codigo,
        periodo=periodo,
        monto=monto,
        moneda=planes.MONEDA,
        pasarela=pasarela.nombre,
        url="",
    )
    pasarela.crear_checkout(checkout)
    almacen.registrar_pago(
        usuario_id=perfil.id,
        plan=plan_codigo,
        periodo=periodo,
        monto=monto,
        moneda=planes.MONEDA,
        estado="pendiente",
        pasarela=pasarela.nombre,
        referencia=checkout.id,
        referencia_externa=checkout.referencia_externa,
    )
    return checkout


def confirmar(almacen, perfil: Perfil, referencia: str) -> dict:
    """Da de alta el plan. Idempotente por referencia: reintentar el webhook no
    duplica los 30 días — es el bug clásico de las integraciones de pago."""
    fila = next(
        (p for p in almacen.pagos_de(perfil.id) if p["referencia"] == referencia), None
    )
    if not fila:
        raise DatosInvalidos("no existe ese pago")
    if fila["estado"] == "pagado":
        return {"ya_confirmado": True, "plan": perfil.plan}

    # SE LE PREGUNTA A LA PASARELA. Este chequeo no estaba y era el agujero más
    # grave del producto: `/api/pagos/confirmar` daba el plan de alta con sólo
    # recibir una referencia, así que cualquiera con cuenta pedía un checkout
    # de Gold, lo "confirmaba" a mano y se quedaba con el plan sin pagar un
    # peso. En `demo` sigue pasando siempre (no hay plata), pero con
    # MercadoPago, PayPal o dLocal ahora manda el proveedor.
    pasarela = pasarela_por_nombre(fila["pasarela"])
    externa = fila["referencia_externa"] if "referencia_externa" in fila.keys() else ""
    if not pasarela.esta_pagado(referencia, externa):
        raise PagoNoAcreditado(
            "el pago todavía no figura como acreditado en la pasarela. "
            "Si acabás de pagar, esperá unos segundos y volvé a intentar."
        )

    almacen.con.execute(
        "UPDATE pagos SET estado = 'pagado' WHERE referencia = ?", (referencia,)
    )
    almacen.con.commit()

    perfil.plan = fila["plan"]
    # Si todavía tiene plan vigente, se suma al vencimiento en vez de pisarlo.
    base = (
        perfil.plan_vence
        if perfil.plan_vence and perfil.plan_vence > datetime.utcnow()
        else None
    )
    perfil.plan_vence = planes.vencimiento(fila["periodo"], base)
    almacen.guardar_perfil(perfil)
    return {
        "ya_confirmado": False,
        "plan": perfil.plan,
        "vence": perfil.plan_vence.isoformat(),
        "monto": fila["monto"],
        "moneda": fila["moneda"],
    }


def confirmar_por_referencia(almacen, referencia: str) -> dict:
    """Variante de `confirmar` para el webhook: ahí no hay una sesión de
    usuario, sólo lo que avisó la pasarela. Busca a quién pertenece el pago y
    delega en `confirmar`, así la lógica de idempotencia vive en un solo
    lugar."""
    fila = almacen.pago_por_referencia(referencia)
    if not fila:
        raise DatosInvalidos("no existe ese pago")
    perfil = almacen.perfil(fila["usuario_id"])
    if not perfil:
        raise DatosInvalidos("el pago existe pero el perfil ya no")
    return confirmar(almacen, perfil, referencia)


def cancelar(almacen, perfil: Perfil) -> dict:
    """Baja del plan. No corta el acceso al toque: se respeta lo pagado hasta
    el vencimiento. Cancelar y perder el mes que ya pagaste es la razón número
    uno de los chargebacks."""
    vence = perfil.plan_vence
    almacen.con.execute(
        "UPDATE pagos SET estado = 'cancelado' WHERE usuario_id = ? AND estado = 'pendiente'",
        (perfil.id,),
    )
    almacen.con.commit()
    return {
        "cancelado": True,
        "acceso_hasta": vence.isoformat() if vence else None,
        "mensaje": "No se renueva. Mantenés el plan hasta el vencimiento.",
    }
