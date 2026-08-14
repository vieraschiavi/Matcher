"""Radar: quién hay cerca, con posición SIEMPRE redondeada."""

from datetime import datetime, timedelta

from matcher import cruces, geo, radar
from matcher.modelos import Preferencias


def alta(almacen, hacer_perfil, **kw):
    p = hacer_perfil(**kw)
    almacen.crear_perfil(p, "clave-larga-1")
    return p


def test_nadie_ve_una_coordenada_exacta(almacen, hacer_perfil):
    """La regla dura del módulo: todo lo que sale de acá pasó por
    `geo.aproximar`. Si algún día se filtra una coordenada sin redondear, es
    un incidente de seguridad, no un detalle visual."""
    yo = alta(almacen, hacer_perfil, ciudad="UY-MVD", preferencias=Preferencias(generos=[]))
    otro = alta(almacen, hacer_perfil, ciudad="UY-MVD")
    exacta = (-34.9012345, -56.1645678)
    almacen.guardar_ubicacion(otro.id, *exacta, datetime.utcnow())
    almacen.guardar_ubicacion(yo.id, -34.9011, -56.1645, datetime.utcnow())

    r = radar.alrededor(almacen, yo)
    fila = next(p for p in r["personas"] if p["id"] == otro.id)
    assert (fila["lat_aprox"], fila["lon_aprox"]) != exacta
    assert (fila["lat_aprox"], fila["lon_aprox"]) == geo.aproximar(*exacta)


def test_respeta_el_radio_pedido(almacen, hacer_perfil):
    yo = alta(almacen, hacer_perfil, ciudad="UY-MVD", preferencias=Preferencias(generos=[]))
    cerca = alta(almacen, hacer_perfil, ciudad="UY-MVD", nombre="Cerca")
    lejos = alta(almacen, hacer_perfil, ciudad="UY-SAL", nombre="Lejos")  # Salto, ~450 km
    ahora = datetime.utcnow()
    almacen.guardar_ubicacion(yo.id, -34.9011, -56.1645, ahora)
    almacen.guardar_ubicacion(cerca.id, -34.905, -56.16, ahora)
    almacen.guardar_ubicacion(*geo.coordenadas("UY-SAL"), ahora) if False else None
    lat, lon = geo.coordenadas("UY-SAL")
    almacen.guardar_ubicacion(lejos.id, lat, lon, ahora)

    r = radar.alrededor(almacen, yo, radio_km=10)
    ids = [p["id"] for p in r["personas"]]
    assert cerca.id in ids
    assert lejos.id not in ids


def test_respeta_los_mismos_filtros_duros_que_el_deck(almacen, hacer_perfil):
    """Mostrar en el radar a alguien que el usuario filtró es peor que no
    tener radar: le dice "está a 400 metros" de quien pidió no ver."""
    yo = alta(
        almacen,
        hacer_perfil,
        ciudad="UY-MVD",
        genero="hombre",
        preferencias=Preferencias(generos=["mujer"]),
    )
    hombre = alta(almacen, hacer_perfil, ciudad="UY-MVD", genero="hombre")
    ahora = datetime.utcnow()
    almacen.guardar_ubicacion(yo.id, -34.9011, -56.1645, ahora)
    almacen.guardar_ubicacion(hombre.id, -34.9011, -56.1645, ahora)

    r = radar.alrededor(almacen, yo, radio_km=50)
    assert hombre.id not in [p["id"] for p in r["personas"]]


def test_sin_ubicacion_cae_al_centro_de_la_ciudad(almacen, hacer_perfil):
    yo = alta(almacen, hacer_perfil, ciudad="UY-MVD", preferencias=Preferencias(generos=[]))
    otro = alta(almacen, hacer_perfil, ciudad="UY-MVD")
    almacen.guardar_ubicacion(otro.id, *geo.coordenadas("UY-MVD"), datetime.utcnow())

    r = radar.alrededor(almacen, yo, radio_km=5)
    assert r["centro"] is not None
    assert any(p["id"] == otro.id for p in r["personas"])


def test_fantasmas_no_aparecen_en_el_radar(almacen, hacer_perfil):
    yo = alta(almacen, hacer_perfil, ciudad="UY-MVD", preferencias=Preferencias(generos=[]))
    fantasma = alta(
        almacen,
        hacer_perfil,
        ciudad="UY-MVD",
        ultima_actividad=datetime.utcnow() - timedelta(days=60),
    )
    ahora = datetime.utcnow()
    almacen.guardar_ubicacion(yo.id, -34.9011, -56.1645, ahora)
    almacen.guardar_ubicacion(fantasma.id, -34.9011, -56.1645, ahora)

    r = radar.alrededor(almacen, yo, radio_km=10, ahora=ahora)
    assert fantasma.id not in [p["id"] for p in r["personas"]]


def test_ordena_por_distancia(almacen, hacer_perfil):
    yo = alta(almacen, hacer_perfil, ciudad="UY-MVD", preferencias=Preferencias(generos=[]))
    ahora = datetime.utcnow()
    almacen.guardar_ubicacion(yo.id, -34.9011, -56.1645, ahora)
    lejos = alta(almacen, hacer_perfil, ciudad="UY-MVD", nombre="B")
    cerca = alta(almacen, hacer_perfil, ciudad="UY-MVD", nombre="A")
    almacen.guardar_ubicacion(lejos.id, -34.95, -56.20, ahora)
    almacen.guardar_ubicacion(cerca.id, -34.9012, -56.1646, ahora)

    r = radar.alrededor(almacen, yo, radio_km=50)
    assert r["personas"][0]["id"] == cerca.id


def test_geo_celda_es_determinista_y_estable():
    a = geo.aproximar(-34.9011, -56.1645)
    b = geo.aproximar(-34.90111, -56.16449)  # 1 metro de diferencia
    assert a == b  # misma celda


def test_geo_aproximar_nunca_devuelve_lo_mismo_que_metio(monkeypatch=None):
    exacta = (-34.123456, -58.654321)
    aprox = geo.aproximar(*exacta)
    assert aprox != exacta
    # Y el error es acotado: no puede alejarse más de una celda del original.
    assert geo.distancia_km(exacta, aprox) < 1.0


# ---------------------------------------------------------------------------
# Cruces
# ---------------------------------------------------------------------------
def test_dos_pings_en_la_misma_celda_generan_un_cruce(almacen, hacer_perfil):
    a = alta(almacen, hacer_perfil)
    b = alta(almacen, hacer_perfil)
    ahora = datetime.utcnow()
    cruces.registrar_ping(almacen, a, -34.9011, -56.1645, ahora)
    r = cruces.registrar_ping(almacen, b, -34.9011, -56.1645, ahora + timedelta(minutes=5))
    assert len(r["cruces_nuevos"]) == 1
    assert r["cruces_nuevos"][0]["otro_id"] == a.id

    total, personas = almacen.total_cruces(a.id)
    assert total == 1 and personas == 1


def test_lejos_no_cuenta_como_cruce(almacen, hacer_perfil):
    a = alta(almacen, hacer_perfil)
    b = alta(almacen, hacer_perfil)
    ahora = datetime.utcnow()
    cruces.registrar_ping(almacen, a, -34.9011, -56.1645, ahora)
    cruces.registrar_ping(almacen, b, -34.95, -56.20, ahora)  # varios km de distancia
    total, _ = almacen.total_cruces(a.id)
    assert total == 0


def test_fuera_de_la_ventana_no_cuenta(almacen, hacer_perfil):
    a = alta(almacen, hacer_perfil)
    b = alta(almacen, hacer_perfil)
    ahora = datetime.utcnow()
    cruces.registrar_ping(almacen, a, -34.9011, -56.1645, ahora)
    cruces.registrar_ping(almacen, b, -34.9011, -56.1645, ahora + timedelta(hours=2))
    total, _ = almacen.total_cruces(a.id)
    assert total == 0


def test_quedarse_en_el_mismo_lugar_no_infla_el_contador(almacen, hacer_perfil):
    """Sin el tope por ventana, quedarse media hora en el mismo café con otra
    persona daría un cruce por cada ping en vez de uno."""
    a = alta(almacen, hacer_perfil)
    b = alta(almacen, hacer_perfil)
    ahora = datetime.utcnow()
    cruces.registrar_ping(almacen, a, -34.9011, -56.1645, ahora)
    for m in range(1, 20, 2):
        cruces.registrar_ping(almacen, b, -34.9011, -56.1645, ahora + timedelta(minutes=m))
    total, _ = almacen.total_cruces(a.id)
    assert total <= 2  # una ventana de 30' contiene todos esos pings


def test_no_se_cruza_con_uno_mismo(almacen, hacer_perfil):
    a = alta(almacen, hacer_perfil)
    ahora = datetime.utcnow()
    cruces.registrar_ping(almacen, a, -34.9011, -56.1645, ahora)
    r = cruces.registrar_ping(almacen, a, -34.9011, -56.1645, ahora + timedelta(minutes=1))
    assert r["cruces_nuevos"] == []


def test_pings_viejos_se_borran(almacen, hacer_perfil):
    a = alta(almacen, hacer_perfil)
    viejo = datetime.utcnow() - timedelta(hours=10)
    cruces.registrar_ping(almacen, a, -34.9011, -56.1645, viejo)
    borrados = almacen.limpiar_pings(datetime.utcnow() - cruces.VIDA_PING)
    assert borrados >= 1


def test_cruces_de_excluye_a_quien_ya_descartaste(almacen, hacer_perfil):
    a = alta(almacen, hacer_perfil, preferencias=Preferencias(generos=[]))
    b = alta(almacen, hacer_perfil)
    ahora = datetime.utcnow()
    cruces.registrar_ping(almacen, a, -34.9011, -56.1645, ahora)
    cruces.registrar_ping(almacen, b, -34.9011, -56.1645, ahora + timedelta(minutes=1))
    almacen.interactuar(a, b.id, "pass")
    assert cruces.de(almacen, a) == []
