"""MercadoPago, PayPal y dLocal: creación de checkout y verificación de
webhook, con las llamadas HTTP simuladas (no hay credenciales reales acá).

Lo que importa verificar de este módulo no es que la integración funcione
contra el proveedor de verdad —eso no se puede probar sin una cuenta— sino
las partes que dependen de nosotros: sin credenciales no arranca, la firma se
verifica antes de confirmar nada, y ningún dato bancario viaja en el código.
"""

import hashlib
import hmac
import json

import pytest

from matcher import pagos
from matcher.modelos import DatosInvalidos


def test_ninguna_pasarela_pide_una_cuenta_bancaria():
    """El código no recibe ni maneja un CBU, un IBAN, ni un número de cuenta:
    eso se configura en el panel de cada proveedor, nunca acá. Se busca la
    palabra como POSIBLE CAMPO (cbu=, "account_number":, etc.), no en la
    prosa de los docstrings — que sí puede mencionarla para explicar por qué
    no está."""
    fuente = open(pagos.__file__, encoding="utf-8").read().lower()
    for patron in ("cbu=", "cbu:", '"cbu"', "iban=", "iban:", '"iban"', "account_number"):
        assert patron not in fuente
    # Y de verdad no hay ningún campo de formulario para cargar una cuenta:
    # las tres integraciones sólo leen credenciales de API por variable de
    # entorno.
    assert "os.getenv" in fuente
    assert "def crear_checkout" in fuente


def test_sin_credenciales_ninguna_pasarela_nueva_arranca(monkeypatch):
    for var in (
        "MERCADOPAGO_ACCESS_TOKEN",
        "PAYPAL_CLIENT_ID",
        "PAYPAL_CLIENT_SECRET",
        "DLOCAL_X_LOGIN",
        "DLOCAL_X_TRANS_KEY",
        "DLOCAL_SECRET_KEY",
    ):
        monkeypatch.delenv(var, raising=False)

    checkout = pagos.Checkout(
        id="c1", usuario_id="u1", plan="plus", periodo="mensual", monto=3.99,
        moneda="USD", pasarela="", url="",
    )
    for nombre in ("mercadopago", "paypal", "dlocal"):
        with pytest.raises(DatosInvalidos, match="falta|faltan"):
            pagos.pasarela_por_nombre(nombre).crear_checkout(checkout)


def test_mercadopago_arma_la_preferencia_y_devuelve_el_init_point(monkeypatch):
    monkeypatch.setenv("MERCADOPAGO_ACCESS_TOKEN", "token-de-prueba")
    monkeypatch.setenv("MATCHER_URL_PUBLICA", "https://matcher.test")

    llamadas = []

    def _pedir_falso(url, *, metodo="GET", datos=None, headers=None):
        llamadas.append((url, metodo, datos, headers))
        return {"id": "pref-123", "init_point": "https://mp.test/pagar/pref-123"}

    monkeypatch.setattr(pagos, "_pedir", _pedir_falso)
    checkout = pagos.Checkout(
        id="c1", usuario_id="u1", plan="plus", periodo="mensual", monto=3.99,
        moneda="USD", pasarela="", url="",
    )
    salida = pagos.PasarelaMercadoPago().crear_checkout(checkout)
    assert salida.url == "https://mp.test/pagar/pref-123"
    assert salida.referencia_externa == "pref-123"

    url, metodo, datos, headers = llamadas[0]
    assert url.endswith("/checkout/preferences")
    assert metodo == "POST"
    assert headers["Authorization"] == "Bearer token-de-prueba"
    assert datos["external_reference"] == "c1"
    assert datos["items"][0]["unit_price"] == 3.99


def test_mercadopago_verifica_la_firma_hmac(monkeypatch):
    monkeypatch.setenv("MERCADOPAGO_WEBHOOK_SECRET", "secreto")
    cuerpo = json.dumps({"data": {"id": "pago-1"}}).encode()
    ts = "1700000000"
    manifest = "id:pago-1;request-id:req-1;ts:1700000000;"
    v1 = hmac.new(b"secreto", manifest.encode(), hashlib.sha256).hexdigest()

    pasarela = pagos.PasarelaMercadoPago()
    ok = pasarela.verificar_webhook(
        cuerpo, {"x-signature": f"ts={ts},v1={v1}", "x-request-id": "req-1"}
    )
    assert ok is True

    # Firma adulterada: no pasa.
    mala = pasarela.verificar_webhook(
        cuerpo, {"x-signature": f"ts={ts},v1=adulterada", "x-request-id": "req-1"}
    )
    assert mala is False


def test_dlocal_firma_el_pedido_y_arma_la_url(monkeypatch):
    monkeypatch.setenv("DLOCAL_X_LOGIN", "login-x")
    monkeypatch.setenv("DLOCAL_X_TRANS_KEY", "trans-x")
    monkeypatch.setenv("DLOCAL_SECRET_KEY", "secreto-dlocal")
    monkeypatch.setenv("MATCHER_URL_PUBLICA", "https://matcher.test")

    class RespuestaFalsa:
        def __init__(self, cuerpo):
            self._cuerpo = cuerpo

        def read(self):
            return self._cuerpo

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    capturado = {}

    def urlopen_falso(pedido, timeout=20):
        capturado["headers"] = dict(pedido.header_items())
        return RespuestaFalsa(json.dumps({"id": "pay-1", "redirect_url": "https://dlocal.test/x"}).encode())

    monkeypatch.setattr(pagos.urllib.request, "urlopen", urlopen_falso)
    checkout = pagos.Checkout(
        id="c1", usuario_id="u1", plan="gold", periodo="anual", monto=59.90,
        moneda="USD", pasarela="", url="",
    )
    salida = pagos.PasarelaDLocal().crear_checkout(checkout)
    assert salida.url == "https://dlocal.test/x"
    assert "X-login" in capturado["headers"] or "X-Login" in capturado["headers"]


def test_dlocal_verifica_webhook_por_hmac_del_cuerpo():
    cuerpo = b'{"order_id":"c1"}'
    firma = hmac.new(b"secreto-dlocal", cuerpo, hashlib.sha256).hexdigest()
    import os

    os.environ["DLOCAL_SECRET_KEY"] = "secreto-dlocal"
    try:
        pasarela = pagos.PasarelaDLocal()
        assert pasarela.verificar_webhook(cuerpo, {"authorization": firma}) is True
        assert pasarela.verificar_webhook(cuerpo, {"authorization": "otra-cosa"}) is False
    finally:
        del os.environ["DLOCAL_SECRET_KEY"]


def test_confirmar_por_referencia_encuentra_al_dueno_del_pago(almacen, hacer_perfil):
    p = hacer_perfil()
    almacen.crear_perfil(p, "clave-larga-1")
    checkout = pagos.iniciar(almacen, p, "plus", "mensual")
    r = pagos.confirmar_por_referencia(almacen, checkout.id)
    assert r["plan"] == "plus"
    assert almacen.perfil(p.id).es_premium is True


def test_confirmar_por_referencia_inexistente_falla(almacen):
    with pytest.raises(DatosInvalidos, match="no existe ese pago"):
        pagos.confirmar_por_referencia(almacen, "no-existe")
