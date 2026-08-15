"""Cita a ciegas: primero la charla, después las caras.

El diferencial que ninguna de las tres grandes tiene completo: la app elige a
UNA persona que pasa los filtros duros de los dos y con la mejor
compatibilidad, abre el chat… y no muestra las fotos. Se revelan solas cuando
cada uno escribió `UMBRAL` mensajes. Es el ataque directo a la queja de fondo
de la categoría —todo es la foto— con la tesis de Matcher: si los filtros son
de verdad, podés confiar en que la persona del otro lado es lo que pediste
antes de verle la cara.

Tres decisiones de diseño, y por qué:

- **Las fotos no viajan hasta la revelación** (regla 8). Un blur en el cliente
  se saca con "inspeccionar elemento" en la web y con un proxy en el APK. Acá
  el servidor manda `fotos: []` y listo.
- **La revelación es derivada, no un estado.** Se cuenta cuántos mensajes
  mandó cada uno; no hay una columna "revelado" que pueda quedar
  desincronizada entre instancias (ya nos pasó con las sesiones — un estado
  compartido menos es un bug menos).
- **Una sola cita a ciegas sin revelar por vez.** El valor está en la
  escasez: abrir cinco chats ciegos en paralelo es volver al deck, pero sin
  fotos.
"""

from __future__ import annotations

from .filtros import candidatos
from .modelos import DatosInvalidos, Perfil
from .scoring import compatibilidad

# Mensajes que tiene que mandar CADA UNO para que se revelen las fotos. Seis
# es suficiente para que haya conversación de verdad y poco para no frustrar.
UMBRAL = 6


def estado(almacen, match_id: str, mi_id: str) -> dict:
    """Progreso de la revelación, contado desde los mensajes reales."""
    filas = almacen.con.execute(
        "SELECT de_id, COUNT(*) c FROM mensajes WHERE match_id = ? GROUP BY de_id",
        (match_id,),
    ).fetchall()
    conteo = {f["de_id"]: f["c"] for f in filas}
    mios = conteo.get(mi_id, 0)
    suyos = sum(c for de, c in conteo.items() if de != mi_id)
    return {
        "activo": True,
        "umbral": UMBRAL,
        "mios": min(mios, UMBRAL),
        "suyos": min(suyos, UMBRAL),
        "revelado": mios >= UMBRAL and suyos >= UMBRAL,
    }


def silueta(perfil: Perfil) -> dict:
    """El perfil sin caras: queda lo que da pie a conversar (nombre, edad,
    intereses, bio), se van las fotos y los videos."""
    datos = perfil.a_dict()
    datos["fotos"] = []
    datos["videos"] = []
    datos["silueta"] = True
    return datos


def crear(almacen, perfil: Perfil):
    """Elige a la mejor persona nueva que pasa los filtros DE LOS DOS y abre
    el chat ciego. Devuelve el match."""
    # Una por vez: la que está en curso se termina (revelando o borrando el
    # match) antes de pedir otra.
    for m in almacen.matches_de(perfil.id):
        if m.get("ciego") and not m["ciego"]["revelado"]:
            raise DatosInvalidos(
                "ya tenés una cita a ciegas en curso; charlá hasta revelarla "
                "o cerrala antes de pedir otra"
            )

    universo = [p for p in almacen.todos() if p.id != perfil.id]
    vistos = almacen.vistos_por(perfil.id)
    con_match = {m["con"]["id"] for m in almacen.matches_de(perfil.id)}

    # reciproco=True a propósito: acá más que en ningún lado — la gracia es
    # que la persona revelada sea alguien que TAMBIÉN te estaba buscando.
    posibles = [
        o for o in candidatos(perfil, universo, vistos=vistos, reciproco=True)
        if o.id not in con_match
    ]
    if not posibles:
        raise DatosInvalidos(
            "no hay nadie nuevo que pase los filtros de los dos; "
            "aflojá algún filtro o probá más tarde"
        )

    mejor = max(posibles, key=lambda o: (compatibilidad(perfil, o)[0], o.id))
    puntaje, _ = compatibilidad(perfil, mejor)
    return almacen._crear_match(
        perfil.id, mejor.id, automatico=False, compatibilidad=puntaje, ciego=True
    )
