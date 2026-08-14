"""Filtros duros: quién puede aparecerle a quién.

Un filtro duro descarta; el scoring sólo ordena. Están separados a propósito:
si "equipo de fútbol" fuese un peso más del score, un usuario que pide sólo
hinchas de Peñarol igual vería a otros arriba del deck porque compensan por
otro lado, y eso es exactamente la queja de "puse filtros y no los respeta"
que aparece en las reseñas de la competencia.
"""

from __future__ import annotations

from datetime import date

from . import geo
from .modelos import Perfil, Preferencias

# Motivos de descarte. Se devuelven para poder explicarle al usuario por qué su
# deck quedó vacío ("nadie de 1,90 m de izquierda en tu ciudad") en vez de
# mostrar una pantalla vacía sin explicación.
MOTIVOS = {
    "yo_mismo": "es tu propio perfil",
    "inactivo": "perfil desactivado",
    "incompleto": "perfil sin foto de portada",
    "genero": "no coincide con lo que buscás",
    "genero_inverso": "vos no coincidís con lo que busca",
    "edad": "fuera del rango de edad",
    "edad_inversa": "estás fuera del rango de edad que pide",
    "altura": "fuera del rango de altura",
    "politica": "postura política filtrada",
    "equipo": "equipo de fútbol filtrado",
    "pais": "fuera de tu país",
    "distancia": "más lejos que tu radio",
    "verificado": "perfil no verificado",
    "visto": "ya lo viste",
}


def _genero_compatible(busca: str, genero: str) -> bool:
    if busca == "todos":
        return True
    if busca == "mujeres":
        return genero == "mujer"
    if busca == "hombres":
        return genero == "hombre"
    return True


def _no_binario_siempre_visible(busca: str, genero: str) -> bool:
    """Las personas no binarias entran en cualquier búsqueda salvo que el otro
    haya elegido explícitamente un único género. Se decidió así para no
    dejarlas fuera del producto por default, que es el reclamo histórico."""
    return genero == "no_binario" and busca == "todos"


def distancia_entre(a: Perfil, b: Perfil) -> float | None:
    ca, cb = geo.coordenadas(a.ciudad), geo.coordenadas(b.ciudad)
    if not ca or not cb:
        return None
    return geo.distancia_km(ca, cb)


def pasa_filtros(
    yo: Perfil,
    otro: Perfil,
    *,
    vistos: set[str] | None = None,
    hoy: date | None = None,
    reciproco: bool = True,
) -> tuple[bool, str]:
    """¿`otro` puede aparecer en el deck de `yo`?

    `reciproco=True` exige además que YO pase los filtros de género y edad de
    `otro`. Sin eso el deck se llena de gente que nunca me va a dar like, que
    es la forma más rápida de que un usuario nuevo se vaya: mucho swipe, cero
    match.
    """
    hoy = hoy or date.today()
    p: Preferencias = yo.preferencias

    if otro.id == yo.id:
        return False, "yo_mismo"
    if not otro.activo:
        return False, "inactivo"
    if not otro.completo:
        return False, "incompleto"
    if vistos and otro.id in vistos:
        return False, "visto"

    # -- género ------------------------------------------------------------
    if not (
        _genero_compatible(p.busca, otro.genero)
        or _no_binario_siempre_visible(p.busca, otro.genero)
    ):
        return False, "genero"

    # -- edad --------------------------------------------------------------
    edad_otro = otro.edad(hoy)
    if not (p.edad_min <= edad_otro <= p.edad_max):
        return False, "edad"

    # -- altura ------------------------------------------------------------
    if p.altura_min_cm is not None and otro.altura_cm < p.altura_min_cm:
        return False, "altura"
    if p.altura_max_cm is not None and otro.altura_cm > p.altura_max_cm:
        return False, "altura"

    # -- política ----------------------------------------------------------
    if p.politicas and otro.politica not in p.politicas:
        return False, "politica"

    # -- equipo de fútbol --------------------------------------------------
    # La lista del usuario viene del catálogo de SU país. Se compara
    # normalizado porque el mismo club se escribe de varias formas.
    if p.equipos:
        elegidos = {geo.normalizar(e) for e in p.equipos}
        if geo.normalizar(otro.equipo) not in elegidos:
            return False, "equipo"

    # -- localización ------------------------------------------------------
    if p.solo_mi_pais and otro.pais != yo.pais:
        return False, "pais"
    if p.distancia_max_km is not None:
        d = distancia_entre(yo, otro)
        if d is not None and d > p.distancia_max_km:
            return False, "distancia"

    if p.solo_verificados and not otro.verificado:
        return False, "verificado"

    # -- reciprocidad ------------------------------------------------------
    if reciproco:
        q = otro.preferencias
        if not (
            _genero_compatible(q.busca, yo.genero)
            or _no_binario_siempre_visible(q.busca, yo.genero)
        ):
            return False, "genero_inverso"
        if not (q.edad_min <= yo.edad(hoy) <= q.edad_max):
            return False, "edad_inversa"

    return True, ""


def candidatos(
    yo: Perfil,
    universo: list[Perfil],
    *,
    vistos: set[str] | None = None,
    hoy: date | None = None,
    reciproco: bool = True,
) -> list[Perfil]:
    return [
        o
        for o in universo
        if pasa_filtros(yo, o, vistos=vistos, hoy=hoy, reciproco=reciproco)[0]
    ]


def diagnostico(
    yo: Perfil,
    universo: list[Perfil],
    *,
    vistos: set[str] | None = None,
    hoy: date | None = None,
) -> dict[str, int]:
    """Cuántos perfiles descartó cada filtro. Alimenta el mensaje de 'deck
    vacío' del frontend, que sugiere qué filtro aflojar."""
    conteo: dict[str, int] = {}
    for o in universo:
        ok, motivo = pasa_filtros(yo, o, vistos=vistos, hoy=hoy)
        if not ok and motivo not in ("yo_mismo",):
            conteo[motivo] = conteo.get(motivo, 0) + 1
    return conteo
