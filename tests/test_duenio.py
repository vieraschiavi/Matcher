"""Las cuentas del dueño.

El riesgo de una función así es evidente: si se equivoca, cualquiera se queda
con Gold gratis. Estos tests fijan las tres cosas que la hacen segura —lista
vacía por defecto, comparación exacta, y que no toque la contabilidad— y la que
la hace útil: que en producción el dueño tenga su app en Gold sin pagarse a sí
mismo.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from matcher import duenio
from matcher.modelos import Preferencias


@pytest.fixture
def cuenta(hacer_perfil, almacen):
    p = hacer_perfil(id="due", email="Duenio@Matcher.test")
    p.preferencias = Preferencias(generos=[], edad_min=18, edad_max=99)
    almacen.crear_perfil(p, "clave-larga-1")
    return p


def test_sin_configurar_no_hay_ninguna_cuenta_privilegiada(monkeypatch, almacen, cuenta):
    """El bug con el que se cuelan la mitad de los productos es el admin/admin
    de fábrica. Acá, sin variable, la lista está vacía."""
    monkeypatch.delenv("MATCHER_CUENTAS_DUENIO", raising=False)
    assert duenio.emails() == set()
    assert duenio.aplicar(almacen, cuenta) is False
    assert cuenta.plan == "gratis"


def test_la_cuenta_de_la_lista_queda_en_gold(monkeypatch, almacen, cuenta):
    monkeypatch.setenv("MATCHER_CUENTAS_DUENIO", "duenio@matcher.test")
    assert duenio.aplicar(almacen, cuenta) is True
    guardado = almacen.perfil(cuenta.id)
    assert guardado.plan == "gold"
    assert guardado.plan_vence > datetime.utcnow() + timedelta(days=300)


def test_la_comparacion_no_distingue_mayusculas(monkeypatch, almacen, cuenta):
    """El email del perfil está en mayúsculas mezcladas a propósito."""
    monkeypatch.setenv("MATCHER_CUENTAS_DUENIO", "  DUENIO@matcher.TEST , otro@x.test ")
    assert duenio.es_duenio("duenio@matcher.test")
    assert duenio.aplicar(almacen, cuenta) is True


def test_no_se_puede_poner_un_comodin(monkeypatch, almacen, hacer_perfil):
    """`*@gmail.com` tiene que NO funcionar: si funcionara, un error de dedo
    dejaría a medio mundo con Gold."""
    monkeypatch.setenv("MATCHER_CUENTAS_DUENIO", "*@matcher.test")
    assert duenio.es_duenio("cualquiera@matcher.test") is False


def test_una_cuenta_que_no_esta_no_recibe_nada(monkeypatch, almacen, cuenta):
    monkeypatch.setenv("MATCHER_CUENTAS_DUENIO", "otra@matcher.test")
    assert duenio.aplicar(almacen, cuenta) is False
    assert almacen.perfil(cuenta.id).plan == "gratis"


def test_no_reescribe_el_perfil_en_cada_entrada(monkeypatch, almacen, cuenta):
    """Se llama en cada login: si escribiera siempre, sería una escritura por
    pedido contra la base por nada."""
    monkeypatch.setenv("MATCHER_CUENTAS_DUENIO", "duenio@matcher.test")
    assert duenio.aplicar(almacen, cuenta) is True
    assert duenio.aplicar(almacen, cuenta) is False, "reescribió sin necesidad"


def test_se_renueva_cuando_esta_por_vencer(monkeypatch, almacen, cuenta):
    monkeypatch.setenv("MATCHER_CUENTAS_DUENIO", "duenio@matcher.test")
    cuenta.plan = "gold"
    cuenta.plan_vence = datetime.utcnow() + timedelta(days=3)
    almacen.guardar_perfil(cuenta)
    assert duenio.aplicar(almacen, cuenta) is True
    assert almacen.perfil(cuenta.id).plan_vence > datetime.utcnow() + timedelta(days=300)


def test_no_inventa_un_pago(monkeypatch, almacen, cuenta):
    """La contabilidad tiene que seguir mostrando lo que se cobró DE VERDAD.
    Un Gold de regalo que aparece como venta arruina el único número que sirve
    para saber cómo va el negocio."""
    monkeypatch.setenv("MATCHER_CUENTAS_DUENIO", "duenio@matcher.test")
    duenio.aplicar(almacen, cuenta)
    assert almacen.pagos_de(cuenta.id) == []


def test_por_http_el_login_del_duenio_entra_en_gold(cliente, monkeypatch):
    """El circuito real: entrar con la cuenta y salir con Gold puesto."""
    r = cliente.post(
        "/api/registro",
        json={
            "email": "jefe@matcher.test", "clave": "clave-larga-12345", "nombre": "Jefe",
            "nacimiento": "1990-01-01", "genero": "hombre", "altura_cm": 178,
            "pais": "UY", "ciudad": "UY-MVD",
            "preferencias": {"generos": [], "edad_min": 18, "edad_max": 99},
        },
    )
    assert r.status_code == 200 and r.json()["perfil"]["plan"] == "gratis"

    monkeypatch.setenv("MATCHER_CUENTAS_DUENIO", "jefe@matcher.test")
    r = cliente.post("/api/login", json={"email": "jefe@matcher.test", "clave": "clave-larga-12345"})
    assert r.status_code == 200
    assert r.json()["perfil"]["plan"] == "gold"
    assert r.json()["perfil"]["es_premium"] is True


def test_por_http_sin_la_variable_nadie_sube_de_plan(cliente, monkeypatch):
    monkeypatch.delenv("MATCHER_CUENTAS_DUENIO", raising=False)
    cliente.post(
        "/api/registro",
        json={
            "email": "comun@matcher.test", "clave": "clave-larga-12345", "nombre": "Común",
            "nacimiento": "1990-01-01", "genero": "hombre", "altura_cm": 178,
            "pais": "UY", "ciudad": "UY-MVD",
            "preferencias": {"generos": [], "edad_min": 18, "edad_max": 99},
        },
    )
    r = cliente.post("/api/login", json={"email": "comun@matcher.test", "clave": "clave-larga-12345"})
    assert r.json()["perfil"]["plan"] == "gratis"
