"""Interacciones, matches, chat, cupos y persistencia."""

from datetime import datetime, timedelta

import pytest

from matcher import planes
from matcher.almacen import SinCupo
from matcher.modelos import DatosInvalidos, Preferencias


def alta(almacen, hacer_perfil, **kw):
    p = hacer_perfil(**kw)
    almacen.crear_perfil(p, "clave-larga-1")
    return p


def test_alta_login_y_token(almacen, hacer_perfil):
    p = alta(almacen, hacer_perfil, email="ana@test.local")
    assert almacen.login("ana@test.local", "mal") is None
    perfil, token = almacen.login("ana@test.local", "clave-larga-1")
    assert perfil.id == p.id
    assert almacen.por_token(token).id == p.id
    almacen.logout(token)
    assert almacen.por_token(token) is None


def test_email_duplicado(almacen, hacer_perfil):
    alta(almacen, hacer_perfil, email="dup@test.local")
    with pytest.raises(DatosInvalidos, match="ya existe"):
        alta(almacen, hacer_perfil, email="DUP@test.local")  # case-insensitive


def test_perfil_va_y_vuelve_entero(almacen, hacer_perfil):
    p = alta(
        almacen,
        hacer_perfil,
        equipo="Peñarol",
        politica="izquierda",
        intereses=["mate", "cine"],
        bio="hola",
        preferencias=Preferencias(generos=["mujer"], altura_min_cm=160, equipos=["Peñarol"]),
    )
    leido = almacen.perfil(p.id)
    assert leido.equipo == "Peñarol"
    assert leido.intereses == ["mate", "cine"]
    assert leido.preferencias.equipos == ["Peñarol"]
    assert leido.preferencias.altura_min_cm == 160
    assert leido.edad() == p.edad()


def test_like_reciproco_crea_match(almacen, hacer_perfil):
    a = alta(almacen, hacer_perfil, genero="hombre", preferencias=Preferencias(generos=[]))
    b = alta(almacen, hacer_perfil, genero="mujer", preferencias=Preferencias(generos=[]))
    r1 = almacen.interactuar(a, b.id, "like")
    assert r1["match"] is False
    r2 = almacen.interactuar(b, a.id, "like")
    assert r2["match"] is True
    assert len(almacen.matches_de(a.id)) == 1
    assert len(almacen.matches_de(b.id)) == 1


def test_el_match_no_se_duplica_en_los_dos_sentidos(almacen, hacer_perfil):
    a = alta(almacen, hacer_perfil)
    b = alta(almacen, hacer_perfil)
    almacen.interactuar(a, b.id, "like")
    almacen.interactuar(b, a.id, "superfan")
    # Par ordenado: (A,B) y (B,A) son la misma fila.
    assert almacen.con.execute("SELECT COUNT(*) c FROM matches").fetchone()["c"] == 1


def test_pass_no_hace_match(almacen, hacer_perfil):
    a = alta(almacen, hacer_perfil)
    b = alta(almacen, hacer_perfil)
    almacen.interactuar(a, b.id, "pass")
    assert almacen.interactuar(b, a.id, "like")["match"] is False


def test_no_se_puede_interactuar_dos_veces_ni_consigo_mismo(almacen, hacer_perfil):
    a = alta(almacen, hacer_perfil)
    b = alta(almacen, hacer_perfil)
    almacen.interactuar(a, b.id, "like")
    with pytest.raises(DatosInvalidos, match="ya interactuaste"):
        almacen.interactuar(a, b.id, "pass")
    with pytest.raises(DatosInvalidos, match="tu propio perfil"):
        almacen.interactuar(a, a.id, "like")


def test_cupo_de_likes_del_plan_gratis(almacen, hacer_perfil):
    yo = alta(almacen, hacer_perfil, preferencias=Preferencias(generos=[]))
    tope = planes.PLANES["gratis"].limites.likes_por_dia
    otros = [alta(almacen, hacer_perfil) for _ in range(tope + 1)]
    for o in otros[:tope]:
        almacen.interactuar(yo, o.id, "like")
    assert almacen.cupos(yo)["likes_restantes"] == 0
    with pytest.raises(SinCupo) as e:
        almacen.interactuar(yo, otros[tope].id, "like")
    assert e.value.recurso == "likes"
    # El pass no consume cupo de likes: castigar el descarte llena el deck de
    # gente que el usuario no quiere ver.
    almacen.interactuar(yo, otros[tope].id, "pass")


def test_el_like_rechazado_por_cupo_no_queda_registrado(almacen, hacer_perfil):
    """Si se registra la interacción y después falla el cupo, el perfil queda
    quemado (no vuelve a aparecer) sin que el like haya existido."""
    yo = alta(almacen, hacer_perfil)
    tope = planes.PLANES["gratis"].limites.likes_por_dia
    otros = [alta(almacen, hacer_perfil) for _ in range(tope + 1)]
    for o in otros[:tope]:
        almacen.interactuar(yo, o.id, "like")
    victima = otros[tope]
    with pytest.raises(SinCupo):
        almacen.interactuar(yo, victima.id, "like")
    assert victima.id not in almacen.vistos_por(yo.id)
    assert almacen.perfil(victima.id).likes_recibidos == 0


def test_premium_no_tiene_tope_de_likes(almacen, hacer_perfil):
    yo = alta(
        almacen,
        hacer_perfil,
        plan="gold",
        plan_vence=datetime.utcnow() + timedelta(days=30),
    )
    assert almacen.cupos(yo)["likes_max"] is None
    assert almacen.cupos(yo)["likes_restantes"] is None


def test_plan_vencido_vuelve_a_los_limites_gratis(almacen, hacer_perfil):
    yo = alta(
        almacen,
        hacer_perfil,
        plan="gold",
        plan_vence=datetime.utcnow() - timedelta(days=1),
    )
    assert yo.es_premium is False
    cupos = almacen.cupos(yo)
    assert cupos["plan"] == "gratis"
    assert cupos["likes_max"] == planes.PLANES["gratis"].limites.likes_por_dia


def test_ver_quien_me_dio_like_es_pago(almacen, hacer_perfil):
    yo = alta(almacen, hacer_perfil)
    fans = [alta(almacen, hacer_perfil) for _ in range(3)]
    for f in fans:
        almacen.interactuar(f, yo.id, "like")

    gratis = almacen.quien_me_dio_like(yo)
    assert gratis["visible"] is False
    assert gratis["cantidad"] == 3
    # Lo importante: los perfiles NO viajan. Mandarlos y esconderlos con CSS
    # es la fuga clásica de este feature.
    assert gratis["perfiles"] == []

    yo.plan = "plus"
    yo.plan_vence = datetime.utcnow() + timedelta(days=30)
    almacen.guardar_perfil(yo)
    pago = almacen.quien_me_dio_like(yo)
    assert pago["visible"] is True
    assert len(pago["perfiles"]) == 3


def test_rebobinar_es_pago_y_devuelve_el_ultimo(almacen, hacer_perfil):
    yo = alta(almacen, hacer_perfil)
    otro = alta(almacen, hacer_perfil)
    almacen.interactuar(yo, otro.id, "pass")
    with pytest.raises(SinCupo):
        almacen.rebobinar(yo)

    yo.plan = "plus"
    yo.plan_vence = datetime.utcnow() + timedelta(days=30)
    almacen.guardar_perfil(yo)
    r = almacen.rebobinar(yo)
    assert r == {"deshecho": True, "perfil_id": otro.id}
    assert otro.id not in almacen.vistos_por(yo.id)


def test_deck_no_repite_ni_se_incluye_a_uno_mismo(almacen, hacer_perfil):
    yo = alta(almacen, hacer_perfil, preferencias=Preferencias(generos=[]))
    otros = [alta(almacen, hacer_perfil) for _ in range(5)]
    ids = [t["id"] for t in almacen.deck(yo)["tarjetas"]]
    assert yo.id not in ids
    assert len(ids) == len(set(ids)) == 5

    almacen.interactuar(yo, otros[0].id, "pass")
    assert otros[0].id not in [t["id"] for t in almacen.deck(yo)["tarjetas"]]


def test_el_deck_no_expone_el_email(almacen, hacer_perfil):
    yo = alta(almacen, hacer_perfil, preferencias=Preferencias(generos=[]))
    alta(almacen, hacer_perfil, email="secreto@test.local")
    for t in almacen.deck(yo)["tarjetas"]:
        assert "email" not in t


def test_ver_el_deck_suma_vistas(almacen, hacer_perfil):
    yo = alta(almacen, hacer_perfil, preferencias=Preferencias(generos=[]))
    otro = alta(almacen, hacer_perfil)
    assert almacen.perfil(otro.id).vistas_recibidas == 0
    almacen.deck(yo)
    assert almacen.perfil(otro.id).vistas_recibidas == 1


def test_chat_completo(almacen, hacer_perfil):
    a = alta(almacen, hacer_perfil)
    b = alta(almacen, hacer_perfil)
    almacen.interactuar(a, b.id, "like")
    r = almacen.interactuar(b, a.id, "like")
    mid = r["match_id"]

    almacen.enviar_mensaje(mid, a, "hola")
    almacen.enviar_mensaje(mid, b, "hola vos")
    conv = almacen.conversacion(mid, a)
    assert [m["texto"] for m in conv] == ["hola", "hola vos"]
    assert conv[0]["mio"] is True and conv[1]["mio"] is False
    # Leer marca como leídos los del otro.
    assert almacen.matches_de(a.id)[0]["sin_leer"] == 0

    with pytest.raises(DatosInvalidos, match="vacío"):
        almacen.enviar_mensaje(mid, a, "   ")


def test_no_se_puede_espiar_un_chat_ajeno(almacen, hacer_perfil):
    a = alta(almacen, hacer_perfil)
    b = alta(almacen, hacer_perfil)
    intruso = alta(almacen, hacer_perfil)
    almacen.interactuar(a, b.id, "like")
    mid = almacen.interactuar(b, a.id, "like")["match_id"]
    with pytest.raises(DatosInvalidos, match="no es tuyo"):
        almacen.conversacion(mid, intruso)
    with pytest.raises(DatosInvalidos, match="no es tuyo"):
        almacen.enviar_mensaje(mid, intruso, "hola")


def test_deshacer_match_borra_los_mensajes(almacen, hacer_perfil):
    a = alta(almacen, hacer_perfil)
    b = alta(almacen, hacer_perfil)
    almacen.interactuar(a, b.id, "like")
    mid = almacen.interactuar(b, a.id, "like")["match_id"]
    almacen.enviar_mensaje(mid, a, "hola")
    almacen.deshacer_match(mid, b)
    assert almacen.matches_de(a.id) == []
    assert almacen.con.execute("SELECT COUNT(*) c FROM mensajes").fetchone()["c"] == 0


def test_reportar_tambien_descarta(almacen, hacer_perfil):
    yo = alta(almacen, hacer_perfil, preferencias=Preferencias(generos=[]))
    malo = alta(almacen, hacer_perfil)
    almacen.reportar(yo, malo.id, "spam", "manda links")
    assert malo.id not in [t["id"] for t in almacen.deck(yo)["tarjetas"]]


def test_baja_logica_saca_del_deck_pero_no_rompe_el_chat(almacen, hacer_perfil):
    a = alta(almacen, hacer_perfil, preferencias=Preferencias(generos=[]))
    b = alta(almacen, hacer_perfil)
    almacen.interactuar(a, b.id, "like")
    almacen.interactuar(b, a.id, "like")
    b.activo = False
    almacen.guardar_perfil(b)
    assert almacen.matches_de(a.id) == []       # no se lista
    assert almacen.perfil(b.id) is not None      # pero la fila sigue ahí


# ---------------------------------------------------------------------------
# Regresión: campos que se perdían en cada guardado
# ---------------------------------------------------------------------------
# El perfil se guarda serializado como un JSON en una columna. `intenciones` y
# `disponible_hasta` no estaban en ese JSON, así que se perdían en CADA
# guardado, en silencio y sin error: "qué buscás" no sobrevivía a editar el
# perfil, y "disponible hoy" no funcionó nunca — el endpoint respondía 200 y a
# la lectura siguiente el perfil volvía a figurar como no disponible.
#
# El test recorre TODOS los campos del dataclass en vez de listar unos pocos:
# el bug fue justamente que alguien agregó campos al modelo y se olvidó de la
# serialización, así que un test que enumera a mano se olvidaría igual.
def test_ningun_campo_del_perfil_se_pierde_al_guardar(almacen, hacer_perfil):
    from dataclasses import fields

    p = hacer_perfil(id="completo", email="completo@test.local")
    p.intenciones = ["relacion_formal", "amistad"]
    p.marcar_disponible()
    p.bio = "Probando el ida y vuelta"
    p.intereses = ["cine", "programar"]
    almacen.crear_perfil(p, "clave-larga-1")
    almacen.guardar_perfil(p)

    vuelto = almacen.perfil(p.id)
    # `clave_hash` no vive en el dataclass y `nacimiento` es date: se comparan
    # igual porque el ida y vuelta tiene que devolver exactamente lo mismo.
    for campo in fields(p):
        assert getattr(vuelto, campo.name) == getattr(p, campo.name), (
            f"el campo '{campo.name}' no sobrevivió al guardado"
        )


def test_disponible_hoy_sobrevive_al_guardado(almacen, hacer_perfil):
    """El caso puntual que rompía la vitrina de disponibles."""
    p = hacer_perfil(id="disp", email="disp@test.local")
    almacen.crear_perfil(p, "clave-larga-1")
    p.marcar_disponible()
    almacen.guardar_perfil(p)

    vuelto = almacen.perfil(p.id)
    assert vuelto.disponible_hoy is True
    assert "disponible_hoy" in vuelto.intenciones_vigentes
