"""Sesiones firmadas.

Estos tests existen por una regresión concreta y cara: desplegado en Vercel,
cada instancia serverless tiene su propio disco efímero y por lo tanto su
propia base. Con la sesión guardada SÓLO en la tabla `sesiones`, el token que
emitía una instancia no existía en la de al lado y ~40% de los pedidos volvían
401. La app no mostraba el error: se quedaba en "Cargando…" y parecía rota.

Lo que se fija acá:
  - un token válido en una base sirve en OTRA base (el caso serverless);
  - la firma no se puede falsificar sin el secreto;
  - el logout sigue cerrando la sesión de verdad (si no, no sería un logout).
"""

from __future__ import annotations

import time

import pytest

from matcher import seguridad
from matcher.almacen import Almacen


@pytest.fixture(autouse=True)
def secreto_fijo(monkeypatch):
    """Un secreto estable, como el que hay que configurar en producción."""
    monkeypatch.setenv("MATCHER_SECRETO", "secreto-compartido-de-prueba")


# ---------------------------------------------------------------------------
# La firma
# ---------------------------------------------------------------------------
def test_un_token_firmado_se_puede_leer():
    token = seguridad.firmar_sesion("usuario-1")
    assert seguridad.leer_sesion(token) == "usuario-1"


def test_dos_sesiones_del_mismo_usuario_dan_tokens_distintos():
    # Sin el `n` al azar, dos logins en el mismo segundo daban el mismo token
    # y cerrar uno cerraba el otro.
    a = seguridad.firmar_sesion("usuario-1")
    b = seguridad.firmar_sesion("usuario-1")
    assert a != b


@pytest.mark.parametrize(
    "token",
    ["", "cualquier-cosa", "a.b", "sin-punto-ninguno", "....", "eyJ1IjoieCJ9.firma-inventada"],
)
def test_un_token_sin_firma_valida_no_sirve(token):
    assert seguridad.leer_sesion(token) is None


def test_no_se_puede_cambiar_el_usuario_del_token():
    """El cuerpo es base64, no está cifrado: si la firma no se verificara,
    cualquiera se haría pasar por otro editando el payload."""
    import base64
    import json

    token = seguridad.firmar_sesion("usuario-1")
    _, firma = token.split(".")
    falsificado = (
        base64.urlsafe_b64encode(json.dumps({"u": "admin", "n": "x", "t": int(time.time())}).encode())
        .decode()
        .rstrip("=")
    )
    assert seguridad.leer_sesion(f"{falsificado}.{firma}") is None


def test_un_token_vencido_no_sirve():
    token = seguridad.firmar_sesion("usuario-1")
    futuro = time.time() + seguridad.VIDA_SESION_SEG + 60
    assert seguridad.leer_sesion(token, ahora=futuro) is None


def test_con_otro_secreto_la_firma_no_vale(monkeypatch):
    token = seguridad.firmar_sesion("usuario-1")
    monkeypatch.setenv("MATCHER_SECRETO", "un-secreto-distinto")
    assert seguridad.leer_sesion(token) is None


def test_sin_variable_configurada_se_avisa(monkeypatch):
    monkeypatch.delenv("MATCHER_SECRETO", raising=False)
    assert seguridad.secreto_compartido() is False
    # Y aun así firma: dentro del proceso la sesión funciona igual.
    assert seguridad.leer_sesion(seguridad.firmar_sesion("u")) == "u"


# ---------------------------------------------------------------------------
# El caso que motivó todo: dos instancias, dos bases
# ---------------------------------------------------------------------------
def test_la_sesion_sobrevive_a_una_instancia_con_otra_base(hacer_perfil):
    """El token emitido por una instancia tiene que valer en la siguiente.

    Es literalmente lo que pasa en serverless: la instancia B nunca vio el
    login, arranca con la base recién sembrada y le llega el token igual.
    """
    perfil = hacer_perfil(id="mismo-id", email="a@test.local")

    instancia_a = Almacen(":memory:")
    instancia_a.crear_perfil(perfil, "clave-larga-1")
    _, token = instancia_a.login("a@test.local", "clave-larga-1")

    instancia_b = Almacen(":memory:")  # otra base, sin la tabla de sesiones poblada
    instancia_b.crear_perfil(hacer_perfil(id="mismo-id", email="a@test.local"), "clave-larga-1")

    assert instancia_b.por_token(token) is not None
    assert instancia_b.por_token(token).id == "mismo-id"

    instancia_a.cerrar()
    instancia_b.cerrar()


def test_un_token_inventado_no_entra_en_ninguna_instancia(almacen, hacer_perfil):
    almacen.crear_perfil(hacer_perfil(id="x1", email="x@test.local"), "clave-larga-1")
    assert almacen.por_token("token.inventado") is None
    # Firmado bien pero de un usuario que no existe: tampoco.
    assert almacen.por_token(seguridad.firmar_sesion("no-existe")) is None


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------
def test_el_logout_cierra_la_sesion_aunque_el_token_este_firmado(almacen, hacer_perfil):
    """Con el token firmado, borrar la fila no alcanza: `por_token` lo
    aceptaría por la firma. Por eso hay lista de revocados."""
    almacen.crear_perfil(hacer_perfil(id="y1", email="y@test.local"), "clave-larga-1")
    _, token = almacen.login("y@test.local", "clave-larga-1")
    assert almacen.por_token(token) is not None

    almacen.logout(token)
    assert almacen.por_token(token) is None


def test_el_logout_no_cierra_las_otras_sesiones(almacen, hacer_perfil):
    almacen.crear_perfil(hacer_perfil(id="z1", email="z@test.local"), "clave-larga-1")
    _, telefono = almacen.login("z@test.local", "clave-larga-1")
    _, navegador = almacen.login("z@test.local", "clave-larga-1")

    almacen.logout(telefono)
    assert almacen.por_token(telefono) is None
    assert almacen.por_token(navegador) is not None


# ---------------------------------------------------------------------------
# El login con proveedor, que tenía el mismo problema en dos lugares más
# ---------------------------------------------------------------------------
def test_el_state_de_oauth_vale_en_otra_instancia(monkeypatch):
    """El `state` se emitía en un dict del proceso.

    En serverless la instancia que arma la URL de Google no es la que atiende
    el callback, así que el login fallaba SIEMPRE con "el login expiró".
    """
    from matcher import oauth

    # El `destino` es una lista cerrada ("web"/"app"), no una ruta libre: la
    # ruta libre nunca se usó y era la forma de un open redirect. Lo que este
    # test fija es otra cosa: que el estado firmado se lea en otra instancia.
    estado = oauth.nuevo_estado(oauth.DESTINO_APP)
    # Otra instancia: proceso nuevo, memoria vacía.
    monkeypatch.setattr(oauth, "_CONSUMIDOS", {})
    assert oauth.consumir_estado(estado) == oauth.DESTINO_APP


def test_el_state_sigue_siendo_de_un_solo_uso():
    from matcher import oauth
    from matcher.modelos import DatosInvalidos

    estado = oauth.nuevo_estado(oauth.DESTINO_WEB)
    assert oauth.consumir_estado(estado) == oauth.DESTINO_WEB
    with pytest.raises(DatosInvalidos):
        oauth.consumir_estado(estado)


def test_un_state_inventado_se_rechaza():
    from matcher import oauth
    from matcher.modelos import DatosInvalidos

    for basura in ["", "inventado", "a.b"]:
        with pytest.raises(DatosInvalidos):
            oauth.consumir_estado(basura)


def test_un_state_vencido_se_rechaza(monkeypatch):
    from matcher import oauth
    from matcher.modelos import DatosInvalidos

    estado = oauth.nuevo_estado("/")
    ahora = time.time()
    monkeypatch.setattr(time, "time", lambda: ahora + oauth.VIDA_ESTADO_SEG + 60)
    with pytest.raises(DatosInvalidos):
        oauth.consumir_estado(estado)


def test_el_alta_pendiente_vale_en_otra_instancia(hacer_perfil):
    """El callback guarda el alta en una instancia y la pantalla de
    "completar" le pega a otra, que no tiene la fila."""
    a = Almacen(":memory:")
    token = a.guardar_alta_pendiente("google", "Nueva@Test.local", "Ana", "http://f/1.png")

    b = Almacen(":memory:")  # otra base, sin la fila
    leido = b.leer_alta_pendiente(token)
    assert leido is not None
    assert leido["email"] == "nueva@test.local"
    assert leido["nombre"] == "Ana"
    assert leido["proveedor"] == "google"

    assert b.leer_alta_pendiente("token.inventado") is None
    a.cerrar()
    b.cerrar()


# ---------------------------------------------------------------------------
# Almacenamiento efímero: la app tiene que saber que lo es
# ---------------------------------------------------------------------------
# Medido contra el despliegue serverless: con una cuenta recién creada, de 40
# pedidos en paralelo 25 volvieron 401. La firma era válida — lo que faltaba
# era el PERFIL, porque cada instancia resiembra su propia base y una cuenta
# real no está en la semilla. Las fotos subidas "desaparecen" por lo mismo.
#
# No hay arreglo del lado de la sesión: necesita disco compartido. Lo que sí
# se puede es no mentirle al usuario, y para eso el servidor tiene que saber
# en qué está parado.
def test_una_base_en_tmp_se_declara_efimera(monkeypatch):
    from webapp.backend import api as backend

    monkeypatch.delenv("MATCHER_EFIMERO", raising=False)
    monkeypatch.setattr(backend, "RUTA_BD", "/tmp/matcher.db")
    assert backend.almacenamiento_efimero() is True


def test_una_base_con_disco_no_es_efimera(monkeypatch):
    from webapp.backend import api as backend

    monkeypatch.delenv("MATCHER_EFIMERO", raising=False)
    monkeypatch.setattr(backend, "RUTA_BD", "/datos/matcher.db")
    assert backend.almacenamiento_efimero() is False


def test_se_puede_forzar_con_la_variable(monkeypatch):
    """Por si /tmp está montado sobre un disco de verdad."""
    from webapp.backend import api as backend

    monkeypatch.setattr(backend, "RUTA_BD", "/tmp/matcher.db")
    monkeypatch.setenv("MATCHER_EFIMERO", "0")
    assert backend.almacenamiento_efimero() is False


def test_salud_reporta_el_almacenamiento(cliente):
    r = cliente.get("/api/salud").json()
    assert "almacenamiento_efimero" in r
    assert isinstance(r["almacenamiento_efimero"], bool)
