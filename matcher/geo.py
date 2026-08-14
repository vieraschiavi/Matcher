"""Geografía: países, ciudades, distancia y equipos de fútbol por país.

Por qué vive acá y no cableado en el scoring: el filtro de "equipo de fútbol"
que pidió el producto es **relativo al país de localización del usuario**. Un
uruguayo tiene que ver Peñarol/Nacional; un mexicano, Chivas/América. Si el
catálogo se cablea a un país, el filtro deja de servir para el resto del
mundo — el mismo error que ya se pagó caro en MV Cliente IA con Uruguay.

El catálogo es de clubes de primera división, información pública y estable.
No pretende ser exhaustivo: cubre los equipos con hinchada masiva de cada país
más una opción "otro" para que nadie quede afuera.
"""

from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass

# Ola geográfica: mismo criterio que MV Cliente IA. Primero tu ciudad, después
# tu país, después tu región, después el mundo. Los pesos multiplican al score
# de compatibilidad, así que un candidato perfecto a 8.000 km nunca le gana a
# uno muy bueno a 5 km salvo que el usuario abra el radio a propósito.
PESO_OLA: dict[str, float] = {
    "ciudad": 1.00,
    "pais": 0.80,
    "region": 0.55,
    "mundo": 0.30,
}

ORDEN_OLA: dict[str, int] = {"ciudad": 0, "pais": 1, "region": 2, "mundo": 3}


@dataclass(frozen=True)
class Pais:
    codigo: str
    nombre: str
    region: str
    equipos: tuple[str, ...]


# --------------------------------------------------------------------------
# Catálogo de países. `equipos` son clubes de fútbol de primera división del
# país; el frontend le agrega "Otro" y "Ninguno / no me interesa" al final.
# --------------------------------------------------------------------------
CATALOGO: dict[str, Pais] = {
    p.codigo: p
    for p in [
        Pais("UY", "Uruguay", "cono_sur", (
            "Peñarol", "Nacional", "Defensor Sporting", "Danubio", "Liverpool",
            "Montevideo City Torque", "Racing", "Cerro", "Wanderers", "Progreso",
        )),
        Pais("AR", "Argentina", "cono_sur", (
            "Boca Juniors", "River Plate", "Racing Club", "Independiente",
            "San Lorenzo", "Vélez Sarsfield", "Estudiantes", "Newell's Old Boys",
            "Rosario Central", "Talleres", "Lanús", "Huracán",
        )),
        Pais("CL", "Chile", "cono_sur", (
            "Colo-Colo", "Universidad de Chile", "Universidad Católica",
            "Cobreloa", "Everton", "Unión Española", "Palestino",
        )),
        Pais("PY", "Paraguay", "cono_sur", (
            "Olimpia", "Cerro Porteño", "Libertad", "Guaraní", "Nacional",
        )),
        Pais("BR", "Brasil", "brasil", (
            "Flamengo", "Corinthians", "Palmeiras", "São Paulo", "Santos",
            "Grêmio", "Internacional", "Cruzeiro", "Atlético Mineiro",
            "Vasco da Gama", "Botafogo", "Fluminense", "Bahia", "Fortaleza",
        )),
        Pais("PE", "Perú", "andina", (
            "Alianza Lima", "Universitario", "Sporting Cristal", "Melgar",
            "Cienciano",
        )),
        Pais("BO", "Bolivia", "andina", (
            "Bolívar", "The Strongest", "Oriente Petrolero", "Blooming",
            "Always Ready",
        )),
        Pais("EC", "Ecuador", "andina", (
            "Barcelona SC", "Emelec", "LDU Quito", "Independiente del Valle",
            "Aucas",
        )),
        Pais("CO", "Colombia", "andina", (
            "Atlético Nacional", "Millonarios", "América de Cali",
            "Deportivo Cali", "Junior", "Independiente Santa Fe",
            "Deportivo Independiente Medellín",
        )),
        Pais("VE", "Venezuela", "andina", (
            "Caracas FC", "Deportivo Táchira", "Deportivo La Guaira",
            "Zamora", "Carabobo",
        )),
        Pais("MX", "México", "norteamerica", (
            "Club América", "Chivas de Guadalajara", "Cruz Azul", "Pumas UNAM",
            "Tigres UANL", "Monterrey", "Santos Laguna", "Toluca", "León",
            "Pachuca",
        )),
        Pais("US", "Estados Unidos", "norteamerica", (
            "Inter Miami", "LA Galaxy", "LAFC", "Seattle Sounders",
            "Atlanta United", "New York City FC", "New York Red Bulls",
        )),
        Pais("CA", "Canadá", "norteamerica", (
            "Toronto FC", "CF Montréal", "Vancouver Whitecaps",
        )),
        Pais("ES", "España", "europa_sur", (
            "Real Madrid", "FC Barcelona", "Atlético de Madrid", "Sevilla",
            "Real Betis", "Valencia", "Athletic Club", "Real Sociedad",
            "Villarreal", "Celta de Vigo",
        )),
        Pais("PT", "Portugal", "europa_sur", (
            "Benfica", "FC Porto", "Sporting CP", "Braga", "Vitória de Guimarães",
        )),
        Pais("IT", "Italia", "europa_sur", (
            "Juventus", "Inter", "Milan", "Napoli", "Roma", "Lazio",
            "Fiorentina", "Atalanta",
        )),
        Pais("FR", "Francia", "europa_oeste", (
            "Paris Saint-Germain", "Olympique de Marsella", "Olympique de Lyon",
            "Mónaco", "Lille", "Saint-Étienne",
        )),
        Pais("GB", "Reino Unido", "europa_oeste", (
            "Manchester United", "Manchester City", "Liverpool", "Arsenal",
            "Chelsea", "Tottenham", "Everton", "Newcastle United",
            "Celtic", "Rangers",
        )),
        Pais("DE", "Alemania", "europa_oeste", (
            "Bayern Múnich", "Borussia Dortmund", "RB Leipzig", "Schalke 04",
            "Bayer Leverkusen", "Hamburgo",
        )),
        Pais("NL", "Países Bajos", "europa_oeste", (
            "Ajax", "PSV", "Feyenoord", "AZ Alkmaar",
        )),
    ]
}

# Ciudades con coordenadas aproximadas del centro. Sirven para dos cosas:
# calcular distancia sin pedirle GPS al usuario, y ofrecer un selector cerrado
# en el alta (escribir la ciudad a mano ensucia el filtro de localización).
CIUDADES: dict[str, tuple[str, float, float]] = {
    "UY-MVD": ("Montevideo", -34.9011, -56.1645),
    "UY-MAL": ("Maldonado", -34.9089, -54.9581),
    "UY-SAL": ("Salto", -31.3833, -57.9667),
    "UY-CAN": ("Canelones", -34.5228, -56.2772),
    "AR-BUE": ("Buenos Aires", -34.6037, -58.3816),
    "AR-COR": ("Córdoba", -31.4201, -64.1888),
    "AR-ROS": ("Rosario", -32.9442, -60.6505),
    "AR-MDZ": ("Mendoza", -32.8895, -68.8458),
    "CL-SCL": ("Santiago", -33.4489, -70.6693),
    "CL-VAP": ("Valparaíso", -33.0472, -71.6127),
    "PY-ASU": ("Asunción", -25.2637, -57.5759),
    "BR-SAO": ("São Paulo", -23.5505, -46.6333),
    "BR-RIO": ("Río de Janeiro", -22.9068, -43.1729),
    "BR-POA": ("Porto Alegre", -30.0346, -51.2177),
    "BR-BSB": ("Brasilia", -15.7939, -47.8828),
    "PE-LIM": ("Lima", -12.0464, -77.0428),
    "BO-LPB": ("La Paz", -16.4897, -68.1193),
    "EC-UIO": ("Quito", -0.1807, -78.4678),
    "EC-GYE": ("Guayaquil", -2.1894, -79.8891),
    "CO-BOG": ("Bogotá", 4.7110, -74.0721),
    "CO-MDE": ("Medellín", 6.2442, -75.5812),
    "VE-CCS": ("Caracas", 10.4806, -66.9036),
    "MX-MEX": ("Ciudad de México", 19.4326, -99.1332),
    "MX-GDL": ("Guadalajara", 20.6597, -103.3496),
    "MX-MTY": ("Monterrey", 25.6866, -100.3161),
    "US-NYC": ("Nueva York", 40.7128, -74.0060),
    "US-MIA": ("Miami", 25.7617, -80.1918),
    "US-LAX": ("Los Ángeles", 34.0522, -118.2437),
    "CA-YTO": ("Toronto", 43.6532, -79.3832),
    "ES-MAD": ("Madrid", 40.4168, -3.7038),
    "ES-BCN": ("Barcelona", 41.3874, 2.1686),
    "PT-LIS": ("Lisboa", 38.7223, -9.1393),
    "IT-ROM": ("Roma", 41.9028, 12.4964),
    "IT-MIL": ("Milán", 45.4642, 9.1900),
    "FR-PAR": ("París", 48.8566, 2.3522),
    "GB-LON": ("Londres", 51.5074, -0.1278),
    "DE-BER": ("Berlín", 52.5200, 13.4050),
    "NL-AMS": ("Ámsterdam", 52.3676, 4.9041),
}


def ciudades_de(codigo_pais: str) -> list[dict]:
    """Ciudades del catálogo que pertenecen a un país."""
    salida = []
    for clave, (nombre, lat, lon) in CIUDADES.items():
        if clave.startswith(f"{codigo_pais}-"):
            salida.append({"id": clave, "nombre": nombre, "lat": lat, "lon": lon})
    return sorted(salida, key=lambda c: c["nombre"])


def coordenadas(id_ciudad: str) -> tuple[float, float] | None:
    dato = CIUDADES.get(id_ciudad)
    return (dato[1], dato[2]) if dato else None


def equipos_de(codigo_pais: str) -> list[str]:
    """Equipos del país. Vacío si el país no está en el catálogo."""
    pais = CATALOGO.get(codigo_pais)
    return list(pais.equipos) if pais else []


def region_de(codigo_pais: str) -> str:
    pais = CATALOGO.get(codigo_pais)
    return pais.region if pais else "desconocida"


def distancia_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Haversine. Redondeada a 1 decimal: mostrar 8.5 km es información,
    mostrar 8.5231 km es ruido y además filtra de más al comparar."""
    radio = 6371.0
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return round(2 * radio * math.asin(math.sqrt(h)), 1)


def ola_entre(pais_a: str, ciudad_a: str, pais_b: str, ciudad_b: str) -> str:
    """En qué ola cae B respecto de A. El orden es ciudad → país → región → mundo."""
    if pais_a == pais_b and ciudad_a and ciudad_a == ciudad_b:
        return "ciudad"
    if pais_a == pais_b:
        return "pais"
    if region_de(pais_a) == region_de(pais_b) != "desconocida":
        return "region"
    return "mundo"


def normalizar(texto: str) -> str:
    """Sin acentos y en minúscula. Se usa para comparar equipos escritos a mano
    ('peñarol' == 'Peñarol' == 'penarol') sin romper el filtro."""
    sin_tildes = unicodedata.normalize("NFKD", texto or "")
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return sin_tildes.strip().lower()


def paises_ordenados() -> list[dict]:
    return sorted(
        (
            {
                "codigo": p.codigo,
                "nombre": p.nombre,
                "region": p.region,
                "equipos": list(p.equipos),
                "ciudades": ciudades_de(p.codigo),
            }
            for p in CATALOGO.values()
        ),
        key=lambda p: p["nombre"],
    )
