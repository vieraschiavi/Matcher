"""Los filtros son DUROS: lo que se descarta, se descarta.

Media suite existe para impedir la regresión clásica de este tipo de app:
que un filtro pase a ser "un peso más" del score y el usuario vea gente que
pidió explícitamente no ver.
"""

from matcher import filtros
from matcher.modelos import Preferencias


def test_equipo_es_filtro_duro_aunque_el_resto_sea_perfecto(hacer_perfil):
    yo = hacer_perfil(
        genero="hombre",
        equipo="Peñarol",
        politica="izquierda",
        intereses=["asado", "cine", "mate"],
        preferencias=Preferencias(busca="mujeres", equipos=["Peñarol"]),
    )
    # Idéntica en todo lo demás — misma ciudad, misma edad, misma política,
    # mismos intereses — pero de otro cuadro.
    otra = hacer_perfil(
        genero="mujer",
        equipo="Nacional",
        politica="izquierda",
        intereses=["asado", "cine", "mate"],
        preferencias=Preferencias(busca="hombres"),
    )
    ok, motivo = filtros.pasa_filtros(yo, otra)
    assert not ok and motivo == "equipo"


def test_equipo_compara_sin_tildes_ni_mayusculas(hacer_perfil):
    yo = hacer_perfil(
        genero="hombre", preferencias=Preferencias(busca="mujeres", equipos=["PENAROL"])
    )
    ella = hacer_perfil(genero="mujer", equipo="Peñarol", preferencias=Preferencias(busca="todos"))
    assert filtros.pasa_filtros(yo, ella)[0]


def test_politica_filtra_y_lista_vacia_no_filtra(hacer_perfil):
    yo = hacer_perfil(
        genero="hombre",
        preferencias=Preferencias(busca="mujeres", politicas=["izquierda", "neutro"]),
    )
    izq = hacer_perfil(genero="mujer", politica="izquierda", preferencias=Preferencias(busca="todos"))
    der = hacer_perfil(genero="mujer", politica="derecha", preferencias=Preferencias(busca="todos"))
    assert filtros.pasa_filtros(yo, izq)[0]
    assert filtros.pasa_filtros(yo, der) == (False, "politica")

    yo.preferencias.politicas = []
    assert filtros.pasa_filtros(yo, der)[0]


def test_rango_de_altura(hacer_perfil):
    yo = hacer_perfil(
        genero="mujer",
        preferencias=Preferencias(busca="hombres", altura_min_cm=175, altura_max_cm=195),
    )
    alto = hacer_perfil(genero="hombre", altura_cm=188, preferencias=Preferencias(busca="todos"))
    bajo = hacer_perfil(genero="hombre", altura_cm=168, preferencias=Preferencias(busca="todos"))
    gigante = hacer_perfil(genero="hombre", altura_cm=205, preferencias=Preferencias(busca="todos"))
    assert filtros.pasa_filtros(yo, alto)[0]
    assert filtros.pasa_filtros(yo, bajo) == (False, "altura")
    assert filtros.pasa_filtros(yo, gigante) == (False, "altura")


def test_rango_de_edad_en_los_dos_bordes(hacer_perfil):
    yo = hacer_perfil(
        edad=30, genero="mujer", preferencias=Preferencias(busca="hombres", edad_min=28, edad_max=38)
    )
    dentro = hacer_perfil(edad=33, genero="hombre", preferencias=Preferencias(busca="todos"))
    joven = hacer_perfil(edad=24, genero="hombre", preferencias=Preferencias(busca="todos"))
    mayor = hacer_perfil(edad=44, genero="hombre", preferencias=Preferencias(busca="todos"))
    assert filtros.pasa_filtros(yo, dentro)[0]
    assert filtros.pasa_filtros(yo, joven) == (False, "edad")
    assert filtros.pasa_filtros(yo, mayor) == (False, "edad")


def test_reciprocidad_evita_el_deck_de_gente_que_nunca_dara_like(hacer_perfil):
    # Yo busco hombres; él busca mujeres pero yo tengo 60 y su tope es 40.
    yo = hacer_perfil(edad=60, genero="mujer", preferencias=Preferencias(busca="hombres"))
    el = hacer_perfil(
        edad=35,
        genero="hombre",
        preferencias=Preferencias(busca="mujeres", edad_min=25, edad_max=40),
    )
    assert filtros.pasa_filtros(yo, el) == (False, "edad_inversa")
    # Sin reciprocidad sí pasaría: es exactamente la diferencia que se quiere.
    assert filtros.pasa_filtros(yo, el, reciproco=False)[0]


def test_distancia_y_solo_mi_pais(hacer_perfil):
    yo = hacer_perfil(
        genero="hombre",
        ciudad="UY-MVD",
        preferencias=Preferencias(busca="todos", distancia_max_km=50),
    )
    cerca = hacer_perfil(genero="mujer", ciudad="UY-CAN", preferencias=Preferencias(busca="todos"))
    lejos = hacer_perfil(genero="mujer", ciudad="UY-SAL", preferencias=Preferencias(busca="todos"))
    assert filtros.pasa_filtros(yo, cerca)[0]
    assert filtros.pasa_filtros(yo, lejos) == (False, "distancia")

    yo.preferencias.distancia_max_km = None
    yo.preferencias.solo_mi_pais = True
    extranjera = hacer_perfil(
        genero="mujer", pais="AR", ciudad="AR-BUE", preferencias=Preferencias(busca="todos")
    )
    assert filtros.pasa_filtros(yo, extranjera) == (False, "pais")


def test_no_binario_entra_en_busqueda_abierta_y_no_en_una_cerrada(hacer_perfil):
    abierto = hacer_perfil(genero="mujer", preferencias=Preferencias(busca="todos"))
    cerrado = hacer_perfil(genero="mujer", preferencias=Preferencias(busca="mujeres"))
    nb = hacer_perfil(genero="no_binario", preferencias=Preferencias(busca="todos"))
    assert filtros.pasa_filtros(abierto, nb)[0]
    assert filtros.pasa_filtros(cerrado, nb) == (False, "genero")


def test_perfil_sin_foto_no_entra_al_deck(hacer_perfil):
    yo = hacer_perfil(preferencias=Preferencias(busca="todos"))
    sin_foto = hacer_perfil(preferencias=Preferencias(busca="todos"))
    sin_foto.fotos = []
    assert filtros.pasa_filtros(yo, sin_foto) == (False, "incompleto")


def test_ya_visto_no_se_repite(hacer_perfil):
    yo = hacer_perfil(preferencias=Preferencias(busca="todos"))
    otra = hacer_perfil(preferencias=Preferencias(busca="todos"))
    assert filtros.pasa_filtros(yo, otra)[0]
    assert filtros.pasa_filtros(yo, otra, vistos={otra.id}) == (False, "visto")


def test_diagnostico_cuenta_por_motivo(hacer_perfil):
    yo = hacer_perfil(
        genero="hombre", preferencias=Preferencias(busca="mujeres", politicas=["izquierda"])
    )
    universo = [
        hacer_perfil(genero="mujer", politica="derecha", preferencias=Preferencias(busca="todos")),
        hacer_perfil(genero="mujer", politica="derecha", preferencias=Preferencias(busca="todos")),
        hacer_perfil(genero="hombre", preferencias=Preferencias(busca="todos")),
    ]
    d = filtros.diagnostico(yo, universo)
    assert d["politica"] == 2
    assert d["genero"] == 1
