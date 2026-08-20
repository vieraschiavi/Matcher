"""Segunda vuelta: la gente que descartaste y que quizás descartaste mal.

Ninguna de las apps grandes tiene esto, y es a propósito de ellas: Tinder
vende el "rewind" del último descarte como función paga e inmediata, y lo que
pasó hace tres semanas se perdió para siempre. Acá es al revés, y con una
tesis: **el descarte a las 2 de la mañana con el pulgar en piloto automático
no es una opinión, es un reflejo.** A la semana, esa persona que pasaste sin
mirar puede ser exactamente lo que buscás.

Las reglas:

- Sólo aparecen descartes con más de `DIAS_ESPERA` días. El período de espera
  ES el producto: sin él, esto sería un "deshacer" y competiría con rebobinar
  (que es lo pago). Con él, es otra cosa — una segunda mirada con la cabeza
  fría, que rebobinar no puede dar.
- La lista respeta los filtros duros DE HOY (regla 1): si después del descarte
  pediste "sólo mujeres", acá no aparece un hombre que descartaste antes.
- **Mirar la lista es gratis** (regla 4: nunca se cobra el derecho a filtrar ni
  a mirar). Dar la segunda oportunidad gasta un like común, así que el volumen
  ya está limitado por el plan sin inventar un cupo nuevo.
- Repescar borra el `pass` viejo y registra un `like`. Si la otra persona te
  había likeado mientras tanto, el match sale en el acto — que es el mejor
  final posible para esta pantalla.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from . import filtros, scoring
from .modelos import DatosInvalidos, Perfil

DIAS_ESPERA = 7
TOPE_LISTA = 30


def _corte(ahora: datetime | None) -> datetime:
    return (ahora or datetime.utcnow()) - timedelta(days=DIAS_ESPERA)


def candidatos(
    almacen, perfil: Perfil, *, limite: int = TOPE_LISTA, ahora: datetime | None = None
) -> list[dict]:
    """Descartes viejos que hoy volverías a mirar. Ordenados por compatibilidad:
    esta pantalla existe para encontrar al que descartaste mal, así que el más
    probable va primero."""
    corte = _corte(ahora)
    filas = almacen.con.execute(
        "SELECT a_id, momento FROM interacciones "
        "WHERE de_id = ? AND tipo = 'pass' AND momento < ? ORDER BY momento ASC",
        (perfil.id, corte.isoformat()),
    ).fetchall()

    salida = []
    for f in filas:
        otro = almacen.perfil(f["a_id"])
        if not otro or not otro.activo or not otro.completo:
            continue
        if not filtros.pasa_filtros(perfil, otro, reciproco=False)[0]:
            continue
        comp, _ = scoring.compatibilidad(perfil, otro)
        hace_dias = max(
            DIAS_ESPERA, ((ahora or datetime.utcnow()) - datetime.fromisoformat(f["momento"])).days
        )
        salida.append(otro.a_dict() | {"compatibilidad": comp, "hace_dias": hace_dias})

    salida.sort(key=lambda d: (-d["compatibilidad"], d["id"]))
    return salida[: max(1, min(limite, TOPE_LISTA))]


def repescar(almacen, perfil: Perfil, a_id: str, *, ahora: datetime | None = None) -> dict:
    """Da la segunda oportunidad: borra el descarte y registra el like.

    El borrado va primero porque `interactuar` rechaza pares repetidos ("ya
    interactuaste"). El like pasa por el camino normal a propósito: consume
    cupo del plan (SinCupo → 402 → muro de pago, como cualquier like) y crea
    el match si el interés es mutuo. Un camino especial que no gastara cupo
    sería un like ilimitado gratis con un paso extra.
    """
    fila = almacen.con.execute(
        "SELECT momento FROM interacciones WHERE de_id = ? AND a_id = ? AND tipo = 'pass'",
        (perfil.id, a_id),
    ).fetchone()
    if not fila:
        raise DatosInvalidos("a esa persona no la descartaste, o ya le respondiste de nuevo")
    if datetime.fromisoformat(fila["momento"]) >= _corte(ahora):
        # La espera es la diferencia entre esto y el rebobinar pago: si se
        # pudiera repescar al toque, nadie pagaría rebobinar y esta pantalla
        # sería un "deshacer" con vueltas.
        raise DatosInvalidos(
            f"ese descarte es reciente; la segunda vuelta abre a los {DIAS_ESPERA} días"
        )

    almacen.con.execute(
        "DELETE FROM interacciones WHERE de_id = ? AND a_id = ? AND tipo = 'pass'",
        (perfil.id, a_id),
    )
    almacen.con.commit()
    return almacen.interactuar(perfil, a_id, "like", ahora=ahora)
