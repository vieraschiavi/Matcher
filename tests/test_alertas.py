"""Avisar cuando alguien quiere comprar, y cuando la plata entró.

PARA QUÉ EXISTE ESTO
El dueño tiene varios proyectos y el hosting pago se cobra por equipo activado.
Pagarlo por adelantado en todos, sin saber si alguien quiere comprar en alguno,
es tirar plata contra una hipótesis. Estas alertas contestan la única pregunta
que decide eso: ¿hay alguien intentando pagar?

LO QUE SE PROTEGE ACÁ, EN ORDEN DE GRAVEDAD

1. **Que un aviso roto no cueste una venta.** Es lo peor que puede pasar: que
   el mail falle y la persona se quede sin llegar a MercadoPago. Hay dos tests
   dedicados — uno rompe el envío a propósito y exige que el checkout salga
   igual, y otro comprueba que el aviso ni siquiera espera al proveedor.
2. **Que la señal sea del servidor.** Un `onClick` del navegador se pierde con
   un bloqueador, se repite si la persona insiste, y lo manda el cliente, así
   que no se puede creer.
3. **Que no se convierta en ruido.** Alguien que vuelve tres veces al checkout
   es una señal, no tres mails. Pero un COBRO siempre avisa: ése es el único
   mail que significa dinero.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from matcher import alertas, aviso, pagos

ALTA = {
    "clave": "clave-larga-12345", "nacimiento": "1990-01-01", "genero": "mujer",
    "altura_cm": 170, "pais": "UY", "ciudad": "UY-MVD",
    "preferencias": {"generos": [], "edad_min": 18, "edad_max": 99},
}


@pytest.fixture
def buzon(monkeypatch):
    """Intercepta el envío real. Devuelve la lista de mails que se mandaron.

    Se parchea `aviso.mandar_en_segundo_plano` y no `aviso.mandar`, porque lo
    que se quiere observar es lo que las alertas DECIDEN mandar — y de paso el
    test no depende de un hilo, que es lo que vuelve intermitente a un test.
    """
    mails = []
    monkeypatch.setattr(
        aviso, "mandar_en_segundo_plano",
        lambda asunto, cuerpo, responder_a="": mails.append(
            {"asunto": asunto, "cuerpo": cuerpo, "responder_a": responder_a}
        ),
    )
    return mails


def cuenta(cliente, email, nombre="Alguien") -> dict:
    r = cliente.post("/api/registro", json={**ALTA, "email": email, "nombre": nombre})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def checkout(cliente, cab, plan="gold"):
    return cliente.post(
        "/api/pagos/checkout", json={"plan": plan, "periodo": "mensual"}, headers=cab
    ).json()["checkout"]


# ---------------------------------------------------------------------------
# Lo primero: que el aviso nunca cueste una venta
# ---------------------------------------------------------------------------
def test_si_el_mail_explota_la_compra_sigue(cliente, monkeypatch):
    """ES LO MÁS IMPORTANTE DE ESTE ARCHIVO.

    Un aviso es una comodidad. Si se cae y con él se cae el checkout, la
    herramienta que existe para no perder ventas pasa a ser la que las pierde
    — y justo el día que el proveedor de correo está caído, que es cuando menos
    se lo mira.

    Este test encontró el bug de verdad: `alertas` decía en su encabezado
    "nunca levanta" y no lo cumplía.
    """
    def explota(*_a, **_k):
        raise RuntimeError("Resend caído")

    monkeypatch.setattr(aviso, "mandar_en_segundo_plano", explota)
    cab = cuenta(cliente, "compra@test.local", "Compradora")

    r = cliente.post(
        "/api/pagos/checkout", json={"plan": "gold", "periodo": "mensual"}, headers=cab
    )
    assert r.status_code == 200, (
        "el checkout se cayó porque falló un mail: eso cuesta la venta que la "
        "alerta existe para no perder"
    )
    assert r.json()["checkout"]["url"], "no devolvió el enlace de pago"


def test_el_aviso_no_hace_esperar_al_que_compra(cliente, monkeypatch):
    """El usuario está esperando el redirect a la pasarela. Una llamada HTTP
    más, con su timeout, en el camino crítico de una compra es el peor lugar
    posible para agregar latencia: por eso va en segundo plano."""
    llamadas = {"sincronico": 0, "segundo_plano": 0}
    monkeypatch.setattr(aviso, "mandar", lambda *a, **k: llamadas.__setitem__(
        "sincronico", llamadas["sincronico"] + 1) or True)
    monkeypatch.setattr(aviso, "mandar_en_segundo_plano", lambda *a, **k: llamadas.__setitem__(
        "segundo_plano", llamadas["segundo_plano"] + 1))

    cab = cuenta(cliente, "compra@test.local", "Compradora")
    checkout(cliente, cab)

    assert llamadas["segundo_plano"] == 1
    assert llamadas["sincronico"] == 0, (
        "el aviso de compra se manda sincrónico y demora el checkout"
    )


# ---------------------------------------------------------------------------
# La señal sale del servidor, con los datos de verdad
# ---------------------------------------------------------------------------
def test_abrir_el_checkout_dispara_el_aviso(cliente, buzon):
    cab = cuenta(cliente, "ana@test.local", "Ana Pérez")
    checkout(cliente, cab)

    assert len(buzon) == 1, buzon
    m = buzon[0]
    assert "quiere comprar" in m["asunto"].lower()
    assert "ana@test.local" in m["cuerpo"]
    assert "Ana Pérez" in m["cuerpo"]
    assert "gold" in m["cuerpo"].lower()
    # Responder va directo a la persona, sin copiar la dirección a mano.
    assert m["responder_a"] == "ana@test.local"


def test_el_aviso_de_intencion_dice_que_todavia_no_pago(cliente, buzon):
    """Buena parte de los checkouts no se completan. Un mail que diga "vendiste"
    cuando no entró un peso hace que el siguiente no se lea."""
    cab = cuenta(cliente, "ana@test.local", "Ana")
    checkout(cliente, cab)
    assert "TODAVÍA NO PAGÓ" in buzon[0]["cuerpo"]


def test_el_monto_del_aviso_es_el_que_se_va_a_cobrar(cliente, buzon):
    """El monto sale del checkout, no de un texto escrito a mano: si cambia el
    precio, el mail cambia solo."""
    cab = cuenta(cliente, "ana@test.local", "Ana")
    ch = checkout(cliente, cab)
    esperado = pagos.precio("gold", "mensual")
    assert ch["monto"] == esperado
    assert f"{esperado:.2f}".replace(".", ",") in buzon[0]["cuerpo"]


# ---------------------------------------------------------------------------
# Que no se vuelva ruido
# ---------------------------------------------------------------------------
def test_volver_al_checkout_no_manda_tres_mails(cliente, buzon):
    """Alguien que duda y vuelve dos veces es UNA señal. Tres mails por la
    misma persona es cómo se aprende a ignorar la casilla."""
    cab = cuenta(cliente, "indecisa@test.local", "Indecisa")
    for _ in range(3):
        checkout(cliente, cab)
    assert len(buzon) == 1, f"mandó {len(buzon)} mails por la misma persona"


def test_otra_persona_si_avisa(cliente, buzon):
    """La contracara: el freno es por persona, no global. Si no, el segundo
    cliente del día pasa desapercibido."""
    checkout(cliente, cuenta(cliente, "una@test.local", "Una"))
    checkout(cliente, cuenta(cliente, "otra@test.local", "Otra"))
    assert len(buzon) == 2


def test_la_ventana_se_vence(almacen, hacer_perfil):
    """Pasada la ventana, la misma persona vuelve a ser noticia."""
    p = hacer_perfil(id="u1", email="ana@test.local")
    almacen.crear_perfil(p, "clave-larga-12345")
    # `registrar_pago` estampa `datetime.utcnow()`, así que el reloj del test
    # tiene que salir de ahí. Con una fecha inventada del pasado, la ventana
    # arranca antes que las filas y las cuenta todas: el test pasaba a probar
    # otra cosa.
    ahora = datetime.utcnow()
    almacen.registrar_pago(
        usuario_id=p.id, plan="gold", periodo="mensual", monto=6.9, moneda="USD",
        estado="pendiente", pasarela="demo", referencia="r1",
    )
    assert alertas._repetida(almacen, p.id, ahora) is False
    almacen.registrar_pago(
        usuario_id=p.id, plan="gold", periodo="mensual", monto=6.9, moneda="USD",
        estado="pendiente", pasarela="demo", referencia="r2",
    )
    assert alertas._repetida(almacen, p.id, ahora) is True
    despues = ahora + alertas.VENTANA_INTENCION + timedelta(minutes=1)
    assert alertas._repetida(almacen, p.id, despues) is False


def test_se_puede_apagar_la_intencion_sin_apagar_el_cobro(cliente, buzon, monkeypatch):
    """Si algún día hay volumen, la de intención se vuelve ruido y la del cobro
    no. Por eso son dos variables."""
    monkeypatch.setenv("MATCHER_ALERTA_INTENCION", "0")
    cab = cuenta(cliente, "ana@test.local", "Ana")
    ch = checkout(cliente, cab)
    assert buzon == [], "avisó la intención con la alerta apagada"

    cliente.post("/api/pagos/confirmar", json={"referencia": ch["id"]}, headers=cab)
    assert len(buzon) == 1, "apagar la intención apagó también el cobro"
    assert "COBRADO" in buzon[0]["asunto"]


# ---------------------------------------------------------------------------
# El cobro: el único mail que significa dinero
# ---------------------------------------------------------------------------
def test_el_cobro_avisa_con_el_monto(cliente, buzon):
    cab = cuenta(cliente, "paga@test.local", "Paga")
    ch = checkout(cliente, cab)
    r = cliente.post("/api/pagos/confirmar", json={"referencia": ch["id"]}, headers=cab)
    assert r.status_code == 200, r.text

    cobro = [m for m in buzon if "COBRADO" in m["asunto"]]
    assert len(cobro) == 1, buzon
    assert "paga@test.local" in cobro[0]["cuerpo"]
    assert "gold" in cobro[0]["cuerpo"].lower()


def test_el_cobro_no_avisa_dos_veces_si_el_webhook_reintenta(cliente, buzon):
    """Las pasarelas reintentan los webhooks. `confirmar` es idempotente, y el
    aviso tiene que heredar esa propiedad: dos mails de COBRADO por un solo
    pago hacen dudar de todos los demás."""
    cab = cuenta(cliente, "paga@test.local", "Paga")
    ch = checkout(cliente, cab)
    for _ in range(3):
        cliente.post("/api/pagos/confirmar", json={"referencia": ch["id"]}, headers=cab)

    assert len([m for m in buzon if "COBRADO" in m["asunto"]]) == 1


def test_un_pago_no_acreditado_no_avisa_cobro(almacen, hacer_perfil, buzon, monkeypatch):
    """El mail de COBRADO no puede salir antes que la plata. Si la pasarela
    dice que no está acreditado, `confirmar` levanta y no se avisa nada."""
    from matcher.pagos import PagoNoAcreditado

    p = hacer_perfil(id="u1", email="ana@test.local")
    almacen.crear_perfil(p, "clave-larga-12345")
    almacen.registrar_pago(
        usuario_id=p.id, plan="gold", periodo="mensual", monto=6.9, moneda="USD",
        estado="pendiente", pasarela="demo", referencia="ref-1",
    )
    monkeypatch.setattr(
        pagos.PasarelaDemo, "esta_pagado", lambda self, ref, ext: False
    )
    with pytest.raises(PagoNoAcreditado):
        pagos.confirmar(almacen, p, "ref-1")

    assert [m for m in buzon if "COBRADO" in m["asunto"]] == []


# ---------------------------------------------------------------------------
# Sin proveedor de correo configurado
# ---------------------------------------------------------------------------
def test_sin_proveedor_de_correo_no_se_levanta_ni_el_hilo(monkeypatch):
    """Sin Resend ni SMTP no hay nada que mandar. Levantar un hilo por cada
    checkout para no hacer nada es gastar por gastar."""
    import threading

    for v in ("RESEND_API_KEY", "MATCHER_SMTP_HOST", "MATCHER_SMTP_USUARIO",
              "MATCHER_SMTP_CLAVE"):
        monkeypatch.delenv(v, raising=False)

    def no_deberia(**_k):
        raise AssertionError("levantó un hilo sin proveedor de correo")

    monkeypatch.setattr(threading, "Thread", no_deberia)

    assert aviso.como_avisa() == "ninguna"
    aviso.mandar_en_segundo_plano("asunto", "cuerpo")   # no tiene que explotar


def test_el_checkout_anda_sin_proveedor_de_correo(cliente, monkeypatch):
    """La app tiene que funcionar entera sin haber configurado ningún mail."""
    for v in ("RESEND_API_KEY", "MATCHER_SMTP_HOST", "MATCHER_SMTP_USUARIO",
              "MATCHER_SMTP_CLAVE"):
        monkeypatch.delenv(v, raising=False)
    cab = cuenta(cliente, "ana@test.local", "Ana")
    assert cliente.post(
        "/api/pagos/checkout", json={"plan": "gold", "periodo": "mensual"}, headers=cab
    ).status_code == 200
