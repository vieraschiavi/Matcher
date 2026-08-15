"""Boost: media hora arriba del deck.

Lo que se fija:
- el cupo es mensual y por plan, y el gratis no lo tiene;
- mientras corre, sube en el deck de los demás;
- **no rompe la ola ni los filtros**: un boost no te mete en el deck de quien
  te filtró ni te trae de otro continente. Eso es lo que separa "pagar por
  visibilidad" de "pagar por saltarse el filtro de otro", que es justo lo que
  el producto le critica a la competencia;
- vence solo, sin job que lo apague.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from matcher import boost
from matcher.modelos import Preferencias


def _premium(perfil, almacen, plan="gold"):
    perfil.plan = plan
    perfil.plan_vence = datetime.utcnow() + timedelta(days=30)
    almacen.guardar_perfil(perfil)
    return perfil


@pytest.fixture
def yo(hacer_perfil, almacen):
    p = hacer_perfil(id="yo", email="yo@test.local", genero="mujer")
    almacen.crear_perfil(p, "clave-larga-1")
    return p


def test_el_plan_gratis_no_tiene_boost(almacen, yo):
    assert boost.estado(almacen, yo)["maximo_mes"] == 0
    with pytest.raises(boost.SinBoosts):
        boost.activar(almacen, yo)


def test_gold_tiene_cuatro_por_mes(almacen, yo):
    _premium(yo, almacen, "gold")
    ahora = datetime(2026, 3, 10, 12, 0)
    for i in range(4):
        # Cada uno arranca después de que venció el anterior: si no, el
        # segundo devuelve "ya_estaba" y no gasta cupo (que es a propósito).
        boost.activar(almacen, yo, ahora=ahora + boost.DURACION * (i + 1))
    with pytest.raises(boost.SinBoosts):
        boost.activar(almacen, yo, ahora=ahora + boost.DURACION * 9)


def test_el_cupo_se_renueva_el_mes_siguiente(almacen, yo):
    _premium(yo, almacen, "plus")  # 1 por mes
    marzo = datetime(2026, 3, 10, 12, 0)
    boost.activar(almacen, yo, ahora=marzo)
    with pytest.raises(boost.SinBoosts):
        boost.activar(almacen, yo, ahora=marzo + timedelta(hours=3))
    abril = datetime(2026, 4, 1, 9, 0)
    assert boost.activar(almacen, yo, ahora=abril)["ya_estaba"] is False


def test_activar_dos_veces_seguidas_no_gasta_otro_cupo(almacen, yo):
    _premium(yo, almacen, "gold")
    ahora = datetime(2026, 3, 10, 12, 0)
    boost.activar(almacen, yo, ahora=ahora)
    r = boost.activar(almacen, yo, ahora=ahora + timedelta(minutes=5))
    assert r["ya_estaba"] is True
    assert r["usados_mes"] == 1, "apilar boosts tiraría el que ya está corriendo"


def test_vence_solo(almacen, yo):
    _premium(yo, almacen, "gold")
    ahora = datetime(2026, 3, 10, 12, 0)
    boost.activar(almacen, yo, ahora=ahora)
    assert boost.activo(almacen, yo.id, ahora + timedelta(minutes=10))
    assert boost.activo(almacen, yo.id, ahora + boost.DURACION + timedelta(seconds=1)) is None


# ---------------------------------------------------------------------------
# El efecto en el deck
# ---------------------------------------------------------------------------
def test_el_boost_sube_en_el_deck(almacen, hacer_perfil, yo):
    """Alguien impulsado sube — pero sólo dentro de su ola."""
    yo.preferencias = Preferencias(generos=["hombre"], edad_min=18, edad_max=99)
    almacen.guardar_perfil(yo)
    ellos = []
    for i in range(6):
        p = hacer_perfil(id=f"h{i}", email=f"h{i}@test.local", genero="hombre",
                         ciudad="UY-MVD", pais="UY")
        almacen.crear_perfil(p, "clave-larga-1")
        ellos.append(p)

    antes = [t["id"] for t in almacen.deck(yo, limite=10)["tarjetas"]]
    ultimo = antes[-1]

    impulsado = almacen.perfil(ultimo)
    _premium(impulsado, almacen, "gold")
    boost.activar(almacen, impulsado)

    despues = [t["id"] for t in almacen.deck(yo, limite=10)["tarjetas"]]
    assert despues.index(ultimo) < antes.index(ultimo), "el boost tiene que hacerlo subir"


def test_el_boost_no_saltea_el_filtro_duro(almacen, hacer_perfil, yo):
    """Lo más importante del módulo: el boost compra visibilidad, no el
    derecho a aparecerle a alguien que te filtró."""
    yo.preferencias = Preferencias(generos=["hombre"], edad_min=18, edad_max=99)
    almacen.guardar_perfil(yo)
    una_mujer = hacer_perfil(id="ella2", email="e2@test.local", genero="mujer")
    almacen.crear_perfil(una_mujer, "clave-larga-1")
    _premium(una_mujer, almacen, "gold")
    boost.activar(almacen, una_mujer)

    ids = [t["id"] for t in almacen.deck(yo, limite=50)["tarjetas"]]
    assert una_mujer.id not in ids


def test_el_boost_no_rompe_la_ola(almacen, hacer_perfil, yo):
    """Regla 3: la ola manda antes que el puntaje. Un boost de alguien de otro
    continente no puede pasarle por delante a alguien de tu ciudad."""
    yo.preferencias = Preferencias(generos=["hombre"], edad_min=18, edad_max=99)
    almacen.guardar_perfil(yo)
    vecino = hacer_perfil(id="vec", email="vec@test.local", genero="hombre",
                          pais="UY", ciudad="UY-MVD")
    lejano = hacer_perfil(id="lej", email="lej@test.local", genero="hombre",
                          pais="ES", ciudad="ES-MAD")
    for p in (vecino, lejano):
        almacen.crear_perfil(p, "clave-larga-1")
    _premium(lejano, almacen, "gold")
    boost.activar(almacen, lejano)

    ids = [t["id"] for t in almacen.deck(yo, limite=10)["tarjetas"]]
    assert ids.index(vecino.id) < ids.index(lejano.id)
