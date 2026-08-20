"""Segunda vuelta: los descartes viejos que hoy volverías a mirar.

Lo que se fija:
- sólo entran descartes con más de DIAS_ESPERA días — sin la espera esto sería
  un "deshacer" gratis y canibalizaría el rebobinar pago;
- la lista respeta los filtros duros DE HOY (regla 1);
- repescar borra el pass, registra un like por el camino normal (consume cupo,
  puede dar match) y no deja tocar descartes ajenos ni recientes.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from matcher import segundavuelta
from matcher.modelos import DatosInvalidos, Preferencias


@pytest.fixture
def ella(hacer_perfil, almacen):
    p = hacer_perfil(
        id="ella", email="ella@test.local", genero="mujer",
        preferencias=Preferencias(generos=["mujer"], edad_min=18, edad_max=99),
    )
    almacen.crear_perfil(p, "clave-larga-1")
    return p


def _crear(almacen, hacer_perfil, id_, genero="mujer", **kw):
    p = hacer_perfil(id=id_, email=f"{id_}@test.local", genero=genero, **kw)
    almacen.crear_perfil(p, "clave-larga-1")
    return p


def _hace(dias):
    return datetime.utcnow() - timedelta(days=dias)


def test_el_descarte_viejo_aparece_y_el_reciente_no(almacen, hacer_perfil, ella):
    vieja = _crear(almacen, hacer_perfil, "vieja")
    reciente = _crear(almacen, hacer_perfil, "reciente")
    almacen.interactuar(ella, vieja.id, "pass", ahora=_hace(10))
    almacen.interactuar(ella, reciente.id, "pass", ahora=_hace(2))

    ids = {p["id"] for p in segundavuelta.candidatos(almacen, ella)}
    assert vieja.id in ids
    assert reciente.id not in ids, "un descarte de hace 2 días es rebobinar, no segunda vuelta"


def test_respeta_los_filtros_de_hoy(almacen, hacer_perfil, ella):
    """Regla 1: si después del descarte pediste sólo mujeres, el hombre que
    descartaste antes no vuelve a aparecer ni acá."""
    el = _crear(almacen, hacer_perfil, "el", genero="hombre")
    otra = _crear(almacen, hacer_perfil, "otra")
    for p in (el, otra):
        almacen.interactuar(ella, p.id, "pass", ahora=_hace(10))

    ids = {p["id"] for p in segundavuelta.candidatos(almacen, ella)}
    assert el.id not in ids, "un hombre se coló en la segunda vuelta de quien pidió mujeres"
    assert otra.id in ids


def test_repescar_borra_el_pass_y_manda_el_like(almacen, hacer_perfil, ella):
    otra = _crear(almacen, hacer_perfil, "otra")
    almacen.interactuar(ella, otra.id, "pass", ahora=_hace(10))

    r = segundavuelta.repescar(almacen, ella, otra.id)
    assert r["match"] is False

    fila = almacen.con.execute(
        "SELECT tipo FROM interacciones WHERE de_id = ? AND a_id = ?", (ella.id, otra.id)
    ).fetchone()
    assert fila["tipo"] == "like", "el pass tiene que haberse convertido en like"
    # Y ya no está en la lista: le respondiste de nuevo.
    assert otra.id not in {p["id"] for p in segundavuelta.candidatos(almacen, ella)}


def test_repescar_hace_match_si_el_interes_era_mutuo(almacen, hacer_perfil, ella):
    """El caso que le da sentido a la pantalla: mientras vos la descartabas,
    ella te dio like. La repesca cierra el círculo en el acto."""
    otra = _crear(almacen, hacer_perfil, "otra")
    almacen.interactuar(ella, otra.id, "pass", ahora=_hace(10))
    almacen.interactuar(otra, ella.id, "like")

    r = segundavuelta.repescar(almacen, ella, otra.id)
    assert r["match"] is True


def test_no_se_puede_repescar_un_descarte_reciente(almacen, hacer_perfil, ella):
    """La espera es la diferencia con el rebobinar pago: sin ella, nadie
    pagaría rebobinar."""
    otra = _crear(almacen, hacer_perfil, "otra")
    almacen.interactuar(ella, otra.id, "pass", ahora=_hace(2))
    with pytest.raises(DatosInvalidos):
        segundavuelta.repescar(almacen, ella, otra.id)


def test_no_se_puede_repescar_a_quien_no_descartaste(almacen, hacer_perfil, ella):
    otra = _crear(almacen, hacer_perfil, "otra")
    with pytest.raises(DatosInvalidos):
        segundavuelta.repescar(almacen, ella, otra.id)


def test_los_inactivos_y_los_borrados_no_aparecen(almacen, hacer_perfil, ella):
    ida = _crear(almacen, hacer_perfil, "ida")
    almacen.interactuar(ella, ida.id, "pass", ahora=_hace(10))
    almacen.borrar_cuenta(ida)
    assert segundavuelta.candidatos(almacen, ella) == []


def test_ordena_por_compatibilidad(almacen, hacer_perfil, ella):
    """La pantalla existe para encontrar al que descartaste mal: el más
    compatible va primero, sin importar el orden de los descartes."""
    parecida = _crear(
        almacen, hacer_perfil, "parecida",
        intereses=list(ella.intereses), altura_cm=ella.altura_cm, politica=ella.politica,
    )
    distinta = _crear(almacen, hacer_perfil, "distinta", intereses=[], politica="izquierda")
    almacen.interactuar(ella, distinta.id, "pass", ahora=_hace(20))
    almacen.interactuar(ella, parecida.id, "pass", ahora=_hace(10))

    orden = [p["id"] for p in segundavuelta.candidatos(almacen, ella)]
    assert orden.index("parecida") < orden.index("distinta")


def test_por_http_pide_sesion_y_devuelve_la_forma_esperada(cliente):
    from tests.conftest import entrar

    assert cliente.get("/api/segunda-vuelta").status_code == 401
    r = cliente.get("/api/segunda-vuelta", headers=entrar(cliente))
    assert r.status_code == 200
    datos = r.json()
    assert datos["dias_espera"] == segundavuelta.DIAS_ESPERA
    assert isinstance(datos["personas"], list)
