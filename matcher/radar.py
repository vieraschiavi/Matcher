"""Radar: quién hay cerca tuyo, ahora.

Devuelve a la gente del deck que entra en un radio, con **distancia real** y
**posición aproximada a la celda** (~500 m). Con eso el frontend dibuja un
mapa/radar que sirve —"hay 12 personas a menos de 3 km, tres a menos de 500 m"—
sin que nadie pueda ubicar la casa de nadie.

La regla dura, y hay un test que la fija: **de acá no sale una coordenada
exacta**. Ni siquiera la del propio usuario hacia otros. Todo lo que se
devuelve pasó por `geo.aproximar`.

El radar respeta los mismos filtros duros que el deck. Un radar que muestra a
gente que el usuario filtró es peor que no tener radar: le dice "está a 400
metros" de alguien que pidió no ver.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from . import filtros, geo, scoring

# Anillos del radar, en km. La UI dibuja un círculo por cada uno.
ANILLOS_KM = (0.5, 2, 5, 15, 50)
RADIO_DEFECTO_KM = 15
RADIO_MAXIMO_KM = 200

# Más allá de esto no se muestra a nadie en el radar aunque esté cerca: un
# punto de alguien que no entra hace un mes es una promesa falsa.
VENTANA_ACTIVIDAD = timedelta(days=14)


def _posicion_de(almacen, perfil) -> tuple[float, float] | None:
    """Última posición conocida, o el centro de la ciudad declarada.

    El fallback a la ciudad importa: si el radar dependiera de que la persona
    haya abierto la app con GPS, estaría vacío el 90% del tiempo.
    """
    guardada = almacen.ubicacion_de(perfil.id)
    if guardada:
        return (guardada["lat"], guardada["lon"])
    return geo.coordenadas(perfil.ciudad)


def alrededor(
    almacen,
    perfil,
    *,
    radio_km: float = RADIO_DEFECTO_KM,
    limite: int = 60,
    hoy: date | None = None,
    ahora: datetime | None = None,
) -> dict:
    ahora = ahora or datetime.utcnow()
    radio_km = min(max(float(radio_km), 0.1), RADIO_MAXIMO_KM)

    yo_pos = _posicion_de(almacen, perfil)
    if not yo_pos:
        return {
            "centro": None,
            "radio_km": radio_km,
            "anillos_km": list(ANILLOS_KM),
            "personas": [],
            "precision_m": geo.PRECISION_MAPA_M,
            "aviso": "Todavía no sabemos dónde estás. Activá la ubicación o elegí tu ciudad.",
        }

    universo = [p for p in almacen.todos() if p.id != perfil.id]
    vistos = almacen.vistos_por(perfil.id)
    candidatos = filtros.candidatos(perfil, universo, vistos=vistos, hoy=hoy)

    cruces = {c["otro_id"]: c["veces"] for c in almacen.cruces_de(perfil.id, 500)}
    personas = []
    for otro in candidatos:
        if ahora - otro.ultima_actividad > VENTANA_ACTIVIDAD:
            continue
        pos = _posicion_de(almacen, otro)
        if not pos:
            continue
        km = geo.distancia_km(yo_pos, pos)
        if km > radio_km:
            continue
        comp, desglose = scoring.compatibilidad(perfil, otro, hoy=hoy)
        aprox = geo.aproximar(*pos)
        personas.append(
            otro.a_dict()
            | {
                "distancia_km": km,
                "rumbo": geo.rumbo(yo_pos, aprox),
                "lat_aprox": aprox[0],
                "lon_aprox": aprox[1],
                "compatibilidad": comp,
                "motivos": scoring.motivos(perfil, otro, desglose),
                "cruces": cruces.get(otro.id, 0),
                "activo_hace_horas": round(
                    (ahora - otro.ultima_actividad).total_seconds() / 3600, 1
                ),
            }
        )

    # Los más cercanos primero: en un radar la distancia ES el orden.
    personas.sort(key=lambda p: (p["distancia_km"], p["id"]))
    personas = personas[:limite]

    return {
        "centro": {"lat": geo.aproximar(*yo_pos)[0], "lon": geo.aproximar(*yo_pos)[1]},
        "radio_km": radio_km,
        "anillos_km": [a for a in ANILLOS_KM if a <= radio_km] or [radio_km],
        "precision_m": geo.PRECISION_MAPA_M,
        "personas": personas,
        "por_anillo": _contar_por_anillo(personas, radio_km),
        "aviso": (
            f"Las posiciones están redondeadas a {geo.PRECISION_MAPA_M} m. "
            "Nadie ve tu ubicación exacta, y vos no ves la de nadie."
        ),
    }


def _contar_por_anillo(personas: list[dict], radio_km: float) -> list[dict]:
    """Cuánta gente hay en cada anillo. Es el número que le da sentido al
    radar cuando hay demasiados puntos para contarlos a ojo."""
    bordes = [a for a in ANILLOS_KM if a <= radio_km] or [radio_km]
    salida, anterior = [], 0.0
    for borde in bordes:
        n = sum(1 for p in personas if anterior < p["distancia_km"] <= borde)
        salida.append({"hasta_km": borde, "desde_km": anterior, "personas": n})
        anterior = borde
    lejos = sum(1 for p in personas if p["distancia_km"] > anterior)
    if lejos:
        salida.append({"hasta_km": radio_km, "desde_km": anterior, "personas": lejos})
    return salida
