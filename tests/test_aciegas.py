"""Cita a ciegas: primero la charla, después las caras.

Lo que estos tests fijan, en orden de importancia:

1. **Las fotos no viajan** hasta que los dos escribieron el umbral. Es la
   regla 8 del producto aplicada al feature: un blur en el cliente se saca
   con "inspeccionar elemento"; acá el payload directamente no trae las URLs.
2. La elección respeta los filtros duros DE LOS DOS (recíproco).
3. La revelación es derivada de los mensajes reales, sin estado aparte.
4. Una sola cita sin revelar por vez.
"""

from __future__ import annotations

import pytest

from matcher import aciegas
from matcher.modelos import DatosInvalidos, Preferencias


@pytest.fixture
def martin(hacer_perfil, almacen):
    p = hacer_perfil(id="martin", email="m@test.local", genero="hombre")
    p.preferencias = Preferencias(generos=["mujer"], edad_min=18, edad_max=99)
    almacen.crear_perfil(p, "clave-larga-1")
    return p


def _con_fotos(perfil) -> bool:
    return bool(perfil.get("fotos"))


def test_elige_a_alguien_que_pasa_los_filtros_de_los_dos(almacen, hacer_perfil, martin):
    # La compatible: mujer que busca hombres.
    ana = hacer_perfil(
        id="ana", email="a@test.local", genero="mujer",
        preferencias=Preferencias(generos=["hombre"], edad_min=18, edad_max=99),
    )
    # El descarte 1: hombre (no pasa MI filtro).
    beto = hacer_perfil(id="beto", email="b@test.local", genero="hombre")
    # El descarte 2: mujer que busca mujeres (yo no paso SU filtro).
    carla = hacer_perfil(
        id="carla", email="c@test.local", genero="mujer",
        preferencias=Preferencias(generos=["mujer"], edad_min=18, edad_max=99),
    )
    for p in (ana, beto, carla):
        almacen.crear_perfil(p, "clave-larga-1")

    m = aciegas.crear(almacen, martin)
    assert m.otro(martin.id) == "ana"


def test_sin_candidatos_lo_dice_en_vez_de_inventar(almacen, hacer_perfil, martin):
    # Sólo hay hombres y Martín busca mujeres: no hay cita posible.
    almacen.crear_perfil(hacer_perfil(id="x", email="x@test.local", genero="hombre"), "clave-larga-1")
    with pytest.raises(DatosInvalidos):
        aciegas.crear(almacen, martin)


def test_las_fotos_no_viajan_hasta_el_umbral(almacen, hacer_perfil, martin):
    ana = hacer_perfil(
        id="ana", email="a@test.local", genero="mujer",
        preferencias=Preferencias(generos=["hombre"], edad_min=18, edad_max=99),
    )
    almacen.crear_perfil(ana, "clave-larga-1")
    m = aciegas.crear(almacen, martin)

    # Recién creado: ninguno escribió, fotos ocultas para los dos lados.
    for quien in (martin, ana):
        [fila] = almacen.matches_de(quien.id)
        assert fila["ciego"]["revelado"] is False
        assert not _con_fotos(fila["con"]), "una foto salió del servidor antes de la revelación"
        assert fila["con"]["silueta"] is True

    # Escriben 6 y 6: se revela para los dos, con las fotos de verdad.
    for i in range(aciegas.UMBRAL):
        almacen.enviar_mensaje(m.id, martin, f"hola {i}")
        almacen.enviar_mensaje(m.id, ana, f"hola {i}")

    for quien in (martin, ana):
        [fila] = almacen.matches_de(quien.id)
        assert fila["ciego"]["revelado"] is True
        assert _con_fotos(fila["con"])


def test_escribir_solo_uno_no_revela(almacen, hacer_perfil, martin):
    """El umbral es de CADA UNO: un monólogo de doce mensajes no revela nada.
    Si no, alcanza con spamear para ver las fotos sin conversar."""
    ana = hacer_perfil(
        id="ana", email="a@test.local", genero="mujer",
        preferencias=Preferencias(generos=["hombre"], edad_min=18, edad_max=99),
    )
    almacen.crear_perfil(ana, "clave-larga-1")
    m = aciegas.crear(almacen, martin)

    for i in range(aciegas.UMBRAL * 2):
        almacen.enviar_mensaje(m.id, martin, f"hola {i}")

    [fila] = almacen.matches_de(martin.id)
    assert fila["ciego"]["revelado"] is False
    assert not _con_fotos(fila["con"])
    assert fila["ciego"]["mios"] == aciegas.UMBRAL  # tope: no infla el contador
    assert fila["ciego"]["suyos"] == 0


def test_una_sola_cita_sin_revelar_por_vez(almacen, hacer_perfil, martin):
    for i, email in enumerate(["a@test.local", "b2@test.local"]):
        almacen.crear_perfil(
            hacer_perfil(
                id=f"cand{i}", email=email, genero="mujer",
                preferencias=Preferencias(generos=["hombre"], edad_min=18, edad_max=99),
            ),
            "clave-larga-1",
        )
    aciegas.crear(almacen, martin)
    with pytest.raises(DatosInvalidos):
        aciegas.crear(almacen, martin)


def test_los_matches_comunes_no_se_ven_afectados(almacen, hacer_perfil, martin):
    """Un match normal sigue trayendo las fotos desde el primer segundo."""
    ana = hacer_perfil(
        id="ana", email="a@test.local", genero="mujer",
        preferencias=Preferencias(generos=["hombre"], edad_min=18, edad_max=99),
    )
    almacen.crear_perfil(ana, "clave-larga-1")
    almacen.interactuar(martin, "ana", "like")
    almacen.interactuar(ana, "martin", "like")

    [fila] = almacen.matches_de(martin.id)
    assert fila["ciego"] is None
    assert _con_fotos(fila["con"])
