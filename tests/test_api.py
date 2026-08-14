"""La API de punta a punta, sobre una base en memoria.

Se prueba el contrato HTTP (códigos, forma de la respuesta, autorización), no
la lógica: esa ya tiene sus tests en los módulos del motor.
"""

import pytest
from fastapi.testclient import TestClient

from matcher import demo
from matcher.almacen import Almacen
from webapp.backend import api as backend


@pytest.fixture
def cliente(monkeypatch):
    a = Almacen(":memory:")
    demo.poblar(a, cantidad=40)
    monkeypatch.setattr(backend, "_almacen", a)
    monkeypatch.setattr(backend, "POBLAR_DEMO", False)
    with TestClient(backend.app) as c:
        yield c
    a.cerrar()


def entrar(cliente, email="vieraschiavi@gmail.com"):
    r = cliente.post("/api/login", json={"email": email, "clave": demo.CLAVE_DEMO})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_salud_y_catalogos(cliente):
    assert cliente.get("/api/salud").json()["ok"] is True
    c = cliente.get("/api/catalogos").json()
    assert len(c["paises"]) >= 15
    assert c["limites"] == {"fotos": 10, "videos": 2, "segundos_video": 30}
    uy = next(p for p in c["paises"] if p["codigo"] == "UY")
    assert "Peñarol" in uy["equipos"]
    assert uy["ciudades"]


def test_login_malo_no_distingue_email_de_clave(cliente):
    a = cliente.post("/api/login", json={"email": "nadie@x.test", "clave": "loquesea1"})
    b = cliente.post("/api/login", json={"email": "vieraschiavi@gmail.com", "clave": "malamala"})
    assert a.status_code == b.status_code == 401
    assert a.json()["detail"] == b.json()["detail"]


def test_las_rutas_privadas_piden_token(cliente):
    for ruta in ("/api/yo", "/api/deck", "/api/matches", "/api/likes-recibidos"):
        assert cliente.get(ruta).status_code == 401


def test_yo_devuelve_perfil_privado_y_cupos(cliente):
    h = entrar(cliente)
    r = cliente.get("/api/yo", headers=h).json()
    assert r["perfil"]["email"] == "vieraschiavi@gmail.com"
    assert r["perfil"]["preferencias"]["busca"] == "todos"
    assert r["cupos"]["likes_max"] is None       # gold
    assert r["medios"]["fotos_max"] == 10
    assert r["medios"]["tiene_portada"] is True


def test_deck_no_filtra_el_email_en_el_cliente(cliente):
    h = entrar(cliente)
    r = cliente.get("/api/deck?limite=5", headers=h).json()
    assert len(r["tarjetas"]) > 0
    for t in r["tarjetas"]:
        assert "email" not in t
        assert "compatibilidad" in t and "fotos" in t


def test_registro_y_flujo_de_like(cliente):
    alta = cliente.post(
        "/api/registro",
        json={
            "email": "nueva@test.local",
            "clave": "clave-larga-1",
            "nombre": "Nueva",
            "nacimiento": "1996-05-20",
            "genero": "mujer",
            "altura_cm": 168,
            "pais": "UY",
            "ciudad": "UY-MVD",
            "politica": "izquierda",
            "equipo": "Peñarol",
            "preferencias": {"busca": "todos", "edad_min": 18, "edad_max": 99},
        },
    )
    assert alta.status_code == 200, alta.text
    h = {"Authorization": f"Bearer {alta.json()['token']}"}

    # Sin foto no entra al deck de nadie, pero puede ver el suyo.
    cliente.post("/api/yo/fotos", json={"url": "https://x.test/a.jpg"}, headers=h)
    deck = cliente.get("/api/deck", headers=h).json()
    objetivo = deck["tarjetas"][0]["id"]
    r = cliente.post("/api/interacciones", json={"a_id": objetivo, "tipo": "like"}, headers=h)
    assert r.status_code == 200
    assert "match" in r.json()


def test_registro_rechaza_menor_de_edad(cliente):
    r = cliente.post(
        "/api/registro",
        json={
            "email": "menor@test.local",
            "clave": "clave-larga-1",
            "nombre": "Menor",
            "nacimiento": "2015-01-01",
            "genero": "mujer",
            "altura_cm": 160,
            "pais": "UY",
            "ciudad": "UY-MVD",
        },
    )
    assert r.status_code == 400
    assert "18" in r.json()["detail"]


def test_tope_de_fotos_devuelve_400(cliente):
    h = entrar(cliente)
    faltan = cliente.get("/api/yo", headers=h).json()["medios"]
    for i in range(faltan["fotos_max"] - faltan["fotos"]):
        r = cliente.post("/api/yo/fotos", json={"url": f"https://x.test/{i}.jpg"}, headers=h)
        assert r.status_code == 200, r.text
    assert cliente.get("/api/yo", headers=h).json()["medios"]["fotos"] == 10

    r = cliente.post("/api/yo/fotos", json={"url": "https://x.test/x.jpg"}, headers=h)
    assert r.status_code == 400
    assert "10 fotos" in r.json()["detail"]


def test_tope_de_videos_y_duracion(cliente):
    h = entrar(cliente)
    for i in range(2):
        r = cliente.post(
            "/api/yo/videos", json={"url": f"https://x.test/{i}.mp4", "segundos": 10}, headers=h
        )
        assert r.status_code == 200, r.text
    tercero = cliente.post(
        "/api/yo/videos", json={"url": "https://x.test/3.mp4", "segundos": 5}, headers=h
    )
    assert tercero.status_code == 400 and "2 videos" in tercero.json()["detail"]


def test_sin_cupo_devuelve_402_con_el_plan_sugerido(cliente, monkeypatch):
    """402 Payment Required, con el detalle de qué plan lo destraba: es el
    momento exacto donde se vende, así que el contrato tiene que ser estable."""
    a = backend.almacen()
    # Cuenta gratis nueva.
    r = cliente.post(
        "/api/registro",
        json={
            "email": "gratis@test.local",
            "clave": "clave-larga-1",
            "nombre": "Gratis",
            "nacimiento": "1994-03-03",
            "genero": "hombre",
            "altura_cm": 178,
            "pais": "UY",
            "ciudad": "UY-MVD",
            "preferencias": {"busca": "todos", "edad_min": 18, "edad_max": 99},
        },
    )
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    cliente.post("/api/yo/fotos", json={"url": "https://x.test/a.jpg"}, headers=h)
    yo = a.buscar_por_email("gratis@test.local")

    # Se agota el cupo de superfans (1 por semana en gratis).
    deck = cliente.get("/api/deck?limite=10", headers=h).json()["tarjetas"]
    cliente.post("/api/interacciones", json={"a_id": deck[0]["id"], "tipo": "superfan"}, headers=h)
    segunda = cliente.post(
        "/api/interacciones", json={"a_id": deck[1]["id"], "tipo": "superfan"}, headers=h
    )
    assert segunda.status_code == 402
    cuerpo = segunda.json()
    assert cuerpo["recurso"] == "superfans"
    assert cuerpo["plan_sugerido"] == "plus"
    assert yo is not None


def test_likes_recibidos_oculta_los_perfiles_en_gratis(cliente):
    r = cliente.post(
        "/api/registro",
        json={
            "email": "mirada@test.local",
            "clave": "clave-larga-1",
            "nombre": "Mirada",
            "nacimiento": "1993-02-02",
            "genero": "mujer",
            "altura_cm": 165,
            "pais": "UY",
            "ciudad": "UY-MVD",
            "preferencias": {"busca": "todos", "edad_min": 18, "edad_max": 99},
        },
    )
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    a = backend.almacen()
    yo = a.buscar_por_email("mirada@test.local")
    fan = next(p for p in a.todos() if p.sintetico)
    a.interactuar(fan, yo.id, "like")

    datos = cliente.get("/api/likes-recibidos", headers=h).json()
    assert datos["visible"] is False
    assert datos["cantidad"] == 1
    assert datos["perfiles"] == []


def test_filtros_se_guardan_y_achican_el_deck(cliente):
    h = entrar(cliente)
    antes = len(cliente.get("/api/deck?limite=50", headers=h).json()["tarjetas"])
    r = cliente.patch(
        "/api/yo",
        json={"preferencias": {"busca": "todos", "edad_min": 18, "edad_max": 99,
                               "equipos": ["Peñarol"]}},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["perfil"]["preferencias"]["equipos"] == ["Peñarol"]
    despues = cliente.get("/api/deck?limite=50", headers=h).json()
    assert len(despues["tarjetas"]) < antes
    for t in despues["tarjetas"]:
        assert t["equipo"] == "Peñarol"


def test_deck_vacio_trae_diagnostico(cliente):
    h = entrar(cliente)
    cliente.patch(
        "/api/yo",
        json={
            "preferencias": {
                "busca": "todos",
                "edad_min": 18,
                "edad_max": 19,
                "altura_min_cm": 225,
                "politicas": ["izquierda"],
            }
        },
        headers=h,
    )
    r = cliente.get("/api/deck", headers=h).json()
    assert r["tarjetas"] == []
    assert r["diagnostico"], "el deck vacío tiene que explicar por qué"


def test_chat_ajeno_da_400(cliente):
    h1 = entrar(cliente, "vieraschiavi@gmail.com")
    h2 = entrar(cliente, "arcortito@gmail.com")
    cliente.post("/api/automatch", headers=h1)
    matches = cliente.get("/api/matches", headers=h1).json()["matches"]
    if not matches:
        pytest.skip("sin matches automáticos en esta semilla")
    mid = matches[0]["id"]
    assert cliente.get(f"/api/matches/{mid}/mensajes", headers=h1).status_code == 200
    ajeno = cliente.get(f"/api/matches/{mid}/mensajes", headers=h2)
    assert ajeno.status_code == 400


def test_pago_completo_por_http(cliente):
    r = cliente.post(
        "/api/registro",
        json={
            "email": "paga@test.local",
            "clave": "clave-larga-1",
            "nombre": "Paga",
            "nacimiento": "1990-06-06",
            "genero": "hombre",
            "altura_cm": 180,
            "pais": "UY",
            "ciudad": "UY-MVD",
        },
    )
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    assert r.json()["perfil"]["plan"] == "gratis"

    checkout = cliente.post("/api/pagos/checkout", json={"plan": "plus", "periodo": "anual"},
                            headers=h).json()["checkout"]
    assert checkout["monto"] == 29.90
    assert checkout["pasarela"] == "demo"

    conf = cliente.post("/api/pagos/confirmar", json={"referencia": checkout["id"]}, headers=h)
    assert conf.status_code == 200
    assert conf.json()["perfil"]["plan"] == "plus"
    assert conf.json()["perfil"]["es_premium"] is True

    historial = cliente.get("/api/pagos", headers=h).json()["pagos"]
    assert historial[0]["estado"] == "pagado"


def test_planes_expone_precios_y_el_aviso_de_referencia(cliente):
    r = cliente.get("/api/planes").json()
    codigos = [p["codigo"] for p in r["planes"]]
    assert codigos == ["gratis", "plus", "gold"]
    assert r["referencia_competencia"]
    assert "verificalos" in r["aviso_referencia"].lower()


def test_ranking_es_publico(cliente):
    r = cliente.get("/api/ranking?limite=5")
    assert r.status_code == 200
    top = r.json()["top"]
    assert len(top) == 5
    assert top == sorted(top, key=lambda x: -x["popularidad"])
