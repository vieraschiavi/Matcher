"""Plataforma de pago.

Estado real, dicho sin vueltas: acá está el **flujo completo** (catálogo →
checkout → confirmación → alta del plan → historial), con una pasarela `demo`
que confirma en el acto para poder probar la app de punta a punta sin cuentas
de comercio. Enchufar Stripe o Mercado Pago es implementar `Pasarela` y
devolver la URL real de checkout: el resto del sistema no cambia.

Lo que NO hace y hay que hacer antes de cobrarle a alguien de verdad:
  * verificar la firma del webhook de la pasarela (`verificar_webhook`),
  * guardar el id de la transacción como clave de idempotencia,
  * facturación e impuestos por país.
Las claves de la pasarela se leen de variables de entorno. No se loguean, no
se guardan en la base y no se devuelven por la API.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime

from . import planes
from .modelos import DatosInvalidos, Perfil

PERIODOS = ("mensual", "anual")


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


class Pasarela:
    """Interfaz mínima. Implementala para enchufar un proveedor real."""

    nombre = "abstracta"

    def crear_checkout(self, checkout: Checkout) -> Checkout:  # pragma: no cover
        raise NotImplementedError

    def verificar_webhook(self, cuerpo: bytes, firma: str) -> bool:  # pragma: no cover
        raise NotImplementedError


class PasarelaDemo(Pasarela):
    """Confirma en el acto. Es la que usa la demo y los tests.

    No mueve plata y lo dice: la URL que devuelve es interna de la app, no de
    un proveedor. Nunca la dejes activa en una build de producción — por eso
    `pasarela_activa()` mira `MATCHER_PASARELA` y avisa.
    """

    nombre = "demo"

    def crear_checkout(self, checkout: Checkout) -> Checkout:
        checkout.url = f"/#/pago/{checkout.id}"
        return checkout

    def verificar_webhook(self, cuerpo: bytes, firma: str) -> bool:
        return True


class PasarelaStripe(Pasarela):
    """Esqueleto. Requiere `STRIPE_API_KEY` y el SDK; sin eso levanta un error
    explícito en vez de fingir que cobró."""

    nombre = "stripe"

    def crear_checkout(self, checkout: Checkout) -> Checkout:
        if not os.getenv("STRIPE_API_KEY"):
            raise DatosInvalidos(
                "falta STRIPE_API_KEY; configurá la pasarela o usá MATCHER_PASARELA=demo"
            )
        raise NotImplementedError(
            "Integración de Stripe pendiente: crear la Checkout Session y devolver su URL."
        )

    def verificar_webhook(self, cuerpo: bytes, firma: str) -> bool:
        raise NotImplementedError("Verificar con stripe.Webhook.construct_event")


_PASARELAS: dict[str, type[Pasarela]] = {
    "demo": PasarelaDemo,
    "stripe": PasarelaStripe,
}


def pasarela_activa() -> Pasarela:
    nombre = os.getenv("MATCHER_PASARELA", "demo").lower()
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
