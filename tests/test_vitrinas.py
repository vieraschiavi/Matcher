"""Las dos vitrinas: "disponible hoy" y "más likeados por zona".

Lo que se fija acá:
- el filtro duro vale también en estas pantallas (regla 1);
- "disponible hoy" vence solo, así que el que se marcó hace tres días no
  figura — es toda la promesa de la sección;
- la cercanía manda antes que el puntaje en "disponible hoy" (regla 3);
- el alcance "barrio" es un radio real y se da vuelta al mover al usuario, sin
  cablear ninguna ciudad (regla 2);
- el tope de la lista es 200 y no se puede pasar por parámetro.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from matcher import geo, vitrinas
from matcher.modelos import Preferencias


@pytest.fixture
def ella(hacer_perfil, almacen):
    p = hacer_perfil(
        id="ella", email="ella@test.local", genero="mujer", pais="UY", ciudad="UY-MVD",
        preferencias=Preferencias(generos=["mujer"], edad_min=18, edad_max=99),
    )
    almacen.crear_perfil(p, "clave-larga-1")
    return p


def _crear(almacen, hacer_perfil, id_, genero="mujer", **kw):
    p = hacer_perfil(id=id_, email=f"{id_}@test.local", genero=genero, **kw)
    almacen.crear_perfil(p, "clave-larga-1")
    return p


# ---------------------------------------------------------------------------
# Disponible hoy
# ---------------------------------------------------------------------------
def test_solo_aparece_quien_esta_disponible(almacen, hacer_perfil, ella):
    libre = _crear(almacen, hacer_perfil, "libre", ciudad="UY-MVD", pais="UY")
    ocupada = _crear(almacen, hacer_perfil, "ocupada", ciudad="UY-MVD", pais="UY")
    libre.marcar_disponible()
    almacen.guardar_perfil(libre)

    ids = {p["id"] for p in vitrinas.disponibles_hoy(almacen, ella)["personas"]}
    assert libre.id in ids
    assert ocupada.id not in ids


def test_la_disponibilidad_vencida_no_cuenta(almacen, hacer_perfil, ella):
    """La promesa de la sección es "hoy". Un perfil que se marcó hace tres días
    y sigue figurando le miente a todo el que abre la pantalla."""
    vieja = _crear(almacen, hacer_perfil, "vieja", ciudad="UY-MVD", pais="UY")
    vieja.disponible_hasta = datetime.utcnow() - timedelta(hours=1)
    almacen.guardar_perfil(vieja)

    ids = {p["id"] for p in vitrinas.disponibles_hoy(almacen, ella)["personas"]}
    assert vieja.id not in ids


def test_disponibles_respeta_el_filtro_duro(almacen, hacer_perfil, ella):
    hombre = _crear(almacen, hacer_perfil, "el", genero="hombre", ciudad="UY-MVD", pais="UY")
    mujer = _crear(almacen, hacer_perfil, "ella2", genero="mujer", ciudad="UY-MVD", pais="UY")
    for p in (hombre, mujer):
        p.marcar_disponible()
        almacen.guardar_perfil(p)

    ids = {p["id"] for p in vitrinas.disponibles_hoy(almacen, ella)["personas"]}
    assert hombre.id not in ids, "un hombre se coló en 'disponible hoy' de quien pidió mujeres"
    assert mujer.id in ids


def test_disponibles_no_repite_a_quien_ya_respondiste(almacen, hacer_perfil, ella):
    """Es una lista para dar like. Volver a mostrar a alguien que ya
    descartaste es la forma más rápida de que la sección se sienta rota."""
    otra = _crear(almacen, hacer_perfil, "otra", ciudad="UY-MVD", pais="UY")
    otra.marcar_disponible()
    almacen.guardar_perfil(otra)
    assert otra.id in {p["id"] for p in vitrinas.disponibles_hoy(almacen, ella)["personas"]}

    almacen.interactuar(ella, otra.id, "pass")
    assert otra.id not in {p["id"] for p in vitrinas.disponibles_hoy(almacen, ella)["personas"]}


def test_disponibles_pone_la_cercania_antes_que_el_puntaje(almacen, hacer_perfil, ella):
    """Regla 3, y en esta sección es la que le da sentido: alguien disponible
    hoy en otro país no sirve para nada por más compatible que sea."""
    cerca = _crear(
        almacen, hacer_perfil, "cerca", ciudad="UY-MVD", pais="UY",
        intereses=[], altura_cm=160,
    )
    lejos = _crear(
        almacen, hacer_perfil, "lejos", ciudad="ES-MAD", pais="ES",
        intereses=list(ella.intereses), altura_cm=ella.altura_cm,
    )
    for p in (cerca, lejos):
        p.likes_recibidos = 0
        p.marcar_disponible()
        almacen.guardar_perfil(p)

    orden = [p["id"] for p in vitrinas.disponibles_hoy(almacen, ella)["personas"]]
    assert orden.index("cerca") < orden.index("lejos"), (
        "alguien de otro país se puso delante de alguien de la misma ciudad"
    )


# ---------------------------------------------------------------------------
# Más likeados por zona
# ---------------------------------------------------------------------------
def test_el_alcance_ciudad_deja_afuera_a_otras_ciudades(almacen, hacer_perfil, ella):
    local = _crear(almacen, hacer_perfil, "local", ciudad="UY-MVD", pais="UY")
    forastera = _crear(almacen, hacer_perfil, "forastera", ciudad="AR-BUE", pais="AR")

    ids = {p["id"] for p in vitrinas.mas_likeados(almacen, ella, alcance="ciudad")["top"]}
    assert local.id in ids
    assert forastera.id not in ids

    # Y en "mundo" están las dos: el alcance es lo único que cambia.
    ids_mundo = {p["id"] for p in vitrinas.mas_likeados(almacen, ella, alcance="mundo")["top"]}
    assert {local.id, forastera.id} <= ids_mundo


def test_la_ciudad_es_relativa_al_usuario(almacen, hacer_perfil):
    """Regla 2: nada de cablear un país. Si la usuaria es de Madrid, su ciudad
    es Madrid y Montevideo pasa a ser el extranjero."""
    madrilena = _crear(
        almacen, hacer_perfil, "mad", ciudad="ES-MAD", pais="ES",
        preferencias=Preferencias(generos=["mujer"], edad_min=18, edad_max=99),
    )
    de_madrid = _crear(almacen, hacer_perfil, "otra_mad", ciudad="ES-MAD", pais="ES")
    de_mvd = _crear(almacen, hacer_perfil, "de_mvd", ciudad="UY-MVD", pais="UY")

    ids = {p["id"] for p in vitrinas.mas_likeados(almacen, madrilena, alcance="ciudad")["top"]}
    assert de_madrid.id in ids
    assert de_mvd.id not in ids


def test_el_barrio_es_un_radio_y_se_da_vuelta_al_mover_al_usuario(almacen, hacer_perfil, ella):
    """El "barrio" no es un campo de texto, es un radio alrededor tuyo. Se
    comprueba moviendo a la usuaria: la misma vecina deja de serlo."""
    mvd = geo.coordenadas("UY-MVD")
    vecina = _crear(almacen, hacer_perfil, "vecina", ciudad="UY-MVD", pais="UY")
    # ~1 km al norte: adentro del radio de barrio.
    almacen.guardar_ubicacion(vecina.id, mvd[0] + 0.009, mvd[1], datetime.utcnow())
    almacen.guardar_ubicacion(ella.id, mvd[0], mvd[1], datetime.utcnow())

    ids = {p["id"] for p in vitrinas.mas_likeados(almacen, ella, alcance="barrio")["top"]}
    assert vecina.id in ids, "alguien a ~1 km tiene que entrar en el barrio"

    # Ahora la usuaria se mudó ~10 km: la misma persona queda fuera del barrio,
    # pero sigue estando en la ciudad.
    almacen.guardar_ubicacion(ella.id, mvd[0] + 0.09, mvd[1], datetime.utcnow())
    ids_lejos = {p["id"] for p in vitrinas.mas_likeados(almacen, ella, alcance="barrio")["top"]}
    assert vecina.id not in ids_lejos
    assert vecina.id in {
        p["id"] for p in vitrinas.mas_likeados(almacen, ella, alcance="ciudad")["top"]
    }


def test_mas_likeados_respeta_el_filtro_duro(almacen, hacer_perfil, ella):
    hombre = _crear(almacen, hacer_perfil, "el", genero="hombre", ciudad="UY-MVD", pais="UY")
    mujer = _crear(almacen, hacer_perfil, "ella2", genero="mujer", ciudad="UY-MVD", pais="UY")
    hombre.likes_recibidos = 9999
    almacen.guardar_perfil(hombre)

    for alcance in vitrinas.ALCANCES:
        ids = {p["id"] for p in vitrinas.mas_likeados(almacen, ella, alcance=alcance)["top"]}
        assert hombre.id not in ids, f"un hombre se coló en el alcance {alcance}"
    assert mujer.id in {
        p["id"] for p in vitrinas.mas_likeados(almacen, ella, alcance="ciudad")["top"]
    }


def test_el_tope_es_doscientos_y_no_se_puede_pedir_mas(almacen, hacer_perfil, ella):
    for i in range(210):
        _crear(almacen, hacer_perfil, f"m{i:03d}", ciudad="UY-MVD", pais="UY")

    r = vitrinas.mas_likeados(almacen, ella, alcance="ciudad", limite=99999)
    assert len(r["top"]) == vitrinas.TOPE_LISTA == 200
    assert r["total"] >= 210, "el total dice cuánta gente hay, aunque la lista corte en 200"


def test_el_puesto_lo_calcula_el_servidor_y_no_se_renumera(almacen, hacer_perfil, ella):
    """Si el puesto lo pusiera el cliente con el índice del array, cualquier
    perfil que el filtro de cliente saque correría la tabla entera y el #7
    pasaría a #6 sin haber subido un puesto."""
    for i in range(5):
        p = _crear(almacen, hacer_perfil, f"m{i}", ciudad="UY-MVD", pais="UY")
        p.likes_recibidos = 100 - i
        p.vistas_recibidas = 200
        almacen.guardar_perfil(p)

    top = vitrinas.mas_likeados(almacen, ella, alcance="ciudad")["top"]
    assert [f["puesto"] for f in top] == list(range(1, len(top) + 1))


def test_un_alcance_desconocido_cae_en_ciudad(almacen, hacer_perfil, ella):
    """No revienta con 500 ni devuelve el mundo entero: un parámetro raro cae
    en el alcance más conservador."""
    r = vitrinas.mas_likeados(almacen, ella, alcance="galaxia")
    assert r["alcance"] == "ciudad"


def test_sin_ubicacion_el_barrio_no_finge_ser_la_ciudad(almacen, hacer_perfil):
    """Si no se puede saber dónde está el usuario, el barrio va vacío. Devolver
    la ciudad entera llamándola "tu barrio" sería mentir sobre la distancia,
    que es justamente lo que la sección promete."""
    sin_lugar = _crear(
        almacen, hacer_perfil, "sinlugar", ciudad="XX-NOEXISTE", pais="UY",
        preferencias=Preferencias(generos=["mujer"], edad_min=18, edad_max=99),
    )
    _crear(almacen, hacer_perfil, "alguien", ciudad="UY-MVD", pais="UY")

    assert geo.coordenadas(sin_lugar.ciudad) is None, "el escenario necesita una ciudad sin coordenadas"
    assert vitrinas.mas_likeados(almacen, sin_lugar, alcance="barrio")["top"] == []
