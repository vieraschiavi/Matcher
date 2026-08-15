"""Boost: media hora arriba del deck de la gente de tu zona.

Lo que compra el plan pago es **visibilidad temporal**, no privilegio
permanente. La diferencia importa: el multiplicador de plan que ya existía en
`scoring.BOOST_PLAN` es un empujón chico y constante (8–15%); el boost es
grande pero dura 30 minutos y se gasta.

Tres reglas:

- **Se gasta.** El cupo es mensual y por plan (Plus 1, Gold 4). Sin cupo no
  se activa; el gratis directamente no lo tiene y la UI lo dice.
- **No rompe la ola ni los filtros.** El boost multiplica el puntaje, pero
  `ordenar_deck` sigue ordenando por ola antes que por puntaje (regla 3) y
  `filtros` sigue descartando (regla 1). Un boost NO te mete en el deck de
  alguien que te filtró — eso sería vender el derecho a saltarse el filtro
  de otro, que es exactamente lo que hace la competencia.
- **Se ve mientras corre.** El tiempo restante viaja al frontend; un boost
  que no se nota es plata tirada, y es la queja número uno del feature en
  las reseñas de las otras apps.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from . import planes
from .modelos import DatosInvalidos, Perfil

DURACION = timedelta(minutes=30)

# Cuánto multiplica el puntaje mientras corre. 2.2 es fuerte pero no absurdo:
# con 3+ el deck de la zona se llena de una sola persona y se nota el truco.
MULTIPLICADOR = 2.2


class SinBoosts(DatosInvalidos):
    """Se acabaron los del mes. La API lo traduce a 402, igual que los likes."""

    def __init__(self, maximo: int):
        super().__init__(
            "no tenés boosts disponibles este mes"
            if maximo
            else "el boost es de los planes pagos"
        )
        self.maximo = maximo


def _mes(ahora: datetime) -> str:
    return ahora.strftime("%Y-%m")


def usados_en_el_mes(almacen, usuario_id: str, ahora: datetime | None = None) -> int:
    ahora = ahora or datetime.utcnow()
    fila = almacen.con.execute(
        "SELECT COUNT(*) c FROM boosts WHERE usuario_id = ? AND mes = ?",
        (usuario_id, _mes(ahora)),
    ).fetchone()
    return fila["c"]


def activo(almacen, usuario_id: str, ahora: datetime | None = None) -> dict | None:
    """El boost en curso, o None. Se calcula por vencimiento y no con un flag
    `activo` en la tabla: un flag hay que apagarlo con un job, y sin job queda
    prendido para siempre."""
    ahora = ahora or datetime.utcnow()
    fila = almacen.con.execute(
        "SELECT * FROM boosts WHERE usuario_id = ? ORDER BY inicio DESC LIMIT 1",
        (usuario_id,),
    ).fetchone()
    if not fila:
        return None
    inicio = datetime.fromisoformat(fila["inicio"])
    fin = inicio + DURACION
    if ahora >= fin:
        return None
    return {
        "inicio": fila["inicio"],
        "fin": fin.isoformat(),
        "segundos_restantes": int((fin - ahora).total_seconds()),
    }


def estado(almacen, perfil: Perfil, ahora: datetime | None = None) -> dict:
    ahora = ahora or datetime.utcnow()
    maximo = planes.limites_de(perfil).boost_por_mes
    usados = usados_en_el_mes(almacen, perfil.id, ahora)
    return {
        "maximo_mes": maximo,
        "usados_mes": usados,
        "restantes": max(0, maximo - usados),
        "duracion_min": int(DURACION.total_seconds() // 60),
        "multiplicador": MULTIPLICADOR,
        "en_curso": activo(almacen, perfil.id, ahora),
    }


def activar(almacen, perfil: Perfil, ahora: datetime | None = None) -> dict:
    ahora = ahora or datetime.utcnow()
    en_curso = activo(almacen, perfil.id, ahora)
    if en_curso:
        # No se apila: activar otro encima tiraría el que ya está corriendo y
        # el usuario perdería un cupo sin ganar un minuto.
        return {"ya_estaba": True, **estado(almacen, perfil, ahora)}

    maximo = planes.limites_de(perfil).boost_por_mes
    if usados_en_el_mes(almacen, perfil.id, ahora) >= maximo:
        raise SinBoosts(maximo)

    almacen.con.execute(
        "INSERT INTO boosts (id, usuario_id, mes, inicio) VALUES (?,?,?,?)",
        (uuid.uuid4().hex[:12], perfil.id, _mes(ahora), ahora.isoformat()),
    )
    almacen.con.commit()
    return {"ya_estaba": False, **estado(almacen, perfil, ahora)}


def multiplicador_de(almacen, usuario_id: str, ahora: datetime | None = None) -> float:
    """Lo que usa el orden del deck. 1.0 si no hay boost corriendo."""
    return MULTIPLICADOR if activo(almacen, usuario_id, ahora) else 1.0
