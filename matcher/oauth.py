"""Login con proveedor externo (Google), como el resto de las apps de citas.

Flujo, que es el estándar OAuth 2.0 / OpenID Connect con *authorization code*:

  1. `url_de_autorizacion()` arma la URL del proveedor y el frontend redirige.
  2. El proveedor vuelve a `/api/auth/<proveedor>/callback?code=...&state=...`.
  3. `intercambiar_codigo()` cambia el código por un access token.
  4. `datos_del_usuario()` pregunta quién es al endpoint del proveedor.

Por qué se pregunta al proveedor en vez de leer el `id_token` localmente: el
`id_token` es un JWT firmado con RS256 y verificar esa firma exige una
biblioteca de criptografía. Preguntarle al proveedor por HTTPS con el access
token da los mismos datos, ya verificados, y mantiene el motor con sólo
biblioteca estándar. **Nunca leas el id_token sin verificar la firma**: un JWT
sin verificar es texto que manda el cliente.

El `state` es obligatorio y se valida: sin eso, cualquiera puede inducir un
login ajeno (CSRF sobre el callback). Los `state` son de un solo uso y vencen.
Van firmados (no guardados) porque el callback puede caer en otra instancia
que nunca vio arrancar el login — ver el comentario de `_CONSUMIDOS`.

Sin credenciales configuradas (`GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`),
`configurado()` devuelve False y la UI no muestra el botón. No hay modo
"simulado" que finja un login real: un login falso en producción es una puerta
abierta.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from . import seguridad
from .modelos import DatosInvalidos

# El `state` va FIRMADO, no guardado.
#
# Antes vivía en un dict del proceso. En serverless eso no funciona nunca: la
# instancia que arma la URL de autorización no es la misma que atiende el
# callback, así que el `state` no estaba y el login con Google fallaba SIEMPRE
# con "el login expiró". Firmado, cualquier instancia lo valida.
#
# Lo que sí sigue necesitando memoria es el "de un solo uso": acá se anotan los
# que ya se usaron, para no aceptar dos veces el mismo callback. Con varias
# instancias esa parte sólo vale dentro de cada una — un replay dentro de los
# 10 minutos podría colarse por otra instancia. Se acota con la vida corta;
# cerrarlo del todo pide un almacén compartido (Redis o una base con disco).
_CONSUMIDOS: dict[str, float] = {}
VIDA_ESTADO_SEG = 600

# ---------------------------------------------------------------------------
# A dónde vuelve el navegador cuando el proveedor terminó
# ---------------------------------------------------------------------------
#
# Hay DOS destinos posibles y ninguno más:
#
# - `web`: el navegador ya está en la web del backend, así que vuelve a una
#   ruta del propio sitio.
# - `app`: el login salió de la app instalada. Ahí volver a la web no sirve de
#   nada —la app vive en otro origen y nunca vería el token—, así que se vuelve
#   por un enlace profundo que el sistema operativo enruta a la app.
#
# Por qué el login de la app NO puede pasar por el WebView, que es como estaba:
# Google rechaza el flujo OAuth cuando detecta un navegador embebido y
# responde `disallowed_useragent`. Es política suya desde hace años y no se
# puede esquivar cambiando el user-agent (además de que hacerlo sería
# exactamente lo que la política busca impedir). El flujo tiene que abrirse en
# el navegador del sistema —Chrome Custom Tab en Android, SFSafariViewController
# en iOS— y volver por el enlace profundo.
#
# El esquema es el appId de Capacitor, que es único por app en la tienda.
ESQUEMA_APP = "com.matcher.app"
DESTINO_APP = "app"
DESTINO_WEB = "web"
DESTINOS = (DESTINO_WEB, DESTINO_APP)


def normalizar_destino(destino: str | None) -> str:
    """Cualquier cosa que no sea exactamente "app" es la web.

    Es una lista cerrada y no un parseo de URL a propósito: ver `url_de_vuelta`.
    """
    return DESTINO_APP if destino == DESTINO_APP else DESTINO_WEB


def url_de_vuelta(base: str, destino: str, ruta: str, parametros: dict) -> str:
    """La URL final del callback, ya con el token o el error adentro.

    **El `destino` nunca se usa como URL.** Viaja firmado dentro del `state`,
    así que el cliente no lo puede falsificar, pero igual se compara contra la
    lista cerrada de arriba y la URL se arma acá. Tomar una URL del parámetro y
    redirigir a ella sería un open redirect de manual: el atacante manda a la
    víctima a su propio sitio y se lleva el token de sesión en la query.
    """
    consulta = urllib.parse.urlencode(parametros)
    if normalizar_destino(destino) == DESTINO_APP:
        return f"{ESQUEMA_APP}://auth{ruta}?{consulta}"
    return f"{base.rstrip('/')}/#{ruta}?{consulta}"


@dataclass(frozen=True)
class Proveedor:
    nombre: str
    autorizacion: str
    token: str
    usuario: str
    alcance: str
    variable_id: str
    variable_secreto: str

    @property
    def client_id(self) -> str:
        return os.getenv(self.variable_id, "")

    @property
    def client_secret(self) -> str:
        return os.getenv(self.variable_secreto, "")

    @property
    def configurado(self) -> bool:
        return bool(self.client_id and self.client_secret)


PROVEEDORES: dict[str, Proveedor] = {
    "google": Proveedor(
        nombre="google",
        autorizacion="https://accounts.google.com/o/oauth2/v2/auth",
        token="https://oauth2.googleapis.com/token",
        usuario="https://openidconnect.googleapis.com/v1/userinfo",
        alcance="openid email profile",
        variable_id="GOOGLE_CLIENT_ID",
        variable_secreto="GOOGLE_CLIENT_SECRET",
    ),
    "facebook": Proveedor(
        nombre="facebook",
        autorizacion="https://www.facebook.com/v21.0/dialog/oauth",
        token="https://graph.facebook.com/v21.0/oauth/access_token",
        # Hay que pedir los campos explícitamente: el endpoint /me sin
        # `fields` devuelve sólo id y nombre, sin email, y el alta quedaba
        # trabada sin decir por qué.
        usuario="https://graph.facebook.com/v21.0/me?fields=id,name,first_name,email,picture",
        alcance="email public_profile",
        variable_id="FACEBOOK_APP_ID",
        variable_secreto="FACEBOOK_APP_SECRET",
    ),
}


def proveedor(nombre: str) -> Proveedor:
    p = PROVEEDORES.get(nombre)
    if not p:
        raise DatosInvalidos(f"proveedor de login desconocido: {nombre}")
    return p


def disponibles() -> list[str]:
    """Los que están realmente configurados. El frontend sólo muestra estos."""
    return [n for n, p in PROVEEDORES.items() if p.configurado]


def redirect_uri(base: str, nombre: str) -> str:
    return f"{base.rstrip('/')}/api/auth/{nombre}/callback"


def _limpiar_consumidos(ahora: float) -> None:
    for s, cuando in list(_CONSUMIDOS.items()):
        if ahora - cuando > VIDA_ESTADO_SEG:
            _CONSUMIDOS.pop(s, None)


def nuevo_estado(destino: str = DESTINO_WEB) -> str:
    _limpiar_consumidos(time.time())
    return seguridad.firmar_datos({"d": normalizar_destino(destino)})


def consumir_estado(s: str) -> str:
    """Valida y quema el `state`.

    De un solo uso: sin eso, un callback capturado se puede reproducir. Y
    obligatorio: sin `state` cualquiera induce un login ajeno (CSRF).
    """
    datos = seguridad.leer_datos(s or "", VIDA_ESTADO_SEG)
    if not datos:
        raise DatosInvalidos("el login expiró o el enlace ya se usó; probá de nuevo")
    ahora = time.time()
    _limpiar_consumidos(ahora)
    if s in _CONSUMIDOS:
        raise DatosInvalidos("el login expiró o el enlace ya se usó; probá de nuevo")
    _CONSUMIDOS[s] = ahora
    return normalizar_destino(datos.get("d"))


def url_de_autorizacion(
    nombre: str, base: str, destino: str = DESTINO_WEB
) -> tuple[str, str]:
    p = proveedor(nombre)
    if not p.configurado:
        raise DatosInvalidos(
            f"el login con {nombre} no está configurado "
            f"(faltan {p.variable_id} y {p.variable_secreto})"
        )
    estado = nuevo_estado(destino)
    parametros = {
        "client_id": p.client_id,
        "redirect_uri": redirect_uri(base, nombre),
        "response_type": "code",
        "scope": p.alcance,
        "state": estado,
        # `select_account` evita el caso molesto de quedar pegado a la sesión
        # de Google que el navegador ya tenía abierta.
        "prompt": "select_account",
    }
    return f"{p.autorizacion}?{urllib.parse.urlencode(parametros)}", estado


def _post(url: str, datos: dict) -> dict:
    cuerpo = urllib.parse.urlencode(datos).encode()
    pedido = urllib.request.Request(
        url, data=cuerpo, headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    try:
        with urllib.request.urlopen(pedido, timeout=15) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        # Nunca se propaga el cuerpo crudo del proveedor: puede traer el
        # client_secret reflejado en el mensaje de error.
        raise DatosInvalidos(f"el proveedor rechazó el login (HTTP {e.code})") from e
    except urllib.error.URLError as e:
        raise DatosInvalidos("no se pudo contactar al proveedor de login") from e


def _get(url: str, token_acceso: str) -> dict:
    pedido = urllib.request.Request(url, headers={"Authorization": f"Bearer {token_acceso}"})
    try:
        with urllib.request.urlopen(pedido, timeout=15) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise DatosInvalidos(f"no se pudo leer el perfil del proveedor (HTTP {e.code})") from e
    except urllib.error.URLError as e:
        raise DatosInvalidos("no se pudo contactar al proveedor de login") from e


def intercambiar_codigo(nombre: str, codigo: str, base: str) -> str:
    p = proveedor(nombre)
    respuesta = _post(
        p.token,
        {
            "code": codigo,
            "client_id": p.client_id,
            "client_secret": p.client_secret,
            "redirect_uri": redirect_uri(base, nombre),
            "grant_type": "authorization_code",
        },
    )
    token = respuesta.get("access_token")
    if not token:
        raise DatosInvalidos("el proveedor no devolvió un token de acceso")
    return token


def datos_del_usuario(nombre: str, token_acceso: str) -> dict:
    """Email verificado, nombre y foto. Todo lo demás lo completa el usuario.

    Se exige `email_verified`: aceptar un email sin verificar permite reclamar
    la cuenta de otra persona registrando ese email en el proveedor.
    """
    p = proveedor(nombre)
    datos = _get(p.usuario, token_acceso)
    email = (datos.get("email") or "").strip().lower()
    if not email:
        # Facebook permite cuentas sin email (alta por teléfono) y además el
        # usuario puede desmarcar el permiso en la pantalla de consentimiento.
        # Sin email no hay forma de identificar la cuenta, así que se corta
        # con un mensaje que explique qué hacer.
        raise DatosInvalidos(
            "el proveedor no compartió un email. Revisá que la cuenta tenga uno "
            "y que hayas aceptado compartirlo, o entrá con email y contraseña."
        )
    if datos.get("email_verified") is False:
        raise DatosInvalidos("ese email no está verificado en el proveedor")

    # La foto viene plana en Google y anidada en Facebook
    # (`picture.data.url`). Normalizar acá evita que cada proveedor nuevo
    # obligue a tocar el backend.
    foto = datos.get("picture") or ""
    if isinstance(foto, dict):
        foto = foto.get("data", {}).get("url", "")

    return {
        "email": email,
        "nombre": (datos.get("given_name") or datos.get("first_name") or datos.get("name") or "").strip(),
        "foto": foto,
        "proveedor": nombre,
    }
