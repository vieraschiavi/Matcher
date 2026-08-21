"""Las cuentas del dueño: acceso completo sin pasar por la caja.

POR QUÉ HACE FALTA

En la demo, las cuentas del dueño vienen sembradas con Gold (`demo.py`). Pero
en producción la siembra se apaga (`MATCHER_DEMO=0`), y ahí el dueño del
producto se queda sin forma de tener su propia app en Gold: tendría que
pagarse a sí mismo con tarjeta, cobrarse la comisión de MercadoPago y esperar
la acreditación. Absurdo.

CÓMO FUNCIONA

Una lista de emails en la variable de entorno `MATCHER_CUENTAS_DUENIO`,
separados por coma. Esas cuentas quedan en Gold al entrar.

    MATCHER_CUENTAS_DUENIO=vieraschiavi@gmail.com,arcortito@gmail.com

POR QUÉ ES SEGURO, Y QUÉ LO HACE SEGURO

- **No es un endpoint.** No hay ninguna ruta HTTP que otorgue planes. La lista
  sólo se puede tocar desde el panel de la plataforma donde está desplegado,
  que es exactamente el mismo lugar desde donde se puede tirar abajo la app
  entera. Quien puede editar esto ya podía todo.
- **No hay valor por defecto.** Sin la variable, la lista está vacía y esto no
  hace nada. Nunca hay una cuenta privilegiada "de fábrica" — que es el bug con
  el que se cuelan la mitad de los productos (el admin/admin de siempre).
- **La comparación es exacta y en minúsculas**, sin comodines: no se puede
  poner `*@gmail.com` y quedarse con medio mundo adentro.
- **No toca los pagos.** No inventa una fila en `pagos` ni marca nada como
  cobrado: sólo levanta el plan. La contabilidad sigue mostrando lo que se
  cobró de verdad, que es lo que hay que mirar para saber cómo va el negocio.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

# Cuánto dura el Gold del dueño antes de renovarse solo al volver a entrar. No
# es "para siempre" para que una cuenta que se saca de la lista deje de tener
# Gold sola, sin que nadie se acuerde de bajarla a mano.
DIAS = 365

PLAN = "gold"


def emails() -> set[str]:
    crudo = os.getenv("MATCHER_CUENTAS_DUENIO", "")
    return {e.strip().lower() for e in crudo.split(",") if e.strip()}


def es_duenio(email: str) -> bool:
    return bool(email) and email.strip().lower() in emails()


def aplicar(almacen, perfil) -> bool:
    """Si es cuenta del dueño y le falta el plan, se lo pone. Devuelve si tocó
    algo, para no escribir en la base en cada pedido."""
    if not es_duenio(getattr(perfil, "email", "")):
        return False

    vence = getattr(perfil, "plan_vence", None)
    # Se renueva sólo cuando queda poco: sin este corte, cada login reescribiría
    # el perfil entero por nada.
    falta_poco = not vence or vence < datetime.utcnow() + timedelta(days=30)
    if perfil.plan == PLAN and not falta_poco:
        return False

    perfil.plan = PLAN
    perfil.plan_vence = datetime.utcnow() + timedelta(days=DIAS)
    almacen.guardar_perfil(perfil)
    return True
