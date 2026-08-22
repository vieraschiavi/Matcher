"""Contraseñas y tokens de sesión.

PBKDF2-HMAC-SHA256 de la biblioteca estándar. No es argon2, pero con 260.000
iteraciones y sal por usuario alcanza para el MVP y evita meter una dependencia
nativa que rompe el empaquetado del APK. Si esto se pone en producción con
usuarios reales, migrar a argon2id — el formato del hash ya lleva el algoritmo
adelante justamente para poder rotarlo sin invalidar las cuentas viejas.

Nunca se loguea ni se serializa un hash ni un token. El almacén los guarda,
la API devuelve el token una sola vez, y listo.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

ITERACIONES = 260_000
ALGORITMO = "pbkdf2_sha256"

# Vida de una sesión firmada. Larga a propósito: es una app de citas, no un
# home banking, y que te eche cada media hora es motivo de desinstalación.
VIDA_SESION_SEG = 30 * 24 * 3600

# Clave de respaldo, al azar y distinta en cada proceso. NO hay un valor por
# defecto fijo: un secreto cableado en un repo público deja que cualquiera se
# firme una sesión de cualquier usuario.
_SECRETO_PROCESO = secrets.token_bytes(32)


# Hash de una contraseña que no es de nadie. Se verifica contra éste cuando el
# email no existe, para que errar el mail cueste lo mismo que errar la clave.
# Ver `Almacen.login`. Se calcula una vez, al importar: hacerlo en cada intento
# fallido costaría el doble de PBKDF2 que un intento normal, y esa diferencia
# también se mide con un cronómetro.
HASH_DE_DESCARTE = (
    f"{ALGORITMO}${ITERACIONES}$"
    + "00" * 16
    + "$"
    + hashlib.pbkdf2_hmac("sha256", secrets.token_bytes(32), bytes(16), ITERACIONES).hex()
)


def hashear(clave: str) -> str:
    if len(clave or "") < 8:
        raise ValueError("la contraseña tiene que tener al menos 8 caracteres")
    sal = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", clave.encode(), bytes.fromhex(sal), ITERACIONES)
    return f"{ALGORITMO}${ITERACIONES}${sal}${dk.hex()}"


def verificar(clave: str, guardado: str) -> bool:
    try:
        algoritmo, iteraciones, sal, esperado = guardado.split("$")
        if algoritmo != ALGORITMO:
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", (clave or "").encode(), bytes.fromhex(sal), int(iteraciones)
        )
    except (ValueError, AttributeError):
        return False
    # compare_digest y no ==: comparar hashes con == filtra información por
    # tiempo de respuesta.
    return hmac.compare_digest(dk.hex(), esperado)


def nuevo_token() -> str:
    return secrets.token_urlsafe(32)


# ---------------------------------------------------------------------------
# Sesiones firmadas
# ---------------------------------------------------------------------------
# Por qué existen, además de la tabla `sesiones`:
#
# En serverless (Vercel) cada instancia tiene su propio disco efímero y, por
# lo tanto, su propia base. Con la sesión guardada SÓLO en la base, el token
# que emitió una instancia no existe en la de al lado: medían 401 el 40% de
# los pedidos y la app quedaba colgada en "Cargando…" sin decir por qué. Con
# el token firmado, cualquier instancia puede validarlo sin compartir estado.
#
# La tabla `sesiones` se sigue escribiendo: donde el disco es de verdad, es la
# que permite revocar (ver `Almacen.logout`).


def secreto_compartido() -> bool:
    """True si hay un secreto estable entre procesos (`MATCHER_SECRETO`).

    Sin él las firmas siguen siendo válidas, pero sólo dentro del proceso que
    las emitió — que es justo lo que no alcanza en serverless.
    """
    return bool(os.getenv("MATCHER_SECRETO", "").strip())


def _secreto() -> bytes:
    valor = os.getenv("MATCHER_SECRETO", "").strip()
    return valor.encode() if valor else _SECRETO_PROCESO


def _b64(crudo: bytes) -> str:
    return base64.urlsafe_b64encode(crudo).decode().rstrip("=")


def _des64(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def firmar_datos(datos: dict, ahora: float | None = None) -> str:
    """Firma un diccionario y le pone fecha de emisión.

    El resultado es `<cuerpo>.<firma>`, ambos base64url. El cuerpo **no está
    cifrado**, sólo firmado: no metas nada secreto adentro.

    El `n` al azar hace que dos tokens del mismo contenido en el mismo segundo
    salgan distintos (si no, dos logins simultáneos daban el mismo token y
    cerrar uno cerraba el otro).
    """
    cuerpo = _b64(
        json.dumps(
            {**datos, "n": secrets.token_urlsafe(9), "t": int(time.time() if ahora is None else ahora)},
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    )
    firma = hmac.new(_secreto(), cuerpo.encode(), hashlib.sha256).digest()
    return f"{cuerpo}.{_b64(firma)}"


def leer_datos(token: str, vida_seg: int, ahora: float | None = None) -> dict | None:
    """Verifica firma y vencimiento y devuelve el contenido; None si no valen.

    Nunca leas el cuerpo antes de verificar la firma: es base64 que manda el
    cliente, y sin verificar es tan confiable como un parámetro de la URL.
    """
    partes = (token or "").split(".")
    if len(partes) != 2:
        return None
    cuerpo, firma = partes
    esperada = _b64(hmac.new(_secreto(), cuerpo.encode(), hashlib.sha256).digest())
    # compare_digest y no ==: comparar firmas con == filtra información por
    # tiempo de respuesta.
    if not hmac.compare_digest(firma, esperada):
        return None
    try:
        datos = json.loads(_des64(cuerpo))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(datos, dict):
        return None
    emitido = datos.get("t")
    if not isinstance(emitido, int):
        return None
    if (time.time() if ahora is None else ahora) - emitido > vida_seg:
        return None
    return datos


def firmar_sesion(usuario_id: str, ahora: float | None = None) -> str:
    return firmar_datos({"u": usuario_id}, ahora=ahora)


def leer_sesion(token: str, ahora: float | None = None) -> str | None:
    """Devuelve el `usuario_id` si la firma es válida y no venció; si no, None."""
    datos = leer_datos(token, VIDA_SESION_SEG, ahora=ahora)
    if not datos:
        return None
    usuario = datos.get("u")
    return usuario if isinstance(usuario, str) and usuario else None
