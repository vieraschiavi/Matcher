"""Match automático: propone sólo cuando de verdad califica."""

from matcher import automatch
from matcher.modelos import Preferencias

COMUNES = ["cine", "mate", "asado", "viajar", "perros"]


def alta(almacen, hacer_perfil, **kw):
    p = hacer_perfil(**kw)
    almacen.crear_perfil(p, "clave-larga-1")
    return p


def test_propone_a_la_pareja_muy_afin(almacen, hacer_perfil):
    yo = alta(
        almacen,
        hacer_perfil,
        genero="hombre",
        edad=32,
        equipo="Peñarol",
        politica="izquierda",
        intereses=COMUNES,
        preferencias=Preferencias(generos=["mujer"]),
    )
    ella = alta(
        almacen,
        hacer_perfil,
        genero="mujer",
        edad=31,
        equipo="Peñarol",
        politica="izquierda",
        intereses=COMUNES,
        preferencias=Preferencias(generos=["hombre"]),
    )
    creados = automatch.proponer(almacen, yo)
    assert [c["con"]["id"] for c in creados] == [ella.id]
    assert creados[0]["compatibilidad"] >= automatch.UMBRAL
    # Queda marcado como automático: nadie deslizó y eso se dice.
    assert almacen.matches_de(yo.id)[0]["automatico"] is True


def test_no_propone_a_quien_no_supera_el_umbral(almacen, hacer_perfil):
    yo = alta(
        almacen,
        hacer_perfil,
        genero="hombre",
        edad=25,
        politica="izquierda",
        intereses=["ajedrez"],
        preferencias=Preferencias(generos=["mujer"]),
    )
    alta(
        almacen,
        hacer_perfil,
        genero="mujer",
        edad=48,
        politica="derecha",
        pais="DE",
        ciudad="DE-BER",
        intereses=["surf"],
        preferencias=Preferencias(generos=["hombre"], edad_min=18, edad_max=99),
    )
    assert automatch.proponer(almacen, yo) == []


def test_no_propone_a_quien_ya_descartaste(almacen, hacer_perfil):
    yo = alta(
        almacen,
        hacer_perfil,
        genero="hombre",
        edad=32,
        equipo="Peñarol",
        politica="izquierda",
        intereses=COMUNES,
        preferencias=Preferencias(generos=["mujer"]),
    )
    ella = alta(
        almacen,
        hacer_perfil,
        genero="mujer",
        edad=31,
        equipo="Peñarol",
        politica="izquierda",
        intereses=COMUNES,
        preferencias=Preferencias(generos=["hombre"]),
    )
    almacen.interactuar(yo, ella.id, "pass")
    assert automatch.proponer(almacen, yo) == []


def test_respeta_los_filtros_duros_del_OTRO(almacen, hacer_perfil):
    """Simetría real: no alcanza con que ella me guste a mí en el papel; yo
    tengo que pasar TODOS sus filtros, no sólo género y edad."""
    yo = alta(
        almacen,
        hacer_perfil,
        genero="hombre",
        edad=32,
        altura_cm=170,
        equipo="Peñarol",
        politica="izquierda",
        intereses=COMUNES,
        preferencias=Preferencias(generos=["mujer"]),
    )
    alta(
        almacen,
        hacer_perfil,
        genero="mujer",
        edad=31,
        equipo="Peñarol",
        politica="izquierda",
        intereses=COMUNES,
        preferencias=Preferencias(generos=["hombre"], altura_min_cm=185),
    )
    assert automatch.proponer(almacen, yo) == []


def test_respeta_el_cupo_diario_del_plan(almacen, hacer_perfil):
    yo = alta(
        almacen,
        hacer_perfil,
        genero="hombre",
        edad=32,
        equipo="Peñarol",
        politica="izquierda",
        intereses=COMUNES,
        preferencias=Preferencias(generos=["mujer"]),
    )
    for _ in range(6):
        alta(
            almacen,
            hacer_perfil,
            genero="mujer",
            edad=32,
            equipo="Peñarol",
            politica="izquierda",
            intereses=COMUNES,
            preferencias=Preferencias(generos=["hombre"]),
        )
    creados = automatch.proponer(almacen, yo)
    # Gratis: 1 por día.
    assert len(creados) == 1
    assert automatch.proponer(almacen, yo) == []


def test_sugerencias_no_crean_nada(almacen, hacer_perfil):
    yo = alta(
        almacen,
        hacer_perfil,
        genero="hombre",
        edad=32,
        equipo="Peñarol",
        politica="izquierda",
        intereses=COMUNES,
        preferencias=Preferencias(generos=["mujer"]),
    )
    alta(
        almacen,
        hacer_perfil,
        genero="mujer",
        edad=31,
        equipo="Peñarol",
        politica="izquierda",
        intereses=COMUNES,
        preferencias=Preferencias(generos=["hombre"]),
    )
    s = automatch.sugerencias(almacen, yo)
    assert len(s) == 1
    assert almacen.matches_de(yo.id) == []
