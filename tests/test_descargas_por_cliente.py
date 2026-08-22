"""Qué bajó cada cliente, y qué obtiene por lo que paga.

EL PEDIDO Y LA REALIDAD

El pedido del dueño fue "que cada cliente descargue exactamente la versión que
paga". La parte que SÍ se puede cumplir —y es la que estos tests fijan— es que
cada descarga quede atribuida a una cuenta, con el plan que esa cuenta tenía en
ese momento, y que eso se vea cliente por cliente en el panel.

La parte que NO se puede cumplir como suena, y por qué está bien que no:
**el archivo es el mismo para todos**. Un binario no puede hacer cumplir un
plan. Se lo parchea con un editor hexadecimal, o directamente se pasa el link
por WhatsApp y lo baja alguien que no pagó nada. Un `.exe` "de Gold" sería una
promesa que el archivo no puede sostener — y sostenerla en el cliente es
exactamente el agujero que ya se tapó una vez en los pagos (regla 14).

Lo que cambia según lo que cada uno paga lo decide el SERVIDOR al entrar. Eso
es lo que hace que el plan valga igual en la web, en el APK y en el `.exe`, y
que no haya nada que parchear. Hay un test acá que lo fija.

NOTA SOBRE LOS NÚMEROS: varios tests miden el DELTA y no el valor absoluto. El
fixture `cliente` siembra la demo, que trae sus propias cuentas en Gold; lo que
se prueba es la propiedad, y así el test no se rompe el día que la demo siembre
una cuenta más.
"""

from __future__ import annotations

from datetime import date

import pytest

from matcher import panel
from matcher.modelos import Perfil, Preferencias

ALTA = {
    "clave": "clave-larga-12345", "nacimiento": "1990-01-01", "genero": "mujer",
    "altura_cm": 170, "pais": "UY", "ciudad": "UY-MVD",
    "preferencias": {"generos": [], "edad_min": 18, "edad_max": 99},
}


@pytest.fixture
def urls(monkeypatch):
    monkeypatch.setenv("MATCHER_URL_EXE", "https://ejemplo.test/Matcher.exe")
    monkeypatch.setenv("MATCHER_URL_APK", "https://ejemplo.test/matcher.apk")


def cuenta(cliente, email, nombre="Alguien") -> dict:
    r = cliente.post("/api/registro", json={**ALTA, "email": email, "nombre": nombre})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def duenio(cliente, monkeypatch, email="jefa@test.local") -> dict:
    monkeypatch.setenv("MATCHER_CUENTAS_DUENIO", email)
    cab = cuenta(cliente, email, "Jefa")
    cliente.post("/api/login", json={"email": email, "clave": ALTA["clave"]})
    return cab


# ---------------------------------------------------------------------------
# La descarga queda atribuida
# ---------------------------------------------------------------------------
def test_la_descarga_pide_cuenta(cliente, urls):
    """Sin sesión no se puede atribuir a nadie: quedaba un contador y nada más.
    Registrarse es gratis, así que esto no le cierra la puerta a ningún
    cliente."""
    assert cliente.get("/api/descargar/exe", follow_redirects=False).status_code == 401


def test_se_registra_quien_bajo_y_con_que_plan(cliente, urls, monkeypatch):
    cab = cuenta(cliente, "ana@test.local", "Ana")
    r = cliente.get("/api/descargar/exe", headers=cab, follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "https://ejemplo.test/Matcher.exe"

    cabd = duenio(cliente, monkeypatch)
    fila = [c for c in cliente.get("/api/panel/clientes", headers=cabd).json()["clientes"]
            if c["email"] == "ana@test.local"][0]
    assert fila["descargas"], "la descarga no quedó atribuida a la cuenta"
    assert fila["descargas"][0]["plataforma"] == "exe"
    assert fila["descargas"][0]["plan"] == "gratis"


def test_el_plan_de_la_descarga_queda_congelado(almacen):
    """ES EL DATO QUE IMPORTA. Si el plan se leyera del perfil al mirar el
    panel, un cliente que hoy es Gold figuraría como si siempre lo hubiera
    sido, y se perdería justo lo interesante: que bajó el programa siendo
    gratis y pagó después."""
    p = Perfil(
        id="u1", email="ana@test.local", nombre="Ana", nacimiento=date(1990, 1, 1),
        genero="mujer", altura_cm=170, pais="UY", ciudad="UY-MVD",
        preferencias=Preferencias(),
    )
    almacen.crear_perfil(p, "clave-larga-12345")

    panel.registrar_descarga(almacen, "exe", perfil=p)   # bajó siendo gratis
    p.plan = "gold"
    almacen.guardar_perfil(p)

    bajada = panel.clientes(almacen)[0]["descargas"][0]
    assert bajada["plan"] == "gratis", (
        "el plan de la descarga se lee del perfil actual, no del momento"
    )


def test_el_panel_muestra_las_descargas_por_plan(cliente, urls, monkeypatch):
    cab = cuenta(cliente, "ana@test.local", "Ana")
    cliente.get("/api/descargar/exe", headers=cab, follow_redirects=False)
    cliente.get("/api/descargar/apk", headers=cab, follow_redirects=False)

    cabd = duenio(cliente, monkeypatch)
    d = cliente.get("/api/panel", headers=cabd).json()["descargas"]
    assert d["por_plan"]["gratis"] >= 2
    assert d["por_plataforma"]["exe"] >= 1 and d["por_plataforma"]["apk"] >= 1


# ---------------------------------------------------------------------------
# La lista de clientes es del dueño y sólo del dueño
# ---------------------------------------------------------------------------
def test_la_lista_de_clientes_no_es_para_los_clientes(cliente, monkeypatch):
    """Son emails y planes de gente real. 404 y no 403, igual que el resto del
    panel: un 403 le confirma al que prueba que hay algo que atacar."""
    monkeypatch.delenv("MATCHER_CUENTAS_DUENIO", raising=False)
    cab = cuenta(cliente, "curiosa@test.local", "Curiosa")
    assert cliente.get("/api/panel/clientes").status_code == 401
    assert cliente.get("/api/panel/clientes", headers=cab).status_code == 404


def test_la_lista_no_expone_el_perfil_entero(cliente, monkeypatch):
    """Es la vista comercial, no una ventana a la cuenta de la gente. Un panel
    de administración que muestra el perfil completo es la forma más común de
    que un dato personal termine donde no va."""
    cuenta(cliente, "ana@test.local", "Ana")
    cabd = duenio(cliente, monkeypatch)
    fila = cliente.get("/api/panel/clientes", headers=cabd).json()["clientes"][0]
    for prohibido in ("clave", "clave_hash", "bio", "fotos", "lat", "lon", "ubicacion"):
        assert prohibido not in fila, f"la lista de clientes expone `{prohibido}`"


def test_los_perfiles_sinteticos_no_son_clientes(almacen):
    """Mezclarlos convierte la lista en un número inventado. La demo siembra
    decenas de perfiles sintéticos y 2 cuentas del dueño: los sintéticos no son
    clientes, las 2 sí son cuentas de verdad y tienen que estar."""
    from matcher import demo

    demo.poblar(almacen)
    lista = panel.clientes(almacen)
    sinteticos = almacen.con.execute(
        "SELECT COUNT(*) c FROM perfiles WHERE datos LIKE '%\"sintetico\": true%'"
    ).fetchone()["c"]
    assert sinteticos > 0, "la demo no sembró nada; el test no está probando nada"
    assert len(lista) == 2, f"se colaron perfiles de la demo: {len(lista)} clientes"


# ---------------------------------------------------------------------------
# Lo que el binario NO hace
# ---------------------------------------------------------------------------
def test_el_archivo_es_el_mismo_para_todos(cliente, urls, monkeypatch):
    """Un binario no puede hacer cumplir un plan: se lo parchea, o se pasa el
    link. Si algún día alguien hace que la URL cambie según el plan, este test
    se pone en rojo — y hay que leer el encabezado de este archivo antes de
    tocarlo."""
    gratis = cuenta(cliente, "gratis@test.local", "Gra")
    monkeypatch.setenv("MATCHER_CUENTAS_DUENIO", "gold@test.local")
    gold = cuenta(cliente, "gold@test.local", "Gol")
    cliente.post("/api/login", json={"email": "gold@test.local", "clave": ALTA["clave"]})

    a = cliente.get("/api/descargar/exe", headers=gratis, follow_redirects=False)
    b = cliente.get("/api/descargar/exe", headers=gold, follow_redirects=False)
    assert a.headers["location"] == b.headers["location"]


def test_el_plan_lo_decide_el_servidor_no_el_programa(cliente, monkeypatch):
    """La contracara del test de arriba: si el archivo es el mismo, lo que hace
    la diferencia tiene que venir del servidor al entrar. La cuenta del dueño
    entra en Gold sin tocar el binario, en cualquier plataforma."""
    monkeypatch.setenv("MATCHER_CUENTAS_DUENIO", "jefa@test.local")
    cuenta(cliente, "jefa@test.local", "Jefa")
    r = cliente.post("/api/login", json={"email": "jefa@test.local", "clave": ALTA["clave"]})
    assert r.json()["perfil"]["plan"] == "gold"


# ---------------------------------------------------------------------------
# El contador de "clientes que pagan" tiene que ser el de los que pagan
# ---------------------------------------------------------------------------
def test_las_cuentas_del_duenio_no_cuentan_como_clientes_que_pagan(cliente, monkeypatch):
    """LO PEOR QUE PUEDE HACER UN PANEL ES MENTIR EN EL NÚMERO QUE UNO MIRA.

    Las cuentas de `MATCHER_CUENTAS_DUENIO` están en Gold porque `duenio.py`
    se las pone, no porque hayan pagado. Contándolas, una base recién estrenada
    mostraba "Pagando: 2 · 66,67% de conversión" al lado de "Facturado: USD 0"
    — dos números que se contradicen en la misma pantalla, y el que uno usa
    para decidir si el negocio funciona era el equivocado.
    """
    cab = duenio(cliente, monkeypatch, "jefa@test.local")
    antes = cliente.get("/api/panel", headers=cab).json()

    monkeypatch.setenv("MATCHER_CUENTAS_DUENIO", "jefa@test.local,segunda@test.local")
    cuenta(cliente, "segunda@test.local", "Segunda")
    cliente.post("/api/login", json={"email": "segunda@test.local", "clave": ALTA["clave"]})

    despues = cliente.get("/api/panel", headers=cab).json()
    assert despues["pagando"] == antes["pagando"], (
        "sumar una cuenta del dueño subió el contador de clientes que pagan"
    )
    assert despues["dinero"]["bruto"] == antes["dinero"]["bruto"] == 0, (
        "apareció plata que nadie pagó"
    )
    # Y se dice cuántas se sacaron, en vez de esconderlas.
    assert despues["planes"]["del_duenio"] == 2


def test_un_cliente_que_paga_de_verdad_si_cuenta(cliente, monkeypatch):
    """La contracara: sacar las del dueño no puede tapar a un cliente real."""
    cab_cliente = cuenta(cliente, "paga@test.local", "Paga")
    ch = cliente.post(
        "/api/pagos/checkout", json={"plan": "gold", "periodo": "mensual"},
        headers=cab_cliente,
    ).json()["checkout"]
    # Pasarela `demo`: `esta_pagado` da True siempre porque no mueve plata. Con
    # MercadoPago o PayPal acá manda el proveedor (regla 14).
    r = cliente.post(
        "/api/pagos/confirmar", json={"referencia": ch["id"]}, headers=cab_cliente
    )
    assert r.status_code == 200, r.text

    cab = duenio(cliente, monkeypatch, "jefa@test.local")
    panel_ = cliente.get("/api/panel", headers=cab).json()
    assert panel_["pagando"] >= 1, "el cliente que pagó no aparece"
    assert panel_["dinero"]["bruto"] > 0, "pagó y la facturación quedó en cero"
    assert panel_["dinero"]["cobros"] == 1
