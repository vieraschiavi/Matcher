"""Vitrinas: listados de gente que no son el deck.

Dos secciones que existen para dar entradas distintas a la misma app, porque
swipear no es lo único que la gente quiere hacer:

- **Disponible hoy**: quién dijo que sale hoy. Es la sección con más intención
  de todas —la persona ya declaró que quiere salir— y por eso viene ordenada
  por cercanía antes que por puntaje: alguien disponible a 40 cuadras sirve;
  alguien disponible en otro continente, no.
- **Más likeados por zona**: la tabla de los 200 más likeados de tu barrio, de
  tu ciudad o del mundo. El ranking global ya existía y es lindo de mirar, pero
  no es accionable: los 200 del mundo son inalcanzables. Acotado al barrio, es
  una lista de gente con la que te podés cruzar.

Sobre "barrio": **no hay un campo barrio y no se inventa uno.** Pedirle a la
gente que escriba su barrio es un campo más que nadie llena, y con texto libre
"Pocitos", "pocitos" y "POCITOS" son tres barrios distintos. El barrio acá es
un radio de `RADIO_BARRIO_KM` alrededor de tu última posición conocida, que es
dato que la app ya tiene por el radar. Es menos preciso que un nombre y es
mucho más honesto: la promesa "está cerca tuyo" se puede sostener.

Las dos vitrinas aplican los filtros duros (regla 1). Una vitrina que no los
respeta es exactamente igual de grave que un deck que no los respeta — y peor
todavía, porque una lista de "los más likeados" invita a mirarla entera.
"""

from __future__ import annotations

from datetime import date, datetime

from . import filtros, geo, scoring
from .modelos import Perfil

# El "barrio". Coincide con el segundo anillo del radar (`radar.ANILLOS_KM`) a
# propósito: si el radar te dibuja un círculo de 2 km y le llama "cerca", la
# vitrina no puede llamarle barrio a otra cosa.
RADIO_BARRIO_KM = 2.0

# Tope de las listas. 200 es lo que pidió el producto para "más likeados"; es
# también el techo duro del parámetro, para que nadie se traiga el padrón
# entero pidiendo limite=99999.
TOPE_LISTA = 200

ALCANCES = ("barrio", "ciudad", "mundo")


def _posicion_de(almacen, perfil: Perfil) -> tuple[float, float] | None:
    """Última posición conocida, o el centro de la ciudad declarada.

    Mismo criterio que `radar._posicion_de`, y por la misma razón: si dependiera
    de que la persona haya abierto la app con el GPS prendido, la vitrina del
    barrio estaría vacía casi siempre.
    """
    guardada = almacen.ubicacion_de(perfil.id)
    if guardada:
        return (guardada["lat"], guardada["lon"])
    return geo.coordenadas(perfil.ciudad)


def _visibles(almacen, perfil: Perfil) -> list[Perfil]:
    """El universo base de cualquier vitrina: gente activa, con foto, que pasa
    tus filtros duros. Sin `reciproco`: una vitrina muestra a quien vos podés
    ver, no exige que la otra persona también te quiera ver."""
    return [
        o
        for o in almacen.todos()
        if o.id != perfil.id
        and o.activo
        and o.completo
        and filtros.pasa_filtros(perfil, o, reciproco=False)[0]
    ]


def disponibles_hoy(
    almacen,
    perfil: Perfil,
    *,
    limite: int = 60,
    hoy: date | None = None,
    ahora: datetime | None = None,
) -> dict:
    """Quién marcó "disponible hoy" y todavía no venció.

    `Perfil.disponible_hoy` decide por reloj, no por la lista de intenciones
    guardada: un perfil que dice "disponible hoy" desde hace cinco días le está
    mintiendo a todo el mundo, y esta vitrina sería el lugar donde más se
    notaría.

    Se excluye a quien ya respondiste: es una lista para dar like, no una
    vitrina de contemplación. Repetir a alguien que ya descartaste es la forma
    más rápida de que la sección se sienta rota.
    """
    vistos = almacen.vistos_por(perfil.id)
    candidatos = [
        o for o in _visibles(almacen, perfil) if o.disponible_hoy and o.id not in vistos
    ]

    # Cercanía primero (regla 3): en esta sección importa más que en ninguna
    # otra, porque el valor de la sección es "podés verlo hoy".
    ordenados = scoring.ordenar_deck(
        perfil, candidatos, hoy=hoy, ahora=ahora, priorizar_cercania=True
    )
    por_id = {o.id: o for o in candidatos}

    yo_pos = _posicion_de(almacen, perfil)
    salida = []
    for fila in ordenados[: max(1, min(limite, TOPE_LISTA))]:
        otro = por_id.get(fila["id"])
        if not otro:
            continue
        dato = otro.a_dict() | {
            "compatibilidad": fila["compatibilidad"],
            "motivos": fila.get("motivos", []),
        }
        otro_pos = _posicion_de(almacen, otro)
        if yo_pos and otro_pos:
            dato["distancia_km"] = round(geo.distancia_km(yo_pos, otro_pos), 1)
        salida.append(dato)

    return {"total": len(candidatos), "personas": salida}


def _en_alcance(
    almacen, perfil: Perfil, candidatos: list[Perfil], alcance: str
) -> list[Perfil]:
    if alcance == "mundo":
        return candidatos
    if alcance == "ciudad":
        return [o for o in candidatos if o.ciudad == perfil.ciudad]

    # Barrio: radio alrededor de la posición propia. Sin posición no se puede
    # responder, y devolver la ciudad entera diciendo que es el barrio sería
    # mentir — se devuelve vacío y la UI lo explica.
    yo_pos = _posicion_de(almacen, perfil)
    if not yo_pos:
        return []
    cerca = []
    for o in candidatos:
        pos = _posicion_de(almacen, o)
        if pos and geo.distancia_km(yo_pos, pos) <= RADIO_BARRIO_KM:
            cerca.append(o)
    return cerca


def mas_likeados(
    almacen,
    perfil: Perfil,
    *,
    alcance: str = "ciudad",
    limite: int = TOPE_LISTA,
) -> dict:
    """Los más likeados del barrio, de la ciudad o del mundo.

    Reusa `scoring.top_votados` en vez de contar likes crudos, por la misma
    razón que el ranking global: el conteo crudo lo gana siempre el perfil más
    viejo, y la popularidad suavizada mide tasa, no antigüedad. Lo único que
    cambia acá es el universo sobre el que se calcula.
    """
    if alcance not in ALCANCES:
        alcance = "ciudad"
    limite = max(1, min(int(limite), TOPE_LISTA))

    candidatos = _en_alcance(almacen, perfil, _visibles(almacen, perfil), alcance)
    top = scoring.top_votados(candidatos, limite)

    # El puesto viaja calculado del servidor: si lo calcula el cliente con el
    # índice del array, cualquier filtro de cliente que saque a alguien
    # renumera la tabla entera y el #7 pasa a ser #6 sin haber subido.
    for puesto, fila in enumerate(top, start=1):
        fila["puesto"] = puesto

    return {
        "alcance": alcance,
        "radio_km": RADIO_BARRIO_KM if alcance == "barrio" else None,
        "ciudad": geo.nombre_ciudad(perfil.ciudad) if alcance == "ciudad" else None,
        "total": len(candidatos),
        "top": top,
    }
