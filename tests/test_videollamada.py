"""Videollamada dentro del match.

Lo que estos tests protegen, en orden de gravedad si se rompe:

1. El link NO viaja mientras la propuesta está pendiente (consentimiento de
   los dos, no de uno).
2. Una cita a ciegas sin revelar no puede tener videollamada: sería entregar
   por cámara la cara que el feature entero se cuida de no mandar.
3. Un link pegado tiene que ser del dominio del proveedor: si no, la app
   presta su sello a cualquier URL.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from matcher import aciegas, videollamada
from matcher.modelos import DatosInvalidos, Preferencias
from tests.conftest import entrar


@pytest.fixture
def par(almacen, hacer_perfil):
    """Dos perfiles con match hecho."""
    a = hacer_perfil(id="uno", email="uno@test.local", genero="mujer")
    b = hacer_perfil(id="dos", email="dos@test.local", genero="hombre")
    for p in (a, b):
        p.preferencias = Preferencias(generos=[], edad_min=18, edad_max=99)
        almacen.crear_perfil(p, "clave-larga-1")
    almacen.interactuar(a, b.id, "like")
    almacen.interactuar(b, a.id, "like")
    m = almacen.matches_de(a.id)[0]
    return a, b, m["id"]


# ---------------------------------------------------------------------------
# Consentimiento de los dos
# ---------------------------------------------------------------------------
def test_el_enlace_no_viaja_hasta_que_el_otro_acepta(almacen, par):
    a, b, match_id = par
    prop = videollamada.proponer(almacen, a, match_id, "jitsi")

    assert prop["estado"] == videollamada.PENDIENTE
    assert prop["enlace"] is None, "el link salió del servidor antes de que el otro aceptara"

    # Tampoco lo ve el que la propuso: si lo viera, lo copia al chat y el
    # consentimiento del otro pasa a ser decorativo.
    assert videollamada.estado(almacen, a, match_id)["llamada"]["enlace"] is None
    assert videollamada.estado(almacen, b, match_id)["llamada"]["enlace"] is None

    acept = videollamada.responder(almacen, b, prop["id"], acepta=True)
    assert acept["estado"] == videollamada.ACEPTADA
    assert acept["enlace"].startswith("https://meet.jit.si/matcher-")
    assert videollamada.estado(almacen, a, match_id)["llamada"]["enlace"] == acept["enlace"]


def test_rechazada_tampoco_muestra_el_enlace(almacen, par):
    a, b, match_id = par
    prop = videollamada.proponer(almacen, a, match_id, "jitsi")
    r = videollamada.responder(almacen, b, prop["id"], acepta=False)
    assert r["estado"] == videollamada.RECHAZADA
    assert r["enlace"] is None
    # Y el chat vuelve a quedar libre para proponer otra.
    assert videollamada.estado(almacen, a, match_id)["llamada"] is None


def test_nadie_acepta_su_propia_propuesta(almacen, par):
    a, _b, match_id = par
    prop = videollamada.proponer(almacen, a, match_id, "jitsi")
    with pytest.raises(DatosInvalidos, match="la otra persona"):
        videollamada.responder(almacen, a, prop["id"], acepta=True)


def test_un_tercero_no_puede_tocar_la_llamada(almacen, par, hacer_perfil):
    a, _b, match_id = par
    intruso = hacer_perfil(id="tres", email="tres@test.local")
    almacen.crear_perfil(intruso, "clave-larga-1")
    prop = videollamada.proponer(almacen, a, match_id, "jitsi")

    for accion in (
        lambda: videollamada.responder(almacen, intruso, prop["id"], acepta=True),
        lambda: videollamada.cancelar(almacen, intruso, prop["id"]),
        lambda: videollamada.estado(almacen, intruso, match_id),
    ):
        with pytest.raises(DatosInvalidos):
            accion()


def test_cualquiera_de_los_dos_puede_cancelar_ya_aceptada(almacen, par):
    """Arrepentirse después de decir que sí tiene que ser posible sin tener
    que deshacer el match entero."""
    a, b, match_id = par
    prop = videollamada.proponer(almacen, a, match_id, "jitsi")
    videollamada.responder(almacen, b, prop["id"], acepta=True)

    cancelada = videollamada.cancelar(almacen, b, prop["id"])
    assert cancelada["estado"] == videollamada.CANCELADA
    assert cancelada["enlace"] is None, "el link sigue viajando después de cancelar"


def test_una_propuesta_por_chat(almacen, par):
    a, _b, match_id = par
    videollamada.proponer(almacen, a, match_id, "jitsi")
    with pytest.raises(DatosInvalidos, match="ya hay una videollamada"):
        videollamada.proponer(almacen, a, match_id, "jitsi")


def test_la_propuesta_sin_responder_vence_y_desbloquea(almacen, par):
    """Sin vencimiento, un "sí" que nunca llega deja el chat sin poder
    proponer nunca más."""
    a, b, match_id = par
    viejo = datetime.utcnow() - videollamada.VIDA_PROPUESTA - timedelta(minutes=1)
    prop = videollamada.proponer(almacen, a, match_id, "jitsi", ahora=viejo)

    assert videollamada.estado(almacen, a, match_id)["llamada"] is None
    with pytest.raises(DatosInvalidos, match="venció"):
        videollamada.responder(almacen, b, prop["id"], acepta=True)
    assert videollamada.proponer(almacen, a, match_id, "jitsi")["estado"] == "pendiente"


# ---------------------------------------------------------------------------
# Cita a ciegas
# ---------------------------------------------------------------------------
def test_una_cita_a_ciegas_sin_revelar_no_tiene_videollamada(almacen, par):
    a, b, _ = par
    almacen.con.execute("UPDATE matches SET ciego = 1")
    almacen.con.commit()
    match_id = almacen.matches_de(a.id)[0]["id"]

    est = videollamada.estado(almacen, a, match_id)
    assert est["disponible"] is False
    assert "cita a ciegas" in est["motivo"]
    with pytest.raises(DatosInvalidos, match="cita a ciegas"):
        videollamada.proponer(almacen, a, match_id, "jitsi")

    # Al revelarse (cada uno escribió lo suyo), se destraba.
    for _ in range(aciegas.UMBRAL):
        almacen.enviar_mensaje(match_id, a, "hola")
        almacen.enviar_mensaje(match_id, b, "hola")
    assert videollamada.estado(almacen, a, match_id)["disponible"] is True
    assert videollamada.proponer(almacen, a, match_id, "jitsi")["estado"] == "pendiente"


# ---------------------------------------------------------------------------
# Proveedores y links
# ---------------------------------------------------------------------------
def test_el_catalogo_dice_la_verdad_de_cada_proveedor(almacen):
    """Regla 10: sólo Jitsi puede crear la sala sin cuenta de nadie. Meet,
    Zoom y Webex necesitan las APIs de sus dueños, así que la app pide el link
    en vez de prometer una sala que no puede crear."""
    cat = {p["codigo"]: p for p in videollamada.catalogo()}
    assert cat["jitsi"]["crea_sala"] is True
    for codigo in ("meet", "zoom", "webex"):
        assert cat[codigo]["crea_sala"] is False, (
            f"{codigo} dice que crea la sala solo, y la app no puede hacerlo"
        )
        assert "pegá" in cat[codigo]["nota"].lower()


def test_los_proveedores_sin_sala_propia_exigen_link(almacen, par):
    a, _b, match_id = par
    with pytest.raises(DatosInvalidos, match="falta el link"):
        videollamada.proponer(almacen, a, match_id, "meet")


@pytest.mark.parametrize(
    "proveedor,enlace",
    [
        ("meet", "https://meet.google.com/abc-defg-hij"),
        ("zoom", "https://us02web.zoom.us/j/8412345678"),
        ("webex", "https://empresa.webex.com/meet/alguien"),
    ],
)
def test_un_link_del_dominio_correcto_pasa(almacen, par, proveedor, enlace):
    a, b, match_id = par
    prop = videollamada.proponer(almacen, a, match_id, proveedor, enlace=enlace)
    assert videollamada.responder(almacen, b, prop["id"], acepta=True)["enlace"] == enlace


@pytest.mark.parametrize(
    "enlace",
    [
        "http://meet.google.com/abc",           # sin https
        "https://meet.google.com.trucho.net/x",  # el clásico: sufijo pegado
        "https://meetgoogle.com/abc",            # parecido, no es
        "https://zoom.us/j/1",                   # de otro proveedor
        "javascript:alert(1)",
        "",
    ],
)
def test_un_link_que_no_es_del_proveedor_se_rechaza(almacen, par, enlace):
    a, _b, match_id = par
    with pytest.raises(DatosInvalidos):
        videollamada.proponer(almacen, a, match_id, "meet", enlace=enlace)


def test_dos_salas_de_jitsi_nunca_son_iguales(almacen, par, hacer_perfil):
    """La sala de Jitsi sin cuenta la abre cualquiera que sepa el nombre: si
    fuera derivable del match, un tercero entraría a la cita."""
    a, b, match_id = par
    p1 = videollamada.proponer(almacen, a, match_id, "jitsi")
    e1 = videollamada.responder(almacen, b, p1["id"], acepta=True)["enlace"]
    videollamada.cancelar(almacen, a, p1["id"])
    p2 = videollamada.proponer(almacen, a, match_id, "jitsi")
    e2 = videollamada.responder(almacen, b, p2["id"], acepta=True)["enlace"]

    assert e1 != e2
    assert len(e1.rsplit("/", 1)[-1]) >= 20, "nombre de sala corto = adivinable"
    for parte in (match_id, a.id, b.id):
        assert parte not in e1, "el nombre de la sala se deduce de los ids"


def test_proveedor_inventado(almacen, par):
    a, _b, match_id = par
    with pytest.raises(DatosInvalidos, match="proveedor desconocido"):
        videollamada.proponer(almacen, a, match_id, "skype")


# ---------------------------------------------------------------------------
# Se cae con el match
# ---------------------------------------------------------------------------
def test_deshacer_el_match_borra_la_videollamada(almacen, par):
    a, b, match_id = par
    prop = videollamada.proponer(almacen, a, match_id, "jitsi")
    videollamada.responder(almacen, b, prop["id"], acepta=True)

    almacen.deshacer_match(match_id, a)
    quedan = almacen.con.execute(
        "SELECT COUNT(*) c FROM videollamadas WHERE match_id = ?", (match_id,)
    ).fetchone()["c"]
    assert quedan == 0, "quedó viva una sala de un match que ya no existe"


def test_borrar_la_cuenta_se_lleva_las_videollamadas(almacen, par):
    a, b, match_id = par
    prop = videollamada.proponer(almacen, a, match_id, "jitsi")
    videollamada.responder(almacen, b, prop["id"], acepta=True)

    almacen.borrar_cuenta(a)
    quedan = almacen.con.execute("SELECT COUNT(*) c FROM videollamadas").fetchone()["c"]
    assert quedan == 0


# ---------------------------------------------------------------------------
# Por HTTP
# ---------------------------------------------------------------------------
def _match_por_http(cliente, cabeceras):
    """Un match de verdad, dándole like a alguien que ya me dio like."""
    from webapp.backend import api as backend

    a = backend._almacen
    yo = a.perfil(cliente.get("/api/yo", headers=cabeceras).json()["perfil"]["id"])
    otro = next(
        o for o in a.todos()
        if o.id != yo.id and o.completo and o.activo
    )
    a.interactuar(otro, yo.id, "like")
    cliente.post("/api/interacciones", json={"a_id": otro.id, "tipo": "like"},
                 headers=cabeceras)
    matches = cliente.get("/api/matches", headers=cabeceras).json()["matches"]
    return next(m for m in matches if m["con"]["id"] == otro.id)["id"], otro


def test_el_ciclo_completo_por_http(cliente):
    cabeceras = entrar(cliente)
    match_id, otro = _match_por_http(cliente, cabeceras)

    r = cliente.get(f"/api/matches/{match_id}/videollamada", headers=cabeceras)
    assert r.status_code == 200, r.text
    assert r.json()["llamada"] is None
    assert any(p["crea_sala"] for p in r.json()["proveedores"])

    r = cliente.post(
        f"/api/matches/{match_id}/videollamada",
        json={"proveedor": "jitsi", "cuando": "hoy 21:00"},
        headers=cabeceras,
    )
    assert r.status_code == 200, r.text
    llamada = r.json()["llamada"]
    assert llamada["enlace"] is None and llamada["cuando"] == "hoy 21:00"

    # El JSON crudo tampoco puede traer el link escondido en otro campo: si el
    # payload lo lleva, el "inspeccionar elemento" lo encuentra igual.
    assert "jit.si" not in r.text, "el link viajó en el payload de una propuesta pendiente"

    r = cliente.delete(f"/api/videollamadas/{llamada['id']}", headers=cabeceras)
    assert r.status_code == 200 and r.json()["llamada"]["estado"] == "cancelada"


def test_por_http_el_match_de_otro_no_se_toca(cliente):
    cabeceras = entrar(cliente)
    r = cliente.get("/api/matches/inventado/videollamada", headers=cabeceras)
    assert r.status_code == 400
