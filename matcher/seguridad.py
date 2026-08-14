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

import hashlib
import hmac
import secrets

ITERACIONES = 260_000
ALGORITMO = "pbkdf2_sha256"


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
