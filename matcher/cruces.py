"""Cruces: cuántas veces te cruzaste con alguien en la vida real.

Es la mecánica que hizo conocida a Happn, y la parte buena es real: da un tema
de conversación que no es "hola". Acá se implementa así:

  1. La app manda pings de ubicación (`registrar_ping`).
  2. Cada ping se guarda como **celda** de ~250 m, nunca como coordenada.
  3. Dos personas se cruzaron si estuvieron en la misma celda dentro de una
     ventana de tiempo. Se cuenta una vez por ventana, no una por ping —
     si no, quedarse media hora en un café da 200 cruces con el de al lado.

Lo que NUNCA se guarda ni se devuelve es el recorrido de nadie: los pings
viejos se borran, y del cruce sólo sobrevive el conteo y la celda aproximada.
Un historial de ubicaciones es lo más peligroso que puede tener una app de
citas, y la única forma de no filtrarlo es no tenerlo.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from . import filtros, geo

# Dos pings en la misma celda dentro de esta ventana = un cruce.
VENTANA_CRUCE = timedelta(minutes=30)

# Los pings se borran pasado esto. Alcanza para detectar cruces y no alcanza
# para reconstruir por dónde anduvo alguien.
VIDA_PING = timedelta(hours=6)

# Tope de cruces contados con la misma persona por día: sin esto, dos que
# trabajan en la misma cuadra llegan a 40 cruces en una semana y el número
# deja de significar algo.
MAX_CRUCES_POR_DIA = 4


def registrar_ping(almacen, perfil, lat: float, lon: float, momento: datetime | None = None) -> dict:
    """Guarda dónde está el usuario y devuelve los cruces nuevos detectados."""
    momento = momento or datetime.utcnow()
    clave = geo.clave_celda(lat, lon, geo.PRECISION_CRUCE_M)

    almacen.limpiar_pings(momento - VIDA_PING)
    nuevos = almacen.detectar_cruces(perfil.id, clave, momento, VENTANA_CRUCE, MAX_CRUCES_POR_DIA)
    almacen.guardar_ping(perfil.id, clave, momento)
    # La última posición del propio usuario sí se guarda con precisión de mapa:
    # es la que se usa para centrar SU radar, y es suya.
    almacen.guardar_ubicacion(perfil.id, *geo.aproximar(lat, lon), momento)
    return {"cruces_nuevos": nuevos, "celda": clave}


def de(almacen, perfil, limite: int = 50, hoy: date | None = None) -> list[dict]:
    """Con quién te cruzaste, ordenado por cantidad de cruces.

    Se excluye a quien ya descartaste: cruzarte diez veces con alguien a quien
    le dijiste que no es exactamente lo que no querés que te recuerden. Y se
    respetan los filtros duros, igual que en el deck y en el radar.
    """
    vistos = almacen.vistos_por(perfil.id)
    filas = almacen.cruces_de(perfil.id, limite * 2)
    salida = []
    for fila in filas:
        if fila["otro_id"] in vistos:
            continue
        otro = almacen.perfil(fila["otro_id"])
        if not otro:
            continue
        # Los filtros DUROS también valen acá. Esta lista se saltaba
        # `pasa_filtros` y sólo miraba activo/completo: alguien que pedía ver
        # sólo mujeres se encontraba hombres en "te cruzaste con", que es
        # exactamente la queja que el producto ataca. Cruzarse es un hecho
        # físico, pero no es motivo para mostrar a quien pediste no ver.
        #
        # reciproco=False a propósito: acá no se exige que YO pase los filtros
        # del otro. Eso es una ayuda para que el deck no se llene de gente que
        # nunca me va a dar like; esconder a alguien con quien me crucé porque
        # yo no entro en SU rango sería decidir por él.
        ok, _ = filtros.pasa_filtros(perfil, otro, hoy=hoy, reciproco=False)
        if not ok:
            continue
        from . import scoring

        comp, desglose = scoring.compatibilidad(perfil, otro)
        salida.append(
            otro.a_dict()
            | {
                "veces": fila["veces"],
                "primera": fila["primera"],
                "ultima": fila["ultima"],
                "compatibilidad": comp,
                "motivos": scoring.motivos(perfil, otro, desglose),
                # Dónde se cruzaron, redondeado a la celda de mapa. Nunca la
                # celda de 250 m con la que se detectó: esa es más precisa de
                # lo que hace falta mostrar.
                "cerca_de": fila["cerca_de"],
                # La misma celda ya como coordenada, para poder pintarla en el
                # mapa sin que el frontend tenga que saber cómo se arma la
                # clave.
                "punto": (
                    dict(zip(("lat", "lon"), punto, strict=True))
                    if (punto := geo.punto_de_clave(fila["cerca_de"] or ""))
                    else None
                ),
            }
        )
        if len(salida) >= limite:
            break
    return salida


def resumen(almacen, perfil) -> dict:
    total, personas = almacen.total_cruces(perfil.id)
    return {"cruces_totales": total, "personas": personas}
