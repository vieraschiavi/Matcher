"""Match automático.

Qué es y qué NO es. La app propone un match cuando dos personas se pasan
mutuamente todos los filtros duros y la compatibilidad supera el umbral. No
inventa afinidad: si el par no se pasa los filtros del otro, no hay propuesta,
por vacío que esté el deck. Bajar el umbral para llenar la bandeja es lo que
hace que la gente deje de creerle al porcentaje.

El match automático se crea marcado (`automatico=True`) y cualquiera de los dos
puede deshacerlo. Se muestra distinto en la UI: nadie deslizó, lo propuso el
algoritmo, y decirlo es la diferencia entre una función y un engaño.
"""

from __future__ import annotations

from datetime import date, datetime

from . import filtros, scoring
from .modelos import Perfil

# Umbral de compatibilidad para proponer. 72/100 es alto a propósito: por
# debajo de eso las propuestas se sienten al azar.
UMBRAL = 72.0


def sugerencias(
    almacen,
    perfil: Perfil,
    *,
    limite: int = 10,
    umbral: float = UMBRAL,
    hoy: date | None = None,
    ahora: datetime | None = None,
) -> list[dict]:
    """Candidatos que calificarían para match automático, sin crearlo.

    Se excluye a quien ya se descartó o con quien ya hay match. Un automatch
    con alguien a quien pasaste es la peor experiencia posible.
    """
    universo = [p for p in almacen.todos() if p.id != perfil.id]
    vistos = almacen.vistos_por(perfil.id)
    ya_match = {m["con"]["id"] for m in almacen.matches_de(perfil.id)}
    elegibles = [
        o
        for o in filtros.candidatos(perfil, universo, vistos=vistos, hoy=hoy)
        if o.id not in ya_match
    ]

    salida = []
    for otro in elegibles:
        comp, desglose = scoring.compatibilidad(perfil, otro, hoy=hoy)
        # Simétrico de verdad: se exige que TAMBIÉN pase los filtros del otro
        # (no sólo género y edad, que es lo que chequea el deck recíproco).
        ok_inverso, _ = filtros.pasa_filtros(otro, perfil, hoy=hoy, reciproco=False)
        if not ok_inverso or comp < umbral:
            continue
        salida.append(
            {
                "perfil": otro,
                "compatibilidad": comp,
                "motivos": scoring.motivos(perfil, otro, desglose),
                "actividad": scoring.actividad(otro, ahora),
            }
        )
    salida.sort(key=lambda s: (-s["compatibilidad"], -s["actividad"], s["perfil"].id))
    return salida[:limite]


def proponer(
    almacen,
    perfil: Perfil,
    *,
    umbral: float = UMBRAL,
    ahora: datetime | None = None,
) -> list[dict]:
    """Crea los matches automáticos que le quedan de cupo hoy."""
    ahora = ahora or datetime.utcnow()
    cupos = almacen.cupos(perfil, ahora)
    disponibles = max(0, (cupos["automatch_max"] or 0) - cupos["automatch_hoy"])
    if disponibles == 0:
        return []

    creados = []
    for s in sugerencias(almacen, perfil, limite=disponibles, umbral=umbral, ahora=ahora):
        otro: Perfil = s["perfil"]
        m = almacen._crear_match(
            perfil.id, otro.id, automatico=True, compatibilidad=s["compatibilidad"], ahora=ahora
        )
        creados.append(
            {
                "match_id": m.id,
                "con": otro.a_dict(),
                "compatibilidad": s["compatibilidad"],
                "motivos": s["motivos"],
            }
        )
    return creados
