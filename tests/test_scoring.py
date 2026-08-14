"""Compatibilidad, popularidad y orden del deck."""

from datetime import datetime, timedelta

from matcher import scoring
from matcher.modelos import Preferencias


def test_compatibilidad_esta_acotada_y_es_simetrica(hacer_perfil):
    a = hacer_perfil(equipo="Peñarol", politica="izquierda", intereses=["cine", "mate"])
    b = hacer_perfil(equipo="Nacional", politica="derecha", intereses=["asado"])
    for x, y in ((a, b), (b, a)):
        c, _ = scoring.compatibilidad(x, y)
        assert 0 <= c <= 100
    # Sin preferencias de altura declaradas el cálculo es simétrico.
    assert scoring.compatibilidad(a, b)[0] == scoring.compatibilidad(b, a)[0]


def test_mismo_equipo_puntua_mas_que_el_clasico(hacer_perfil):
    yo = hacer_perfil(equipo="Peñarol", pais="UY")
    igual = hacer_perfil(equipo="Peñarol", pais="UY")
    rival = hacer_perfil(equipo="Nacional", pais="UY")
    assert scoring.afinidad_futbol(yo, igual) > scoring.afinidad_futbol(yo, rival)


def test_izquierda_contra_derecha_es_el_peor_cruce(hacer_perfil):
    assert scoring.afinidad_politica("izquierda", "izquierda") == 1.0
    assert scoring.afinidad_politica("izquierda", "derecha") < scoring.afinidad_politica(
        "izquierda", "neutro"
    )
    assert scoring.afinidad_politica("neutro", "derecha") == scoring.afinidad_politica(
        "derecha", "neutro"
    )


def test_intereses_no_castigan_al_que_carga_muchos():
    # 4 en común. Con Jaccard el segundo caso daba mucho menos que el primero
    # sólo por tener más intereses cargados, que es al revés de lo que espera
    # el usuario.
    pocos = scoring.afinidad_intereses(["a", "b", "c", "d"], ["a", "b", "c", "d"])
    muchos = scoring.afinidad_intereses(["a", "b", "c", "d"], ["a", "b", "c", "d", "e", "f", "g"])
    assert pocos == 1.0
    assert muchos == 1.0
    assert scoring.afinidad_intereses([], ["a"]) == 0.60


def test_una_pareja_muy_afin_supera_el_umbral_de_automatch(hacer_perfil):
    """Si el mejor caso posible no llega al umbral, el automatch nunca dispara
    y la función queda muerta sin que nadie se entere."""
    comunes = ["cine", "mate", "asado", "viajar", "perros"]
    a = hacer_perfil(edad=32, equipo="Peñarol", politica="izquierda", intereses=comunes)
    b = hacer_perfil(edad=33, equipo="Peñarol", politica="izquierda", intereses=comunes)
    comp, _ = scoring.compatibilidad(a, b)
    assert comp >= 80, f"el techo de compatibilidad quedó bajo: {comp}"


def test_popularidad_no_satura_y_castiga_la_muestra_chica(hacer_perfil):
    novato = hacer_perfil(likes_recibidos=1, vistas_recibidas=1)
    consagrado = hacer_perfil(likes_recibidos=300, vistas_recibidas=1000)
    tibio = hacer_perfil(likes_recibidos=40, vistas_recibidas=1000)
    assert scoring.popularidad(consagrado) > scoring.popularidad(novato)
    assert scoring.popularidad(consagrado) > scoring.popularidad(tibio)
    # Nadie llega a 100: si el tope es alcanzable, el ranking empata arriba.
    assert scoring.popularidad(consagrado) < 100


def test_superfan_pesa_mas_que_un_like(hacer_perfil):
    con_likes = hacer_perfil(likes_recibidos=9, vistas_recibidas=100)
    con_fans = hacer_perfil(likes_recibidos=0, superfans_recibidos=9, vistas_recibidas=100)
    assert scoring.popularidad(con_fans) > scoring.popularidad(con_likes)


def test_actividad_cae_con_el_tiempo(hacer_perfil):
    ahora = datetime(2026, 8, 14, 12, 0)
    hoy = hacer_perfil(ultima_actividad=ahora - timedelta(hours=2))
    semana = hacer_perfil(ultima_actividad=ahora - timedelta(days=5))
    fantasma = hacer_perfil(ultima_actividad=ahora - timedelta(days=200))
    assert (
        scoring.actividad(hoy, ahora)
        > scoring.actividad(semana, ahora)
        > scoring.actividad(fantasma, ahora)
    )


def test_la_ola_manda_antes_que_el_puntaje(hacer_perfil):
    """Regresión que se paga cara: alguien de otro continente colándose
    delante de alguien de tu ciudad porque tiene mejor score."""
    yo = hacer_perfil(pais="UY", ciudad="UY-MVD", preferencias=Preferencias(generos=[]))
    vecina = hacer_perfil(
        pais="UY", ciudad="UY-MVD", nombre="Vecina", politica="derecha", intereses=[]
    )
    perfecta_lejos = hacer_perfil(
        pais="DE",
        ciudad="DE-BER",
        nombre="Lejana",
        politica=yo.politica,
        intereses=yo.intereses or ["cine"],
        likes_recibidos=900,
        vistas_recibidas=1000,
    )
    orden = scoring.ordenar_deck(yo, [perfecta_lejos, vecina])
    assert orden[0]["id"] == vecina.id
    assert orden[0]["ola"] == "ciudad"


def test_sin_priorizar_cercania_gana_el_puntaje(hacer_perfil):
    yo = hacer_perfil(pais="UY", ciudad="UY-MVD")
    floja_cerca = hacer_perfil(pais="UY", ciudad="UY-MVD", politica="derecha")
    buena_lejos = hacer_perfil(
        pais="DE", ciudad="DE-BER", politica=yo.politica, likes_recibidos=900, vistas_recibidas=1000
    )
    orden = scoring.ordenar_deck(yo, [floja_cerca, buena_lejos], priorizar_cercania=False)
    assert [d["id"] for d in orden] == sorted(
        [d["id"] for d in orden], key=lambda i: -next(x["puntaje"] for x in orden if x["id"] == i)
    )


def test_el_orden_del_deck_es_determinista(hacer_perfil):
    yo = hacer_perfil()
    candidatos = [hacer_perfil() for _ in range(12)]
    ahora = datetime(2026, 8, 14, 9, 0)
    a = [d["id"] for d in scoring.ordenar_deck(yo, candidatos, ahora=ahora)]
    b = [d["id"] for d in scoring.ordenar_deck(yo, list(reversed(candidatos)), ahora=ahora)]
    assert a == b


def test_boost_premium_esta_acotado(hacer_perfil):
    """El premium empuja, no arrasa: si el que paga se come el deck, la
    experiencia gratis se degrada y la app se queda sin los dos lados."""
    assert max(scoring.BOOST_PLAN.values()) <= 1 + scoring.TOPE_BOOST_EN_DECK


def test_motivos_solo_dicen_verdades(hacer_perfil):
    yo = hacer_perfil(equipo="Peñarol", politica="izquierda", intereses=["cine"])
    otro = hacer_perfil(equipo="Peñarol", politica="izquierda", intereses=["cine", "asado"])
    _, desglose = scoring.compatibilidad(yo, otro)
    ms = scoring.motivos(yo, otro, desglose)
    assert any("Peñarol" in m for m in ms)
    assert any("izquierda" in m for m in ms)
    assert any("cine" in m for m in ms)

    # Nada en común: no se inventa una afinidad para llenar la tarjeta.
    ajeno = hacer_perfil(equipo="", politica="derecha", intereses=["ajedrez"], pais="DE",
                         ciudad="DE-BER")
    _, d2 = scoring.compatibilidad(yo, ajeno)
    assert scoring.motivos(yo, ajeno, d2) == []


def test_top_votados_excluye_inactivos_y_sin_foto(hacer_perfil):
    vivo = hacer_perfil(likes_recibidos=50, vistas_recibidas=100)
    apagado = hacer_perfil(likes_recibidos=90, vistas_recibidas=100, activo=False)
    sin_foto = hacer_perfil(likes_recibidos=90, vistas_recibidas=100)
    sin_foto.fotos = []
    ids = [f["id"] for f in scoring.top_votados([vivo, apagado, sin_foto])]
    assert ids == [vivo.id]
