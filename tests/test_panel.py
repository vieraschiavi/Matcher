"""El panel del dueño y el conteo de descargas.

Dos cosas que este archivo protege:

1. **Que el panel no lo vea nadie más.** Son los números del negocio: cuánta
   plata entró, cuántos clientes hay. Una fuga acá no rompe la app, le entrega
   la contabilidad a la competencia.
2. **Que los números sean los de verdad.** Un panel que cuenta mal es peor que
   no tener panel: se toman decisiones con él.
"""

from __future__ import annotations

from datetime import datetime

from matcher import panel
from matcher.modelos import Preferencias


def cuenta(cliente, email: str) -> dict:
    r = cliente.post(
        "/api/registro",
        json={
            "email": email, "clave": "clave-larga-12345", "nombre": "Alguien",
            "nacimiento": "1993-04-04", "genero": "mujer", "altura_cm": 170,
            "pais": "UY", "ciudad": "UY-MVD",
            "preferencias": {"generos": [], "edad_min": 18, "edad_max": 99},
        },
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


# ---------------------------------------------------------------------------
# Quién puede mirar
# ---------------------------------------------------------------------------
def test_un_usuario_comun_no_ve_el_panel(cliente, monkeypatch):
    monkeypatch.delenv("MATCHER_CUENTAS_DUENIO", raising=False)
    cab = cuenta(cliente, "curioso@test.local")
    r = cliente.get("/api/panel", headers=cab)
    assert r.status_code == 404, f"el panel se filtró con {r.status_code}"


def test_responde_404_y_no_403(cliente, monkeypatch):
    """Un 403 confirma que el panel existe. Con 404 es indistinguible de una
    ruta que no está: el que prueba no aprende nada."""
    monkeypatch.setenv("MATCHER_CUENTAS_DUENIO", "jefe@test.local")
    cab = cuenta(cliente, "otro@test.local")
    assert cliente.get("/api/panel", headers=cab).status_code == 404


def test_sin_sesion_tampoco(cliente):
    assert cliente.get("/api/panel").status_code == 401


def test_el_duenio_si_lo_ve(cliente, monkeypatch):
    monkeypatch.setenv("MATCHER_CUENTAS_DUENIO", "jefa@test.local")
    cab = cuenta(cliente, "jefa@test.local")
    # Entra de nuevo para que se le aplique el plan de dueño.
    cliente.post("/api/login", json={"email": "jefa@test.local", "clave": "clave-larga-12345"})
    r = cliente.get("/api/panel", headers=cab)
    assert r.status_code == 200, r.text
    for clave in ("usuarios", "planes", "dinero", "descargas", "actividad"):
        assert clave in r.json(), f"falta {clave} en el panel"


# ---------------------------------------------------------------------------
# Que los números sean los de verdad
# ---------------------------------------------------------------------------
def test_solo_cuenta_como_plata_lo_que_esta_pagado(almacen, hacer_perfil):
    """Un checkout abierto que nadie pagó NO es facturación."""
    p = hacer_perfil(id="u1", email="u1@test.local")
    p.preferencias = Preferencias(generos=[], edad_min=18, edad_max=99)
    almacen.crear_perfil(p, "clave-larga-1")

    almacen.registrar_pago(usuario_id=p.id, plan="plus", periodo="mensual", monto=3.99,
                           moneda="USD", estado="pendiente", pasarela="demo", referencia="r1")
    assert panel.resumen(almacen)["dinero"]["bruto"] == 0, "contó un pago pendiente"

    almacen.registrar_pago(usuario_id=p.id, plan="gold", periodo="mensual", monto=7.99,
                           moneda="USD", estado="pagado", pasarela="demo", referencia="r2")
    d = panel.resumen(almacen)["dinero"]
    assert d["bruto"] == 7.99 and d["cobros"] == 1
    assert d["pendientes"] == 1


def test_el_neto_se_declara_estimado(almacen, hacer_perfil):
    """La comisión real la descuenta la pasarela y varía. Un número que parece
    exacto sin serlo es peor que uno que se declara aproximado."""
    p = hacer_perfil(id="u2", email="u2@test.local")
    almacen.crear_perfil(p, "clave-larga-1")
    almacen.registrar_pago(usuario_id=p.id, plan="plus", periodo="mensual", monto=100.0,
                           moneda="USD", estado="pagado", pasarela="demo", referencia="r3")
    d = panel.resumen(almacen)["dinero"]
    assert d["estimado"] is True
    assert d["comision_estimada_pct"] > 0
    assert d["neto_estimado"] < d["bruto"], "el neto no puede ser igual al bruto"
    assert abs(d["neto_estimado"] - 100.0 * (1 - panel.COMISION_ESTIMADA)) < 0.01


def test_los_perfiles_sinteticos_no_se_cuentan_como_clientes(almacen, hacer_perfil):
    """Con la demo poblada, contar los 60 sintéticos como clientes daría una
    conversión inventada y un panel que miente sobre el tamaño del negocio."""
    real = hacer_perfil(id="real", email="real@test.local")
    almacen.crear_perfil(real, "clave-larga-1")
    falso = hacer_perfil(id="falso", email="falso@test.local", sintetico=True)
    almacen.crear_perfil(falso, "clave-larga-1")

    u = panel.resumen(almacen)["usuarios"]
    assert u["total"] == 1, f"contó sintéticos como clientes: {u}"
    assert u["sinteticos"] == 1


def test_las_descargas_se_cuentan_por_plataforma(almacen):
    for _ in range(3):
        panel.registrar_descarga(almacen, "apk")
    panel.registrar_descarga(almacen, "exe")
    d = panel.resumen(almacen)["descargas"]
    assert d["por_plataforma"]["apk"] == 3
    assert d["por_plataforma"]["exe"] == 1
    assert d["total"] == 4


def test_una_plataforma_inventada_no_entra(almacen):
    panel.registrar_descarga(almacen, "; DROP TABLE descargas; --")
    assert panel.resumen(almacen)["descargas"]["total"] == 0


def test_no_se_guarda_nada_que_identifique_a_la_persona(almacen):
    """Para saber cuántos bajaron el programa no hace falta saber quiénes son.
    Si mañana alguien agrega una columna `ip`, que se entere acá."""
    panel.registrar_descarga(almacen, "apk", referente="https://matcher.app/es/")
    columnas = {
        f[1] for f in almacen.con.execute("PRAGMA table_info(descargas)").fetchall()
    }
    assert columnas == {"id", "plataforma", "referente", "momento"}, columnas
    assert "ip" not in columnas and "usuario_id" not in columnas


def test_el_dinero_por_mes_queda_ordenado(almacen, hacer_perfil):
    p = hacer_perfil(id="u3", email="u3@test.local")
    almacen.crear_perfil(p, "clave-larga-1")
    for i, monto in enumerate((5.0, 10.0)):
        almacen.con.execute(
            "INSERT INTO pagos (id, usuario_id, plan, periodo, monto, moneda, estado, "
            "pasarela, referencia, momento, referencia_externa) VALUES (?,?,?,?,?,?,?,?,?,?,'')",
            (f"p{i}", p.id, "plus", "mensual", monto, "USD", "pagado", "demo", f"ref{i}",
             (datetime(2026, 3 - i, 10)).isoformat()),
        )
    almacen.con.commit()
    por_mes = panel.resumen(almacen)["dinero"]["por_mes"]
    assert list(por_mes) == sorted(por_mes), "los meses salen desordenados"


# ---------------------------------------------------------------------------
# Descargas por HTTP
# ---------------------------------------------------------------------------
def test_sin_url_publicada_no_manda_a_ningun_lado(cliente, monkeypatch):
    """Mejor un 404 honesto que redirigir a una URL rota."""
    monkeypatch.delenv("MATCHER_URL_APK", raising=False)
    assert cliente.get("/api/descargar/apk", follow_redirects=False).status_code == 404


def test_la_descarga_redirige_y_queda_contada(cliente, monkeypatch):
    monkeypatch.setenv("MATCHER_URL_APK", "https://ejemplo.test/matcher.apk")
    monkeypatch.setenv("MATCHER_CUENTAS_DUENIO", "duenia@test.local")

    r = cliente.get("/api/descargar/apk", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "https://ejemplo.test/matcher.apk"

    cab = cuenta(cliente, "duenia@test.local")
    cliente.post("/api/login", json={"email": "duenia@test.local", "clave": "clave-larga-12345"})
    d = cliente.get("/api/panel", headers=cab).json()["descargas"]
    assert d["por_plataforma"]["apk"] >= 1


def test_una_plataforma_que_no_existe_da_404(cliente):
    assert cliente.get("/api/descargar/windows95").status_code == 404


def test_la_descarga_no_pide_sesion(cliente, monkeypatch):
    """Bajar el programa es libre: el plan se decide al entrar, no al bajar."""
    monkeypatch.setenv("MATCHER_URL_EXE", "https://ejemplo.test/Matcher.exe")
    r = cliente.get("/api/descargar/exe", follow_redirects=False)
    assert r.status_code == 302
