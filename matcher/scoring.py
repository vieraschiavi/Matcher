"""Algoritmo de compatibilidad y orden del deck.

Dos números distintos, que la competencia mezcla y por eso se siente arbitraria:

  * **compatibilidad** (0–100): cuánto se parecen dos personas según lo que
    ellas mismas declararon. Es simétrica y explicable — el frontend muestra
    los motivos ("los dos de Peñarol", "misma postura política").
  * **popularidad** (0–100): cuánto le gusta esa persona al resto. Es el
    "más votados". Se suaviza con un prior bayesiano porque si no, un perfil
    con 1 vista y 1 like queda en 100 y se come el deck entero.

El orden final del deck combina las dos con el peso de la ola geográfica. La
regla que no se rompe: **la ola manda antes que el puntaje**. Alguien de tu
ciudad con 60 de score aparece antes que alguien de otro continente con 95,
salvo que el usuario abra el radio a propósito. Es la queja número uno de las
apps que "te muestran gente de otro país".
"""

from __future__ import annotations

from datetime import date, datetime

from . import geo
from .modelos import Perfil

# Pesos de cada componente de la compatibilidad. Suman 1.0.
PESOS = {
    "politica": 0.22,
    "futbol": 0.16,
    "intereses": 0.24,
    "edad": 0.16,
    "altura": 0.08,
    "cercania": 0.14,
}

# Prior del suavizado bayesiano de popularidad: equivale a arrancar con 20
# vistas y una tasa de like del 12%, que es el promedio observable de un perfil
# medio. Sin esto el ranking lo ganan siempre los perfiles nuevos.
PRIOR_VISTAS = 20.0
PRIOR_TASA = 0.12
# Punto medio de la curva de popularidad: una tasa igual a este valor da 50.
MEDIA_TASA = 0.25

# Cuánto pesa cada cosa en el orden del deck.
PESO_COMPATIBILIDAD = 0.62
PESO_POPULARIDAD = 0.20
PESO_ACTIVIDAD = 0.18

# Empujón de visibilidad de los planes pagos. Es un multiplicador chico y
# acotado a propósito: si el premium arrasa el deck, la experiencia gratis se
# degrada y la app se muere: los que pagan necesitan a los que no.
BOOST_PLAN = {"gratis": 1.00, "plus": 1.08, "gold": 1.15}
TOPE_BOOST_EN_DECK = 0.15


# ---------------------------------------------------------------------------
# Componentes
# ---------------------------------------------------------------------------
def afinidad_politica(a: str, b: str) -> float:
    """Izquierda ↔ derecha es el único cruce que se penaliza fuerte. 'Neutro'
    convive con todo, que es justamente para lo que existe la opción."""
    if a == b:
        return 1.0
    if "neutro" in (a, b):
        return 0.6
    return 0.05  # izquierda vs derecha


def afinidad_futbol(a: Perfil, b: Perfil) -> float:
    """Mismo cuadro es el mejor caso; clásico rival del mismo país no es un
    desastre (mucha gente lo busca a propósito); sin equipo es neutro.

    Ojo con los valores "neutros": no expresar preferencia NO es media
    incompatibilidad. Cuando estos números estaban en 0.5 el score de una
    pareja perfectamente razonable daba 55 y la UI parecía decirle al usuario
    que la persona que tiene enfrente le va la mitad.
    """
    ea, eb = geo.normalizar(a.equipo), geo.normalizar(b.equipo)
    if not ea and not eb:
        return 0.70
    if not ea or not eb:
        return 0.60
    if ea == eb:
        return 1.0
    if a.pais == b.pais:
        return 0.65
    return 0.45


def afinidad_intereses(a: list[str], b: list[str]) -> float:
    """Solapamiento sobre el más chico de los dos, no Jaccard.

    Jaccard castiga a quien carga muchos intereses: 4 en común sobre 5 y 12
    da 0.24, cuando para el usuario eso son "4 cosas en común". El
    solapamiento sobre el mínimo responde a la pregunta que la persona
    realmente se hace.
    """
    sa = {geo.normalizar(i) for i in a if i.strip()}
    sb = {geo.normalizar(i) for i in b if i.strip()}
    if not sa or not sb:
        return 0.60
    return len(sa & sb) / min(len(sa), len(sb))


def afinidad_edad(ea: int, eb: int) -> float:
    """Cae linealmente: 0 años de diferencia = 1.0, 20 años o más = 0.0."""
    return max(0.0, 1.0 - abs(ea - eb) / 20.0)


def afinidad_altura(yo: Perfil, otro: Perfil) -> float:
    """Ya pasó el filtro duro; acá sólo premia estar cómodo en el centro del
    rango pedido. Sin rango declarado no hay nada que premiar ni castigar."""
    p = yo.preferencias
    lo, hi = p.altura_min_cm, p.altura_max_cm
    if lo is None and hi is None:
        return 0.85
    lo = lo if lo is not None else otro.altura_cm
    hi = hi if hi is not None else otro.altura_cm
    if hi <= lo:
        return 1.0
    centro = (lo + hi) / 2
    return max(0.0, 1.0 - abs(otro.altura_cm - centro) / ((hi - lo) / 2 + 1e-9) * 0.5)


def afinidad_cercania(km: float | None) -> float:
    """0 km = 1.0, 100 km = 0.5, 500 km o más ≈ 0.17. Curva suave: para citas,
    la diferencia entre 2 km y 12 km importa mucho más que entre 300 y 400."""
    if km is None:
        return 0.4
    return 1.0 / (1.0 + km / 100.0)


def popularidad(p: Perfil) -> float:
    """0–100. El "más votados" del producto.

    Superfan vale 3 likes: es la señal más cara del sistema (cuesta cupo o
    plata), así que es la menos ruidosa.
    """
    votos = p.likes_recibidos + 3 * p.superfans_recibidos
    vistas = max(p.vistas_recibidas, p.likes_recibidos + p.superfans_recibidos)
    tasa = (votos + PRIOR_VISTAS * PRIOR_TASA) / (vistas + PRIOR_VISTAS)
    # Curva saturante en vez de un factor lineal: con `tasa * 200` cualquiera
    # con tasa ≥ 0.5 quedaba clavado en 100 y el ranking de "más votados" era
    # un empate de veinte personas. Así 0.12 (el promedio) ≈ 32 y hace falta
    # una tasa altísima para acercarse a 100, que es lo que se quiere de un
    # ranking: que el tope cueste.
    return round(100.0 * tasa / (tasa + MEDIA_TASA), 1)


def actividad(p: Perfil, ahora: datetime | None = None) -> float:
    """0–1 por recencia. Un perfil que no entra hace un mes es un fantasma:
    mostrarlo arriba genera likes que nunca se responden."""
    ahora = ahora or datetime.utcnow()
    horas = max(0.0, (ahora - p.ultima_actividad).total_seconds() / 3600.0)
    if horas <= 24:
        return 1.0
    if horas <= 72:
        return 0.85
    if horas <= 24 * 7:
        return 0.65
    if horas <= 24 * 30:
        return 0.35
    return 0.10


# ---------------------------------------------------------------------------
# Compatibilidad
# ---------------------------------------------------------------------------
def compatibilidad(
    yo: Perfil, otro: Perfil, *, hoy: date | None = None
) -> tuple[float, dict[str, float]]:
    """0–100 más el desglose por componente, para poder explicarlo en la UI."""
    hoy = hoy or date.today()
    km = None
    ca, cb = geo.coordenadas(yo.ciudad), geo.coordenadas(otro.ciudad)
    if ca and cb:
        km = geo.distancia_km(ca, cb)

    partes = {
        "politica": afinidad_politica(yo.politica, otro.politica),
        "futbol": afinidad_futbol(yo, otro),
        "intereses": afinidad_intereses(yo.intereses, otro.intereses),
        "edad": afinidad_edad(yo.edad(hoy), otro.edad(hoy)),
        "altura": afinidad_altura(yo, otro),
        "cercania": afinidad_cercania(km),
    }
    total = sum(PESOS[k] * v for k, v in partes.items())
    return round(total * 100, 1), {k: round(v, 3) for k, v in partes.items()}


def motivos(yo: Perfil, otro: Perfil, desglose: dict[str, float]) -> list[str]:
    """Frases cortas para la tarjeta. Sólo las que son verdad — prometer una
    afinidad que no existe es lo que hace que la gente desconfíe del %."""
    salida: list[str] = []
    if desglose.get("futbol", 0) >= 0.99:
        salida.append(f"Los dos de {otro.equipo}")
    elif yo.pais == otro.pais and yo.equipo and otro.equipo and yo.equipo != otro.equipo:
        salida.append(f"Clásico: {yo.equipo} vs {otro.equipo}")
    if yo.politica == otro.politica and yo.politica != "neutro":
        salida.append(f"Misma postura política ({otro.politica})")
    comunes = {geo.normalizar(i) for i in yo.intereses} & {
        geo.normalizar(i) for i in otro.intereses
    }
    if comunes:
        vistos = [i for i in otro.intereses if geo.normalizar(i) in comunes][:3]
        salida.append("En común: " + ", ".join(vistos))
    if desglose.get("cercania", 0) >= 0.9:
        salida.append("Muy cerca tuyo")
    if otro.verificado:
        salida.append("Perfil verificado")
    return salida


# ---------------------------------------------------------------------------
# Orden del deck
# ---------------------------------------------------------------------------
def puntaje_deck(
    yo: Perfil, otro: Perfil, *, hoy: date | None = None, ahora: datetime | None = None
) -> dict:
    comp, desglose = compatibilidad(yo, otro, hoy=hoy)
    pop = popularidad(otro)
    act = actividad(otro, ahora)
    base = (
        PESO_COMPATIBILIDAD * comp
        + PESO_POPULARIDAD * pop
        + PESO_ACTIVIDAD * act * 100
    )
    # El boost premium está acotado: nunca puede mover más de TOPE_BOOST_EN_DECK
    # del puntaje base, aunque el multiplicador diga otra cosa.
    boost = min(BOOST_PLAN.get(otro.plan if otro.es_premium else "gratis", 1.0),
                1.0 + TOPE_BOOST_EN_DECK)
    ola = geo.ola_entre(yo.pais, yo.ciudad, otro.pais, otro.ciudad)
    return {
        "id": otro.id,
        "compatibilidad": comp,
        "popularidad": pop,
        "actividad": round(act, 2),
        "ola": ola,
        "orden_ola": geo.ORDEN_OLA[ola],
        "puntaje": round(base * boost * geo.PESO_OLA[ola], 2),
        "puntaje_sin_ola": round(base * boost, 2),
        "desglose": desglose,
        "motivos": motivos(yo, otro, desglose),
        "distancia_km": (
            geo.distancia_km(geo.coordenadas(yo.ciudad), geo.coordenadas(otro.ciudad))
            if geo.coordenadas(yo.ciudad) and geo.coordenadas(otro.ciudad)
            else None
        ),
    }


def ordenar_deck(
    yo: Perfil,
    candidatos: list[Perfil],
    *,
    hoy: date | None = None,
    ahora: datetime | None = None,
    priorizar_cercania: bool = True,
) -> list[dict]:
    """Devuelve los candidatos puntuados y ordenados.

    Con `priorizar_cercania=True` (el default) la ola es la primera clave de
    orden: nadie de otro país se cuela delante de alguien de tu ciudad. Hay un
    test que existe sólo para impedir esa regresión.

    El desempate final es por id para que el deck sea **determinista**: dos
    llamadas seguidas con los mismos datos devuelven el mismo orden, si no la
    paginación repite y saltea perfiles.
    """
    puntuados = [puntaje_deck(yo, o, hoy=hoy, ahora=ahora) for o in candidatos]
    if priorizar_cercania:
        puntuados.sort(key=lambda d: (d["orden_ola"], -d["puntaje_sin_ola"], d["id"]))
    else:
        puntuados.sort(key=lambda d: (-d["puntaje"], d["id"]))
    return puntuados


def top_votados(perfiles: list[Perfil], limite: int = 20) -> list[dict]:
    """Ranking global de "más votados". Sólo perfiles completos y activos."""
    vivos = [p for p in perfiles if p.activo and p.completo]
    filas = [
        {
            "id": p.id,
            "nombre": p.nombre,
            # Género y edad viajan para que el cliente pueda re-verificar el
            # filtro. El servidor ya filtra; esto es cinturón y tiradores para
            # el despliegue serverless, donde una preferencia recién guardada
            # puede no estar todavía en la instancia que arma el ranking.
            "genero": p.genero,
            "edad": p.edad,
            "popularidad": popularidad(p),
            "likes_recibidos": p.likes_recibidos,
            "superfans_recibidos": p.superfans_recibidos,
            "portada": p.portada,
            "verificado": p.verificado,
            "sintetico": p.sintetico,
        }
        for p in vivos
    ]
    filas.sort(key=lambda f: (-f["popularidad"], -f["likes_recibidos"], f["id"]))
    return filas[:limite]
