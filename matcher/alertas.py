"""Avisar por mail cuando alguien quiere comprar, y cuando la plata entró.

PARA QUÉ SIRVE ESTO DE VERDAD
El dueño tiene varios proyectos y el hosting pago cuesta por equipo que se
active. Pagarlo por adelantado en todos, sin saber si alguien quiere comprar en
alguno, es tirar plata contra una hipótesis. Estas dos alertas contestan la
única pregunta que decide eso: **¿hay alguien intentando pagar?**

DOS EVENTOS, Y NO VALEN LO MISMO

- `intento_de_compra` — alguien llegó al checkout. Es INTENCIÓN, no plata. Sirve
  como señal de demanda y nada más: buena parte de los checkouts no se
  completan.
- `compra_confirmada` — la pasarela dijo que el pago está acreditado. Ésta es la
  que importa, y por eso NO se agrupa ni se limita: si entró plata, sale el
  mail.

LO QUE ESTA HERRAMIENTA **NO** ARREGLA, Y CONVIENE SABERLO
No sirve para vender desde un plan de hosting que prohíbe el uso comercial. El
sitio ya ofrece la venta desde que está publicado, haya clicks o no, y la
alerta corre **adentro** de ese mismo backend: si el proveedor lo suspende, se
apaga la alerta junto con la venta. Es un medidor de demanda, no una forma de
esquivar los términos de nadie.

TRES DECISIONES QUE IMPORTAN

1. **Se dispara en el SERVIDOR, no en un `onClick`.** Un click del navegador se
   pierde con un bloqueador, se repite si la persona insiste, y no se puede
   creer porque lo manda el cliente. El checkout creado es el evento real: pasó
   por `pagos.iniciar`, quedó escrito en la tabla `pagos` y tiene monto y plan
   de verdad.
2. **El aviso va en segundo plano.** El usuario está esperando el redirect a
   MercadoPago; meterle un HTTP más con su timeout en el camino de una compra
   es el peor lugar para agregar latencia (ver `aviso.mandar_en_segundo_plano`).
3. **Nunca levanta.** Si el mail falla, la compra sigue. El pago ya está en la
   base y en el panel: lo que se pierde es el empujón, no el dato.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from . import aviso

# Cada cuánto, como mucho, se avisa una INTENCIÓN de la misma persona. Alguien
# que vuelve tres veces al checkout es una sola señal, no tres mails. La compra
# confirmada no pasa por acá: ésa sale siempre.
VENTANA_INTENCION = timedelta(hours=6)


def _activa(variable: str) -> bool:
    return os.getenv(variable, "1").strip() != "0"


def _nunca_explota(fn):
    """Envuelve una alerta para que NINGÚN error suyo salga hacia afuera.

    NO ES DECORACIÓN DEFENSIVA: esto se escribió porque el test
    `test_si_el_mail_explota_la_compra_sigue` lo encontró en rojo. El
    encabezado de este módulo ya decía "nunca levanta" y el código no lo
    cumplía — alcanzaba con que fallara la consulta de contexto, o el propio
    `Thread.start()`, para que la excepción subiera por `pagos.iniciar` y se
    llevara puesto el checkout.

    Ahí la herramienta que existe para no perder ventas pasa a ser la que las
    pierde, y encima sólo cuando el proveedor de correo está caído: o sea, el
    día que menos se lo mira.

    El error se traga sin loguear el detalle, por lo mismo de siempre: un
    mensaje de fallo de correo suele traer adentro la dirección de destino.
    """

    def envuelta(*args, **kwargs) -> bool:
        try:
            return fn(*args, **kwargs)
        except Exception:
            return False

    envuelta.__name__ = fn.__name__
    envuelta.__doc__ = fn.__doc__
    return envuelta


def _plata(monto: float, moneda: str) -> str:
    return f"{moneda} {monto:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def _repetida(almacen, usuario_id: str, ahora: datetime) -> bool:
    """¿Ya se avisó una intención de esta persona hace poco?

    Se cuenta sobre la tabla `pagos`, que ya existe: cada checkout deja su fila
    en `pendiente`. Un contador aparte sería una tabla más para mantener y otra
    cosa que se puede desincronizar del dato real.

    La fila del checkout de AHORA ya está escrita cuando esto corre, así que
    "hay más de una en la ventana" significa "ya hubo otra antes".
    """
    desde = (ahora - VENTANA_INTENCION).isoformat()
    fila = almacen.con.execute(
        "SELECT COUNT(*) c FROM pagos WHERE usuario_id = ? AND momento >= ?",
        (usuario_id, desde),
    ).fetchone()
    return (fila["c"] if fila else 0) > 1


def _contexto(almacen) -> str:
    """Números que hacen que el mail sirva para decidir algo, en vez de ser
    sólo una notificación más."""
    cobrados = almacen.con.execute(
        "SELECT COUNT(*) c, COALESCE(SUM(monto), 0) t FROM pagos WHERE estado = 'pagado'"
    ).fetchone()
    intentos = almacen.con.execute(
        "SELECT COUNT(*) c FROM pagos WHERE momento >= ?",
        ((datetime.utcnow() - timedelta(days=30)).isoformat(),),
    ).fetchone()
    return (
        f"Contexto:\n"
        f"  Intentos de compra (30 días): {intentos['c'] if intentos else 0}\n"
        f"  Cobros acreditados (total):   {cobrados['c'] if cobrados else 0}\n"
        f"  Facturado (bruto, total):     {cobrados['t'] if cobrados else 0:.2f}\n"
    )


@_nunca_explota
def intento_de_compra(almacen, perfil, checkout, ahora: datetime | None = None) -> bool:
    """Alguien llegó al checkout. Devuelve si se mandó el aviso.

    Se puede apagar con `MATCHER_ALERTA_INTENCION=0` sin tocar la de la compra
    confirmada: si algún día hay volumen, ésta se vuelve ruido y la otra no.
    """
    if not _activa("MATCHER_ALERTA_INTENCION"):
        return False
    momento = ahora or datetime.utcnow()
    if _repetida(almacen, perfil.id, momento):
        return False

    aviso.mandar_en_segundo_plano(
        f"Matcher · alguien quiere comprar {checkout.plan.capitalize()} "
        f"({_plata(checkout.monto, checkout.moneda)})",
        (
            f"Alguien abrió el checkout. TODAVÍA NO PAGÓ.\n\n"
            f"Quién:    {perfil.nombre} <{perfil.email}>\n"
            f"Plan:     {checkout.plan} ({checkout.periodo})\n"
            f"Monto:    {_plata(checkout.monto, checkout.moneda)}\n"
            f"Pasarela: {checkout.pasarela}\n"
            f"Cuándo:   {momento.isoformat(timespec='seconds')} UTC\n\n"
            f"{_contexto(almacen)}\n"
            f"Si completa el pago te llega un segundo mail que dice COBRADO.\n"
            f"Éste es sólo intención: buena parte de los checkouts no se terminan.\n"
        ),
        responder_a=perfil.email,
    )
    return True


@_nunca_explota
def compra_confirmada(almacen, perfil, fila, ahora: datetime | None = None) -> bool:
    """La pasarela dijo que la plata entró. Esta alerta NO se agrupa ni se
    silencia por volumen: es el único mail que significa dinero."""
    if not _activa("MATCHER_ALERTA_COBRO"):
        return False
    momento = ahora or datetime.utcnow()
    monto = fila["monto"]
    moneda = fila["moneda"]

    aviso.mandar_en_segundo_plano(
        f"Matcher · COBRADO {_plata(monto, moneda)} · {fila['plan'].capitalize()}",
        (
            f"Entró un pago.\n\n"
            f"Quién:    {perfil.nombre} <{perfil.email}>\n"
            f"Plan:     {fila['plan']} ({fila['periodo']})\n"
            f"Monto:    {_plata(monto, moneda)}\n"
            f"Pasarela: {fila['pasarela']}\n"
            f"Cuándo:   {momento.isoformat(timespec='seconds')} UTC\n\n"
            f"{_contexto(almacen)}\n"
            f"El neto es menor: la pasarela descuenta su comisión y los\n"
            f"impuestos van aparte. El panel lo muestra estimado.\n"
        ),
        responder_a=perfil.email,
    )
    return True
