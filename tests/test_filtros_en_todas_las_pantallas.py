"""El filtro duro vale en TODAS las pantallas, no sólo en el deck.

Regresión reportada con capturas: el usuario eligió "Mujer" en Filtros y le
aparecían hombres en "Te cruzaste con" y en "Te gustaron". El deck, el radar y
el automatch sí filtraban; `cruces.de` y `quien_me_dio_like` sólo miraban que
el perfil estuviera activo.

Es la regla 1 del producto —el filtro descarta, no compensa— así que estos
tests recorren cada superficie donde aparece gente y verifican que ninguna se
salte `filtros.pasa_filtros`. Si mañana se agrega una pantalla nueva que liste
personas, agregarla acá.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from matcher import cruces
from matcher.filtros import pasa_filtros
from matcher.modelos import Preferencias
from tests.conftest import entrar
from webapp.backend import api as backend


def cruzar(almacen, a, b, veces=2):
    ahora = datetime.utcnow()
    almacen.sumar_cruce(a, b, veces, ahora, ahora, "celda-1")


@pytest.fixture
def ella(hacer_perfil, almacen):
    """Busca sólo mujeres."""
    p = hacer_perfil(
        id="ella", email="ella@test.local", genero="mujer", ciudad="UY-MVD", pais="UY"
    )
    p.preferencias = Preferencias(generos=["mujer"], edad_min=18, edad_max=99)
    # Gold porque "ver quién me dio like" es de plan pago: con el gratis la
    # respuesta trae `perfiles: []` a propósito y no se podría comprobar el
    # filtrado de la lista.
    p.plan = "gold"
    almacen.crear_perfil(p, "clave-larga-1")
    return p


@pytest.fixture
def un_hombre(hacer_perfil, almacen):
    p = hacer_perfil(
        id="el", email="el@test.local", genero="hombre", ciudad="UY-MVD", pais="UY"
    )
    almacen.crear_perfil(p, "clave-larga-1")
    return p


@pytest.fixture
def una_mujer(hacer_perfil, almacen):
    p = hacer_perfil(
        id="otra", email="otra@test.local", genero="mujer", ciudad="UY-MVD", pais="UY"
    )
    almacen.crear_perfil(p, "clave-larga-1")
    return p


# ---------------------------------------------------------------------------
# Te cruzaste con
# ---------------------------------------------------------------------------
def test_los_cruces_no_muestran_a_quien_el_filtro_descarta(almacen, ella, un_hombre, una_mujer):
    for otro in (un_hombre, una_mujer):
        cruzar(almacen, ella.id, otro.id)

    ids = {p["id"] for p in cruces.de(almacen, ella)}
    assert un_hombre.id not in ids, "un hombre se coló en los cruces de quien pidió sólo mujeres"
    assert una_mujer.id in ids, "la mujer que sí pasa el filtro tiene que seguir apareciendo"


def test_al_cambiar_el_filtro_los_cruces_cambian(almacen, ella, un_hombre, una_mujer):
    """La regla se da vuelta: si ahora busca hombres, aparece el hombre."""
    for otro in (un_hombre, una_mujer):
        cruzar(almacen, ella.id, otro.id)

    ella.preferencias = Preferencias(generos=["hombre"], edad_min=18, edad_max=99)
    almacen.guardar_perfil(ella)

    ids = {p["id"] for p in cruces.de(almacen, ella)}
    assert un_hombre.id in ids
    assert una_mujer.id not in ids


def test_los_cruces_respetan_el_rango_de_edad(almacen, ella, hacer_perfil):
    joven = hacer_perfil(id="joven", email="j@test.local", genero="mujer", edad=22, ciudad="UY-MVD", pais="UY")
    grande = hacer_perfil(id="grande", email="g@test.local", genero="mujer", edad=58, ciudad="UY-MVD", pais="UY")
    for p in (joven, grande):
        almacen.crear_perfil(p, "clave-larga-1")
        cruzar(almacen, ella.id, p.id)

    ella.preferencias = Preferencias(generos=["mujer"], edad_min=18, edad_max=30)
    almacen.guardar_perfil(ella)

    ids = {p["id"] for p in cruces.de(almacen, ella)}
    assert joven.id in ids
    assert grande.id not in ids


# ---------------------------------------------------------------------------
# Te gustaron
# ---------------------------------------------------------------------------
def test_los_likes_recibidos_no_muestran_a_quien_el_filtro_descarta(
    almacen, ella, un_hombre, una_mujer
):
    almacen.interactuar(un_hombre, ella.id, "like")
    almacen.interactuar(una_mujer, ella.id, "like")

    r = almacen.quien_me_dio_like(ella)
    ids = {p["id"] for p in r["perfiles"]}
    assert un_hombre.id not in ids, "un hombre se coló en 'te gustaron' de quien pidió sólo mujeres"
    assert una_mujer.id in ids


def test_el_contador_de_likes_coincide_con_lo_que_se_ve(almacen, ella, un_hombre, una_mujer):
    """El conteo del plan gratis tiene que ser el mismo número que la lista que
    se ve al pagar. Si se filtra sólo la lista, el que paga ve menos de lo que
    le prometía el cartel."""
    almacen.interactuar(un_hombre, ella.id, "like")
    almacen.interactuar(una_mujer, ella.id, "like")

    visible = almacen.quien_me_dio_like(ella)
    assert visible["cantidad"] == len(visible["perfiles"]) == 1


# ---------------------------------------------------------------------------
# Barrido por HTTP: ningún endpoint que liste gente puede saltarse el filtro
# ---------------------------------------------------------------------------
# Este test es el que importa a largo plazo. Los de arriba prueban una función
# cada uno; éste recorre la API de punta a punta y falla si aparece una
# pantalla nueva que devuelva personas sin filtrar. "Más votados" se escapó
# justamente por eso: era el único listado que ni siquiera recibía al usuario.
RUTAS_QUE_LISTAN_GENTE = [
    ("/api/deck?limite=50", "tarjetas"),
    ("/api/radar?radio_km=200", "personas"),
    ("/api/cruces", "personas"),
    ("/api/likes-recibidos", "perfiles"),
    ("/api/ranking?limite=50", "top"),
]


def test_ninguna_pantalla_devuelve_a_quien_el_filtro_descarta(cliente):
    """Barrido por HTTP de todos los endpoints que listan gente.

    No mira el género del payload —cada endpoint devuelve una forma distinta y
    "más votados" ni siquiera lo incluye— sino que compara los ids contra los
    que el motor considera aceptables. Así el test sirve igual si mañana cambia
    la forma de una respuesta.
    """
    cabeceras = entrar(cliente)
    assert cliente.patch(
        "/api/yo",
        json={"preferencias": {"generos": ["mujer"], "edad_min": 18, "edad_max": 99}},
        headers=cabeceras,
    ).status_code == 200

    a = backend._almacen
    yo = a.perfil(cliente.get("/api/yo", headers=cabeceras).json()["perfil"]["id"])
    prohibidos = {
        o.id for o in a.todos() if o.id != yo.id and not pasa_filtros(yo, o, reciproco=False)[0]
    }
    assert prohibidos, "el escenario no sirve si no hay nadie a quien filtrar"

    for ruta, campo in RUTAS_QUE_LISTAN_GENTE:
        resp = cliente.get(ruta, headers=cabeceras)
        assert resp.status_code == 200, f"{ruta} → {resp.status_code} {resp.text[:120]}"
        devueltos = {p["id"] for p in (resp.json().get(campo) or []) if isinstance(p, dict)}
        colados = devueltos & prohibidos
        assert not colados, f"{ruta} devolvió {len(colados)} perfiles que el filtro descarta"


def test_el_ranking_sin_sesion_sigue_siendo_publico(cliente):
    """La vitrina se puede mirar sin cuenta. Filtrar exige saber por quién."""
    r = cliente.get("/api/ranking?limite=50")
    assert r.status_code == 200
    assert len(r.json()["top"]) > 0
