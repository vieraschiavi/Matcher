"""Login con proveedor externo (Google).

No se prueba contra Google de verdad: se simulan las respuestas HTTP del
proveedor. Lo que importa verificar acá es lo que puede salir mal del lado
nuestro — `state`, email sin verificar, cuenta ya existente, alta vencida.
"""

import time

import pytest
from fastapi.testclient import TestClient

from matcher import demo, oauth
from matcher.almacen import Almacen
from matcher.modelos import DatosInvalidos
from webapp.backend import api as backend


@pytest.fixture
def con_google(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id-de-prueba")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secreto-de-prueba")
    monkeypatch.setenv("MATCHER_URL_PUBLICA", "https://matcher.test")


@pytest.fixture
def cliente(monkeypatch):
    a = Almacen(":memory:")
    demo.poblar(a, cantidad=25)
    monkeypatch.setattr(backend, "_almacen", a)
    monkeypatch.setattr(backend, "POBLAR_DEMO", False)
    with TestClient(backend.app, follow_redirects=False) as c:
        yield c
    a.cerrar()


def simular_proveedor(monkeypatch, email, nombre="Alguien", verificado=True):
    monkeypatch.setattr(oauth, "intercambiar_codigo", lambda *a, **k: "token-de-acceso")
    monkeypatch.setattr(
        oauth,
        "_get",
        lambda url, tok: {
            "email": email,
            "email_verified": verificado,
            "given_name": nombre,
            "picture": "https://x.test/f.jpg",
        },
    )


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
def test_sin_credenciales_no_se_ofrece(cliente, monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    assert oauth.disponibles() == []
    assert cliente.get("/api/auth/proveedores").json()["proveedores"] == []
    # Y el inicio falla con un mensaje que dice qué falta, en vez de mandar al
    # usuario a una URL rota.
    r = cliente.get("/api/auth/google/inicio")
    assert r.status_code == 400
    assert "GOOGLE_CLIENT_ID" in r.json()["detail"]


def test_con_credenciales_se_ofrece(cliente, con_google):
    assert cliente.get("/api/auth/proveedores").json()["proveedores"] == ["google"]


def test_proveedor_desconocido(cliente):
    assert cliente.get("/api/auth/facebook/inicio").status_code == 400


def test_url_de_autorizacion_lleva_lo_que_tiene_que_llevar(con_google):
    url, estado = oauth.url_de_autorizacion("google", "https://matcher.test")
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=id-de-prueba" in url
    assert "response_type=code" in url
    assert f"state={estado}" in url
    assert "redirect_uri=https%3A%2F%2Fmatcher.test%2Fapi%2Fauth%2Fgoogle%2Fcallback" in url
    # El secreto NUNCA sale en la URL de autorización: va sólo en el POST de
    # intercambio, servidor a servidor.
    assert "secreto-de-prueba" not in url


# ---------------------------------------------------------------------------
# state (CSRF)
# ---------------------------------------------------------------------------
def test_el_state_es_de_un_solo_uso():
    # El `destino` es una lista cerrada de dos valores ("web" y "app"), no una
    # ruta libre. Antes aceptaba cualquier cadena y la devolvía tal cual; no lo
    # usaba nadie (el frontend no lo mandaba y el callback descartaba el valor)
    # y una ruta libre que después se usa para redirigir es exactamente la
    # forma de un open redirect. Ver `oauth.url_de_vuelta`.
    s = oauth.nuevo_estado(oauth.DESTINO_APP)
    assert oauth.consumir_estado(s) == oauth.DESTINO_APP
    with pytest.raises(DatosInvalidos):
        oauth.consumir_estado(s)


def test_state_invalido_o_vencido_se_rechaza(monkeypatch):
    with pytest.raises(DatosInvalidos):
        oauth.consumir_estado("inventado")

    s = oauth.nuevo_estado()
    # El reloj original se captura ANTES de parchear: si el lambda llama a
    # `time.time()`, se llama a sí mismo y explota por recursión.
    ahora = time.time()
    monkeypatch.setattr(time, "time", lambda: ahora + oauth.VIDA_ESTADO_SEG + 10)
    with pytest.raises(DatosInvalidos):
        oauth.consumir_estado(s)


def test_el_callback_sin_state_no_crea_nada(cliente, con_google, monkeypatch):
    """Sin validar el state, cualquiera puede inducir un login ajeno."""
    simular_proveedor(monkeypatch, "intruso@test.local")
    antes = len(backend.almacen().todos())
    r = cliente.get("/api/auth/google/callback?code=abc&state=falsificado")
    assert r.status_code == 400
    assert len(backend.almacen().todos()) == antes


# ---------------------------------------------------------------------------
# Alta nueva
# ---------------------------------------------------------------------------
def test_email_nuevo_manda_a_completar_y_no_crea_perfil(cliente, con_google, monkeypatch):
    simular_proveedor(monkeypatch, "nueva@test.local", "Nueva")
    _, estado = oauth.url_de_autorizacion("google", "https://matcher.test")
    r = cliente.get(f"/api/auth/google/callback?code=abc&state={estado}")
    assert r.status_code == 307
    destino = r.headers["location"]
    assert "#/completar?alta=" in destino
    # Todavía NO hay perfil: un perfil a medias ensucia el deck.
    assert backend.almacen().buscar_por_email("nueva@test.local") is None

    alta = destino.split("alta=")[1]
    datos = cliente.get(f"/api/auth/alta/{alta}").json()
    assert datos["email"] == "nueva@test.local"
    assert datos["nombre"] == "Nueva"
    assert datos["proveedor"] == "google"


def test_completar_crea_la_cuenta_y_deja_la_sesion_abierta(cliente, con_google, monkeypatch):
    simular_proveedor(monkeypatch, "nueva@test.local", "Nueva")
    _, estado = oauth.url_de_autorizacion("google", "https://matcher.test")
    destino = cliente.get(f"/api/auth/google/callback?code=abc&state={estado}").headers["location"]
    alta = destino.split("alta=")[1]

    r = cliente.post(
        "/api/auth/completar",
        json={
            "alta": alta,
            "nacimiento": "1994-04-04",
            "genero": "mujer",
            "altura_cm": 167,
            "pais": "UY",
            "ciudad": "UY-MVD",
            "equipo": "Peñarol",
            "preferencias": {"busca": "todos", "edad_min": 18, "edad_max": 99},
        },
    )
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["perfil"]["email"] == "nueva@test.local"
    assert cuerpo["perfil"]["equipo"] == "Peñarol"
    # El proveedor confirmó el EMAIL; eso no es "perfil verificado" (identidad
    # con documento), así que no se marca.
    assert cuerpo["perfil"]["verificado"] is False

    h = {"Authorization": f"Bearer {cuerpo['token']}"}
    assert cliente.get("/api/yo", headers=h).status_code == 200
    assert backend.almacen().proveedores_de(cuerpo["perfil"]["id"]) == ["google"]


def test_el_alta_es_de_un_solo_uso(cliente, con_google, monkeypatch):
    simular_proveedor(monkeypatch, "unavez@test.local")
    _, estado = oauth.url_de_autorizacion("google", "https://matcher.test")
    destino = cliente.get(f"/api/auth/google/callback?code=abc&state={estado}").headers["location"]
    alta = destino.split("alta=")[1]
    cuerpo = {
        "alta": alta,
        "nacimiento": "1994-04-04",
        "genero": "mujer",
        "altura_cm": 167,
        "pais": "UY",
        "ciudad": "UY-MVD",
    }
    assert cliente.post("/api/auth/completar", json=cuerpo).status_code == 200
    segunda = cliente.post("/api/auth/completar", json=cuerpo)
    assert segunda.status_code == 410


def test_alta_inexistente_da_410(cliente):
    assert cliente.get("/api/auth/alta/no-existe").status_code == 410


def test_completar_valida_igual_que_el_registro_normal(cliente, con_google, monkeypatch):
    simular_proveedor(monkeypatch, "menor@test.local")
    _, estado = oauth.url_de_autorizacion("google", "https://matcher.test")
    destino = cliente.get(f"/api/auth/google/callback?code=abc&state={estado}").headers["location"]
    alta = destino.split("alta=")[1]
    r = cliente.post(
        "/api/auth/completar",
        json={
            "alta": alta,
            "nacimiento": "2016-01-01",
            "genero": "mujer",
            "altura_cm": 150,
            "pais": "UY",
            "ciudad": "UY-MVD",
        },
    )
    assert r.status_code == 400
    assert "18" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Cuenta existente
# ---------------------------------------------------------------------------
def test_email_conocido_entra_directo(cliente, con_google, monkeypatch):
    """La cuenta demo existe con contraseña; entrar con Google contra el mismo
    email tiene que abrir esa cuenta, no crear una segunda."""
    simular_proveedor(monkeypatch, "vieraschiavi@gmail.com", "Martín")
    _, estado = oauth.url_de_autorizacion("google", "https://matcher.test")
    r = cliente.get(f"/api/auth/google/callback?code=abc&state={estado}")
    destino = r.headers["location"]
    assert "#/entrar?token=" in destino

    token = destino.split("token=")[1]
    h = {"Authorization": f"Bearer {token}"}
    yo = cliente.get("/api/yo", headers=h).json()
    assert yo["perfil"]["email"] == "vieraschiavi@gmail.com"
    assert yo["perfil"]["plan"] == "gold"

    a = backend.almacen()
    assert len([p for p in a.todos() if p.email == "vieraschiavi@gmail.com"]) == 1
    # Y la contraseña original sigue sirviendo.
    assert a.login("vieraschiavi@gmail.com", demo.CLAVE_DEMO) is not None


def test_cuenta_desactivada_no_entra(cliente, con_google, monkeypatch):
    a = backend.almacen()
    p = a.buscar_por_email("arcortito@gmail.com")
    p.activo = False
    a.guardar_perfil(p)

    simular_proveedor(monkeypatch, "arcortito@gmail.com")
    _, estado = oauth.url_de_autorizacion("google", "https://matcher.test")
    r = cliente.get(f"/api/auth/google/callback?code=abc&state={estado}")
    assert "error=cuenta_desactivada" in r.headers["location"]


# ---------------------------------------------------------------------------
# Datos del proveedor
# ---------------------------------------------------------------------------
def test_email_sin_verificar_se_rechaza(cliente, con_google, monkeypatch):
    """Aceptar un email sin verificar deja reclamar la cuenta de otra persona
    registrando ese email en el proveedor."""
    simular_proveedor(monkeypatch, "sinverificar@test.local", verificado=False)
    _, estado = oauth.url_de_autorizacion("google", "https://matcher.test")
    r = cliente.get(f"/api/auth/google/callback?code=abc&state={estado}")
    assert r.status_code == 400
    assert "verificado" in r.json()["detail"]


def test_proveedor_sin_email_se_rechaza(cliente, con_google, monkeypatch):
    simular_proveedor(monkeypatch, "")
    _, estado = oauth.url_de_autorizacion("google", "https://matcher.test")
    r = cliente.get(f"/api/auth/google/callback?code=abc&state={estado}")
    assert r.status_code == 400


def test_el_error_del_proveedor_no_filtra_el_secreto(monkeypatch, con_google):
    import urllib.error

    def explota(*a, **k):
        raise urllib.error.HTTPError("u", 401, "no", None, None)

    monkeypatch.setattr(oauth.urllib.request, "urlopen", explota)
    with pytest.raises(DatosInvalidos) as e:
        oauth.intercambiar_codigo("google", "codigo", "https://matcher.test")
    assert "secreto-de-prueba" not in str(e.value)


# ---------------------------------------------------------------------------
# Vuelta a la APP instalada (enlace profundo) vs. vuelta a la web
# ---------------------------------------------------------------------------
# El login desde el APK no puede volver a la web y ya se probó que no alcanza
# con que "funcione": el WebView de la app vive en otro origen, así que el
# token caía en el localStorage equivocado y la app seguía sin sesión. Y Google
# directamente rechaza el flujo dentro de un WebView embebido
# (`disallowed_useragent`), así que el navegador tiene que ser el del sistema.
#
# De ahí el `destino`: viaja firmado adentro del `state` y decide si la vuelta
# es una URL web o el enlace profundo `com.matcher.app://auth/...`.
def test_el_destino_app_vuelve_por_enlace_profundo(cliente, con_google, monkeypatch):
    simular_proveedor(monkeypatch, "vieraschiavi@gmail.com", "Martín")
    _, estado = oauth.url_de_autorizacion("google", "https://matcher.test", "app")
    r = cliente.get(f"/api/auth/google/callback?code=abc&state={estado}")
    destino = r.headers["location"]
    assert destino.startswith(f"{oauth.ESQUEMA_APP}://auth/entrar?token=")
    assert "matcher.test" not in destino, "el enlace de la app no puede apuntar a la web"


def test_el_destino_web_sigue_volviendo_a_la_web(cliente, con_google, monkeypatch):
    """El arreglo no puede romper el login del navegador, que es el que anda."""
    simular_proveedor(monkeypatch, "vieraschiavi@gmail.com", "Martín")
    _, estado = oauth.url_de_autorizacion("google", "https://matcher.test", "web")
    r = cliente.get(f"/api/auth/google/callback?code=abc&state={estado}")
    assert r.headers["location"].startswith("https://matcher.test/#/entrar?token=")


def test_el_alta_desde_la_app_tambien_vuelve_por_enlace_profundo(
    cliente, con_google, monkeypatch
):
    """El email nuevo manda a completar el alta. Si esa vuelta se fuera a la
    web, el usuario terminaría llenando el formulario en el navegador y la app
    quedaría esperando: el alta a medio hacer es justo donde más se nota."""
    simular_proveedor(monkeypatch, "nuevo@ejemplo.test", "Nuevo")
    _, estado = oauth.url_de_autorizacion("google", "https://matcher.test", "app")
    r = cliente.get(f"/api/auth/google/callback?code=abc&state={estado}")
    assert r.headers["location"].startswith(f"{oauth.ESQUEMA_APP}://auth/completar?alta=")


def test_un_destino_arbitrario_no_es_un_open_redirect():
    """El `destino` NUNCA se usa como URL. Si se aceptara una URL cualquiera,
    un atacante mandaría a la víctima a su propio sitio con el token de sesión
    en la query — que es el open redirect de manual."""
    for veneno in (
        "https://malicioso.example",
        "//malicioso.example",
        "javascript:alert(1)",
        "app.malicioso.example",
        "APP",
        "",
        None,
    ):
        url = oauth.url_de_vuelta("https://matcher.test", veneno, "/entrar", {"token": "x"})
        assert url.startswith("https://matcher.test/#/entrar"), f"se coló: {veneno!r}"
        assert "malicioso" not in url
        assert "javascript" not in url


def test_el_destino_no_se_puede_falsificar_desde_el_cliente(cliente, con_google, monkeypatch):
    """El destino viaja firmado. Mandarlo por query en el callback no lo cambia:
    lo único que manda es lo que se firmó al empezar el login."""
    simular_proveedor(monkeypatch, "vieraschiavi@gmail.com", "Martín")
    _, estado = oauth.url_de_autorizacion("google", "https://matcher.test", "web")
    r = cliente.get(f"/api/auth/google/callback?code=abc&state={estado}&destino=app")
    assert r.headers["location"].startswith("https://matcher.test/#/entrar")


def test_el_inicio_acepta_el_destino_por_query(cliente, con_google):
    """Es como lo pide la app: /api/auth/google/inicio?destino=app."""
    r = cliente.get("/api/auth/google/inicio?destino=app")
    assert r.status_code == 200
    # El `state` devuelto tiene que traer el destino adentro, ya normalizado.
    assert oauth.consumir_estado(r.json()["state"]) == oauth.DESTINO_APP
