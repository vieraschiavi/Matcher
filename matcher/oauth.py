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

Sin credenciales configuradas (`GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`),
`configurado()` devuelve False y la UI no muestra el botón. No hay modo
"simulado" que finja un login real: un login falso en producción es una puerta
abierta.
"""

from __future__ import annotations

import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .modelos import DatosInvalidos

# Los `state` viven en memoria del proceso: son de segundos y de un solo uso.
# Con varios workers hay que moverlos a la base o a un caché compartido.
_ESTADOS: dict[str, tuple[float, str]] = {}
VIDA_ESTADO_SEG = 600


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


def _limpiar_estados(ahora: float) -> None:
    for s, (creado, _) in list(_ESTADOS.items()):
        if ahora - creado > VIDA_ESTADO_SEG:
            _ESTADOS.pop(s, None)


def nuevo_estado(destino: str = "/") -> str:
    ahora = time.time()
    _limpiar_estados(ahora)
    s = secrets.token_urlsafe(24)
    _ESTADOS[s] = (ahora, destino)
    return s


def consumir_estado(s: str) -> str:
    """Valida y quema el `state`. De un solo uso: si se pudiera reusar, se
    puede reproducir un callback capturado."""
    dato = _ESTADOS.pop(s or "", None)
    if not dato:
        raise DatosInvalidos("el login expiró o el enlace ya se usó; probá de nuevo")
    creado, destino = dato
    if time.time() - creado > VIDA_ESTADO_SEG:
        raise DatosInvalidos("el login expiró; probá de nuevo")
    return destino


def url_de_autorizacion(nombre: str, base: str, destino: str = "/") -> tuple[str, str]:
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
        raise DatosInvalidos("el proveedor no compartió un email")
    if datos.get("email_verified") is False:
        raise DatosInvalidos("ese email no está verificado en el proveedor")
    return {
        "email": email,
        "nombre": (datos.get("given_name") or datos.get("name") or "").strip(),
        "foto": datos.get("picture") or "",
        "proveedor": nombre,
    }
