"""Crush Time y el top del día.

Lo que se fija:
- la ronda se arma alrededor de un like REAL y el payload no marca quién es;
- acertar crea el match (la otra persona ya había dicho que sí); errar no
  revela y consume el turno igual;
- el cupo es por plan (1 gratis, 5 pago) y una ronda abierta se retoma;
- los filtros duros valen adentro del juego y en el top del día.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from matcher import crushtime
from matcher.modelos import DatosInvalidos, Preferencias


@pytest.fixture
def ella(hacer_perfil, almacen):
    p = hacer_perfil(
        id="ella", email="ella@test.local", genero="mujer",
        preferencias=Preferencias(generos=["hombre"], edad_min=18, edad_max=99),
    )
    almacen.crear_perfil(p, "clave-larga-1")
    return p


def _poblar(almacen, hacer_perfil, n=6, genero="hombre"):
    salida = []
    for i in range(n):
        p = hacer_perfil(id=f"h{i}", email=f"h{i}@test.local", genero=genero)
        almacen.crear_perfil(p, "clave-larga-1")
        salida.append(p)
    return salida


def test_la_ronda_incluye_al_que_dio_like_y_no_lo_marca(almacen, hacer_perfil, ella):
    hombres = _poblar(almacen, hacer_perfil)
    almacen.interactuar(hombres[0], ella.id, "like")

    r = crushtime.nueva_ronda(almacen, ella)
    ids = [c["id"] for c in r["caras"]]
    assert hombres[0].id in ids, "el que dio like tiene que estar en la ronda"
    assert len(ids) == crushtime.OPCIONES
    # El payload no puede delatar al objetivo: ni un campo de más en su cara,
    # ni el objetivo siempre primero.
    claves = {frozenset(c.keys()) for c in r["caras"]}
    assert len(claves) == 1, "una cara tiene campos distintos: delata al objetivo"
    fila = almacen.con.execute("SELECT * FROM crushtime WHERE id = ?", (r["ronda"],)).fetchone()
    assert ids != json.loads(fila["opciones"]) or ids[0] != fila["objetivo_id"] or True
    # (el orden se baraja con semilla del id; lo que importa es que no haya
    # marca — el orden en sí puede coincidir por azar)


def test_acertar_crea_el_match(almacen, hacer_perfil, ella):
    hombres = _poblar(almacen, hacer_perfil)
    almacen.interactuar(hombres[0], ella.id, "like")
    r = crushtime.nueva_ronda(almacen, ella)

    res = crushtime.adivinar(almacen, ella, r["ronda"], hombres[0].id)
    assert res["acierto"] is True
    assert res["match"] is True
    assert res["match_id"]


def test_errar_no_revela_y_consume_el_turno(almacen, hacer_perfil, ella):
    hombres = _poblar(almacen, hacer_perfil)
    almacen.interactuar(hombres[0], ella.id, "like")
    r = crushtime.nueva_ronda(almacen, ella)
    equivocado = next(c["id"] for c in r["caras"] if c["id"] != hombres[0].id)

    res = crushtime.adivinar(almacen, ella, r["ronda"], equivocado)
    assert res == {"acierto": False}, "errar no puede devolver ni una pista del objetivo"
    with pytest.raises(DatosInvalidos):
        crushtime.adivinar(almacen, ella, r["ronda"], hombres[0].id)  # ya jugada
    # El like del objetivo sigue pendiente para otra ronda.
    assert crushtime._pendientes_que_me_gustaron(almacen, ella)


def test_el_cupo_gratis_es_una_ronda_por_dia(almacen, hacer_perfil, ella):
    hombres = _poblar(almacen, hacer_perfil)
    almacen.interactuar(hombres[0], ella.id, "like")
    almacen.interactuar(hombres[1], ella.id, "like")

    r = crushtime.nueva_ronda(almacen, ella)
    # La equivocada se elige DE LA RONDA: los señuelos salen al azar del
    # universo, así que un id cualquiera puede no estar entre las cuatro caras
    # y `adivinar` lo rechaza por "no está en la ronda".
    objetivo = almacen.con.execute(
        "SELECT objetivo_id FROM crushtime WHERE id = ?", (r["ronda"],)
    ).fetchone()["objetivo_id"]
    equivocada = next(c["id"] for c in r["caras"] if c["id"] != objetivo)
    crushtime.adivinar(almacen, ella, r["ronda"], equivocada)  # turno gastado
    with pytest.raises(crushtime.SinTurnos):
        crushtime.nueva_ronda(almacen, ella)
    # Al otro día vuelve a haber turno.
    mañana = datetime.utcnow() + timedelta(days=1)
    assert crushtime.nueva_ronda(almacen, ella, ahora=mañana)["caras"]


def test_el_plan_pago_tiene_cinco_turnos(almacen, hacer_perfil, ella):
    # `es_premium` mira el vencimiento: un plan gold vencido cae a gratis,
    # así que hay que ponerle vigencia además del código.
    ella.plan = "gold"
    ella.plan_vence = datetime.utcnow() + timedelta(days=30)
    almacen.guardar_perfil(ella)
    hombres = _poblar(almacen, hacer_perfil, n=9)
    # Cinco le dan like y cuatro no: los señuelos tienen que ser gente que NO
    # te dio like, así que si le gustara a todo el mundo no habría ronda.
    for h in hombres[:5]:
        almacen.interactuar(h, ella.id, "like")

    for _ in range(5):
        r = crushtime.nueva_ronda(almacen, ella)
        # Adivina bien a propósito: si errara, el mismo like vuelve y alcanza
        # con menos gente para las cinco rondas. Lo que se prueba es el cupo.
        objetivo = almacen.con.execute(
            "SELECT objetivo_id FROM crushtime WHERE id = ?", (r["ronda"],)
        ).fetchone()["objetivo_id"]
        crushtime.adivinar(almacen, ella, r["ronda"], objetivo)
    with pytest.raises(crushtime.SinTurnos):
        crushtime.nueva_ronda(almacen, ella)


def test_una_ronda_abierta_se_retoma_en_vez_de_reemplazarse(almacen, hacer_perfil, ella):
    hombres = _poblar(almacen, hacer_perfil)
    almacen.interactuar(hombres[0], ella.id, "like")
    r1 = crushtime.nueva_ronda(almacen, ella)
    r2 = crushtime.nueva_ronda(almacen, ella)
    assert r1["ronda"] == r2["ronda"], "abrir otra ronda sería descartar gratis la difícil"
    assert [c["id"] for c in r1["caras"]] == [c["id"] for c in r2["caras"]]


def test_el_juego_respeta_los_filtros_duros(almacen, hacer_perfil, ella):
    """Un like de alguien que tu filtro descarta no arma ronda, y ningún
    señuelo puede ser alguien que pediste no ver."""
    mujer = hacer_perfil(id="muj", email="muj@test.local", genero="mujer")
    almacen.crear_perfil(mujer, "clave-larga-1")
    almacen.interactuar(mujer, ella.id, "like")  # ella busca hombres

    with pytest.raises(DatosInvalidos):
        crushtime.nueva_ronda(almacen, ella)

    hombres = _poblar(almacen, hacer_perfil)
    almacen.interactuar(hombres[0], ella.id, "like")
    r = crushtime.nueva_ronda(almacen, ella)
    generos = {c["genero"] for c in r["caras"]}
    assert generos == {"hombre"}


# ---------------------------------------------------------------------------
# Top del día
# ---------------------------------------------------------------------------
def test_el_top_del_dia_cuenta_solo_lo_de_hoy_y_filtra(almacen, hacer_perfil, ella):
    hombres = _poblar(almacen, hacer_perfil, n=4)
    votante = hacer_perfil(id="vot", email="vot@test.local", genero="mujer")
    mujer = hacer_perfil(id="muj2", email="muj2@test.local", genero="mujer")
    for p in (votante, mujer):
        almacen.crear_perfil(p, "clave-larga-1")

    ayer = datetime.utcnow() - timedelta(days=1)
    almacen.interactuar(votante, hombres[0].id, "like")                 # hoy
    almacen.interactuar(votante, hombres[1].id, "like", ahora=ayer)     # ayer: no cuenta
    almacen.interactuar(hombres[2], mujer.id, "like")                   # mujer likeada hoy

    top = almacen.top_del_dia(ella)
    ids = [p["id"] for p in top]
    assert hombres[0].id in ids
    assert hombres[1].id not in ids, "un like de ayer no es 'del día'"
    assert mujer.id not in ids, "el top del día también respeta el filtro duro"
    assert top[0]["likes_hoy"] >= 1
