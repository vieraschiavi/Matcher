"""Nadie recibe un plan sin que la pasarela diga que la plata entró.

EL AGUJERO QUE ESTE ARCHIVO CIERRA

`/api/pagos/confirmar` daba el plan de alta con sólo recibir una referencia,
sin preguntarle nada al proveedor. Con una cuenta cualquiera alcanzaba con:

    POST /api/pagos/checkout  {"plan": "gold"}   -> referencia
    POST /api/pagos/confirmar {"referencia": …}  -> Gold activado

y listo, Gold gratis para siempre. En modo `demo` eso es correcto (no hay plata
de por medio), pero con MercadoPago enchufado era la caja abierta.

Peor: la auditoría de pagos que corrí antes —27 verificaciones, 0 fallos— hacía
EXACTAMENTE esa secuencia y la leía como "los pagos están bien cableados". No
estaba probando el cobro: estaba ejercitando el agujero.

El segundo agujero, funcional: MercadoPago notifica `{"data": {"id": …}}` sin
mandar nuestra referencia, así que el webhook no encontraba a qué cobro
correspondía, respondía "procesado: false" y **el plan no se activaba nunca**.
Quien pagaba y cerraba el navegador se quedaba sin nada.
"""

from __future__ import annotations

import pytest

from matcher import pagos
from matcher.modelos import Preferencias


def cuenta_nueva(cliente, email: str) -> dict:
    """Cabeceras de una cuenta RECIÉN creada, en plan gratis.

    No sirve `conftest.entrar`: entra a las cuentas de demo, que vienen con
    Gold puesto — y un test que arranca en Gold no puede probar que Gold no se
    regala."""
    r = cliente.post(
        "/api/registro",
        json={
            "email": email, "clave": "clave-larga-12345", "nombre": "Prueba",
            "nacimiento": "1993-04-04", "genero": "mujer", "altura_cm": 170,
            "pais": "UY", "ciudad": "UY-MVD",
            "preferencias": {"generos": [], "edad_min": 18, "edad_max": 99},
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["perfil"]["plan"] == "gratis"
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def pagador(hacer_perfil, almacen):
    p = hacer_perfil(id="pagador", email="pagador@test.local")
    p.preferencias = Preferencias(generos=[], edad_min=18, edad_max=99)
    almacen.crear_perfil(p, "clave-larga-1")
    return p


class PasarelaQueNoCobro(pagos.Pasarela):
    """Una pasarela de verdad donde el pago NO entró: es el caso del que pide
    un checkout y nunca paga."""

    nombre = "mercadopago"  # se hace pasar por una real a propósito

    def crear_checkout(self, checkout):
        checkout.url = "https://pasarela.test/pagar"
        checkout.referencia_externa = "pref-123"
        return checkout

    def verificar_webhook(self, cuerpo, cabeceras):
        return True

    def esta_pagado(self, referencia, referencia_externa):
        return False

    def referencia_de_notificacion(self, datos):
        return datos.get("external_reference")


class PasarelaQueSiCobro(PasarelaQueNoCobro):
    def esta_pagado(self, referencia, referencia_externa):
        return True


# ---------------------------------------------------------------------------
# El agujero
# ---------------------------------------------------------------------------
def test_no_se_activa_el_plan_si_la_pasarela_no_cobro(almacen, pagador, monkeypatch):
    monkeypatch.setattr(pagos, "pasarela_activa", lambda: PasarelaQueNoCobro())
    monkeypatch.setattr(pagos, "pasarela_por_nombre", lambda n: PasarelaQueNoCobro())

    checkout = pagos.iniciar(almacen, pagador, "gold", "mensual")
    with pytest.raises(pagos.PagoNoAcreditado):
        pagos.confirmar(almacen, pagador, checkout.id)

    assert almacen.perfil(pagador.id).plan == "gratis", (
        "se activó Gold sin que entrara un peso"
    )


def test_se_activa_cuando_la_pasarela_confirma(almacen, pagador, monkeypatch):
    monkeypatch.setattr(pagos, "pasarela_activa", lambda: PasarelaQueSiCobro())
    monkeypatch.setattr(pagos, "pasarela_por_nombre", lambda n: PasarelaQueSiCobro())

    checkout = pagos.iniciar(almacen, pagador, "gold", "mensual")
    r = pagos.confirmar(almacen, pagador, checkout.id)
    assert r["plan"] == "gold"
    assert almacen.perfil(pagador.id).plan == "gold"


def test_reintentar_no_duplica_el_periodo(almacen, pagador, monkeypatch):
    """Idempotencia: el webhook reintenta y la persona además vuelve del
    redirect. No pueden sumarse dos meses por un pago."""
    monkeypatch.setattr(pagos, "pasarela_activa", lambda: PasarelaQueSiCobro())
    monkeypatch.setattr(pagos, "pasarela_por_nombre", lambda n: PasarelaQueSiCobro())

    checkout = pagos.iniciar(almacen, pagador, "plus", "mensual")
    primero = pagos.confirmar(almacen, pagador, checkout.id)
    segundo = pagos.confirmar(almacen, pagador, checkout.id)

    assert segundo["ya_confirmado"] is True
    assert almacen.perfil(pagador.id).plan_vence.isoformat() == primero["vence"]


def test_la_referencia_externa_se_guarda(almacen, pagador, monkeypatch):
    """Sin el id que le puso el proveedor no se le puede preguntar nada
    después: PayPal y dLocal consultan por ESE id."""
    monkeypatch.setattr(pagos, "pasarela_activa", lambda: PasarelaQueSiCobro())
    checkout = pagos.iniciar(almacen, pagador, "plus", "mensual")
    fila = almacen.pago_por_referencia(checkout.id)
    assert fila["referencia_externa"] == "pref-123"


# ---------------------------------------------------------------------------
# Por HTTP: el exploit exacto
# ---------------------------------------------------------------------------
def test_por_http_confirmar_a_mano_no_regala_el_plan(cliente, monkeypatch):
    monkeypatch.setattr(pagos, "pasarela_activa", lambda: PasarelaQueNoCobro())
    monkeypatch.setattr(pagos, "pasarela_por_nombre", lambda n: PasarelaQueNoCobro())
    cabeceras = cuenta_nueva(cliente, "sinpagar@test.local")

    r = cliente.post(
        "/api/pagos/checkout", json={"plan": "gold", "periodo": "mensual"}, headers=cabeceras
    )
    assert r.status_code == 200
    referencia = r.json()["checkout"]["id"]

    r = cliente.post(
        "/api/pagos/confirmar", json={"referencia": referencia}, headers=cabeceras
    )
    assert r.status_code == 409, f"confirmó sin cobrar: {r.status_code} {r.text[:120]}"
    assert r.json()["reintentable"] is True

    yo = cliente.get("/api/yo", headers=cabeceras).json()["perfil"]
    assert yo["plan"] == "gratis" and not yo["es_premium"]


def test_no_se_puede_confirmar_el_pago_de_otro(cliente, monkeypatch):
    """La referencia es adivinable-ish; el dueño del pago tiene que mandar."""
    monkeypatch.setattr(pagos, "pasarela_activa", lambda: PasarelaQueSiCobro())
    monkeypatch.setattr(pagos, "pasarela_por_nombre", lambda n: PasarelaQueSiCobro())

    uno = cuenta_nueva(cliente, "duenio@test.local")
    referencia = cliente.post(
        "/api/pagos/checkout", json={"plan": "gold", "periodo": "mensual"}, headers=uno
    ).json()["checkout"]["id"]

    otro = cuenta_nueva(cliente, "ladron@test.local")
    r = cliente.post("/api/pagos/confirmar", json={"referencia": referencia}, headers=otro)
    assert r.status_code == 400, "otro usuario confirmó un pago ajeno"
    assert cliente.get("/api/yo", headers=otro).json()["perfil"]["plan"] == "gratis"


# ---------------------------------------------------------------------------
# El webhook de MercadoPago
# ---------------------------------------------------------------------------
def test_mercadopago_avisa_con_el_id_del_pago_y_hay_que_ir_a_buscarlo():
    """El cuerpo real de MercadoPago NO trae `external_reference`.

    Con el `or` encadenado que había antes, esto devolvía None y el plan no se
    activaba nunca. Ahora la pasarela sabe que tiene que consultar su API.
    """
    mp = pagos.PasarelaMercadoPago()
    cuerpo_real = {"action": "payment.updated", "type": "payment", "data": {"id": "1234567890"}}

    # Sin credenciales no puede consultar y devuelve None en vez de reventar:
    # el handler responde 200 y el proveedor reintenta.
    assert mp.referencia_de_notificacion(cuerpo_real) is None

    # Cuando MercadoPago sí manda la referencia (algunos eventos la traen), se
    # usa directamente y no se gasta una llamada a la API.
    assert mp.referencia_de_notificacion({"external_reference": "abc123"}) == "abc123"


def test_cada_pasarela_sabe_leer_su_propia_notificacion():
    assert pagos.PasarelaDLocal().referencia_de_notificacion({"order_id": "o-1"}) == "o-1"
    assert (
        pagos.PasarelaPayPal().referencia_de_notificacion(
            {"resource": {"purchase_units": [{"reference_id": "p-1"}]}}
        )
        == "p-1"
    )


def test_todas_las_pasarelas_implementan_la_verificacion():
    """Si mañana se agrega una pasarela y se olvida `esta_pagado`, el plan se
    daría de alta sin verificar. Que reviente en el test, no en producción."""
    for clase in (
        pagos.PasarelaDemo,
        pagos.PasarelaMercadoPago,
        pagos.PasarelaPayPal,
        pagos.PasarelaDLocal,
    ):
        for metodo in ("esta_pagado", "referencia_de_notificacion"):
            assert metodo in clase.__dict__, f"{clase.__name__} no implementa {metodo}"
