"""Videollamada dentro del match: conocerse por cámara antes de verse en persona.

El paso que falta en todas las apps de la categoría. Tinder tiene Face to Face
(sólo su propia sala), Bumble tiene su videochat propio, Grindr y Kismia no
tienen nada: en todos los casos, si querés usar Meet, Zoom o Webex —lo que la
gente YA tiene instalado y sabe usar— hay que pasarse el link por el chat, y
pasar un link por el chat es exactamente el momento donde entran las estafas.

Acá el link es un objeto del match, no un mensaje suelto, y de ahí salen las
cuatro reglas:

1. **Los dos tienen que aceptar antes de que el link exista para nadie.** Una
   videollamada muestra tu cara, tu casa y tu voz: no puede empezar porque el
   otro apretó un botón. Mientras la propuesta está pendiente, el servidor
   manda `enlace: null` — no lo manda y lo tapa el cliente (regla 9), no lo
   manda.
2. **En una cita a ciegas sin revelar, no hay videollamada.** Sería la fuga
   más obvia posible del feature: la cara que `aciegas.py` se cuida de no
   mandar, entregada por cámara. Se bloquea en el servidor.
3. **Honestidad sobre qué puede crear la app y qué no** (regla 10). Jitsi Meet
   abre una sala con sólo inventar un nombre, sin cuenta de nadie: esa la crea
   Matcher. Meet, Zoom y Webex **no** se pueden crear sin las APIs de Google,
   Zoom y Cisco y una cuenta de organización pagando: para esos, la app pide
   el link que la persona ya generó en su propia cuenta. La UI lo dice con
   todas las letras; no se promete una sala de Meet que la app no puede crear.
4. **El link pegado se valida contra el dominio del proveedor.** Si no,
   "proponer una videollamada de Zoom" es un canal bendecido por la app para
   mandar cualquier URL, que es phishing con el sello de la casa.

El nombre de la sala de Jitsi sale de `secrets.token_urlsafe`: una sala
adivinable es una sala donde se te puede meter un tercero, y Jitsi sin cuenta
no tiene puerta.
"""

from __future__ import annotations

import secrets
import urllib.parse
import uuid
from datetime import datetime, timedelta

from .modelos import DatosInvalidos, Perfil

# Una propuesta sin responder no puede bloquear el match para siempre: a las
# 48 horas se considera vencida y se puede proponer de nuevo.
VIDA_PROPUESTA = timedelta(hours=48)

PENDIENTE = "pendiente"
ACEPTADA = "aceptada"
RECHAZADA = "rechazada"
CANCELADA = "cancelada"

# `crea_sala`: si Matcher puede generar la sala solo. Es el campo que sostiene
# la regla 10 — la UI muestra "la creamos nosotros" o "pegá tu link" según
# esto, y no al revés.
PROVEEDORES = {
    "jitsi": {
        "nombre": "Jitsi Meet",
        "crea_sala": True,
        "dominios": ("meet.jit.si",),
        "nota": "Sala creada por Matcher. No hace falta cuenta ni instalar nada.",
    },
    "meet": {
        "nombre": "Google Meet",
        "crea_sala": False,
        "dominios": ("meet.google.com",),
        "nota": "Creá la reunión en Google Meet y pegá el link acá.",
    },
    "zoom": {
        "nombre": "Zoom",
        "crea_sala": False,
        "dominios": ("zoom.us",),
        "nota": "Creá la reunión en Zoom y pegá el link acá.",
    },
    "webex": {
        "nombre": "Webex",
        "crea_sala": False,
        "dominios": ("webex.com",),
        "nota": "Creá la reunión en Webex y pegá el link acá.",
    },
}


def catalogo() -> list[dict]:
    """Lo que ve la pantalla al elegir proveedor, con la verdad de cada uno."""
    return [
        {
            "codigo": codigo,
            "nombre": p["nombre"],
            "crea_sala": p["crea_sala"],
            "nota": p["nota"],
            "dominios": list(p["dominios"]),
        }
        for codigo, p in PROVEEDORES.items()
    ]


def _validar_enlace(proveedor: str, enlace: str) -> str:
    """El link pegado tiene que ser https y del dominio del proveedor.

    `endswith("." + dominio)` y no `in`: `meet.google.com.sitio-trucho.net`
    contiene el dominio bueno y no es el dominio bueno. Es el clásico, y por
    eso la comparación es sobre el host parseado y anclada al final.
    """
    enlace = (enlace or "").strip()
    if not enlace:
        raise DatosInvalidos("falta el link de la reunión")
    if len(enlace) > 500:
        raise DatosInvalidos("ese link es demasiado largo")
    partes = urllib.parse.urlsplit(enlace)
    if partes.scheme != "https":
        raise DatosInvalidos("el link tiene que empezar con https://")
    host = (partes.hostname or "").lower()
    permitidos = PROVEEDORES[proveedor]["dominios"]
    if not any(host == d or host.endswith("." + d) for d in permitidos):
        raise DatosInvalidos(
            f"ese link no es de {PROVEEDORES[proveedor]['nombre']} "
            f"(tiene que ser de {' o '.join(permitidos)})"
        )
    return enlace


def _sala_jitsi() -> tuple[str, str]:
    """Nombre de sala imposible de adivinar + su URL.

    El prefijo `matcher-` es sólo para reconocerla; la seguridad la da el
    token, porque una sala de Jitsi sin cuenta la abre cualquiera que sepa
    el nombre.
    """
    sala = f"matcher-{secrets.token_urlsafe(16)}"
    return sala, f"https://meet.jit.si/{sala}"


def _fila(almacen, llamada_id: str):
    return almacen.con.execute(
        "SELECT * FROM videollamadas WHERE id = ?", (llamada_id,)
    ).fetchone()


def _vencida(fila, ahora: datetime) -> bool:
    return datetime.fromisoformat(fila["momento"]) + VIDA_PROPUESTA < ahora


def _a_dict(fila, mi_id: str, ahora: datetime) -> dict:
    """La forma que viaja al cliente.

    `enlace` sólo sale si la llamada está ACEPTADA. Es la regla 1 de este
    módulo hecha código: el que propone tampoco lo ve antes, porque si lo
    viera podría copiarlo al chat y saltearse el consentimiento del otro.
    """
    aceptada = fila["estado"] == ACEPTADA
    return {
        "id": fila["id"],
        "match_id": fila["match_id"],
        "proveedor": fila["proveedor"],
        "proveedor_nombre": PROVEEDORES.get(fila["proveedor"], {}).get(
            "nombre", fila["proveedor"]
        ),
        "estado": fila["estado"],
        "mia": fila["de_id"] == mi_id,
        "momento": fila["momento"],
        "cuando": fila["cuando"],
        "vencida": fila["estado"] == PENDIENTE and _vencida(fila, ahora),
        "enlace": fila["enlace"] if aceptada else None,
    }


def _abierta(almacen, match_id: str, ahora: datetime):
    """La propuesta viva del match, si hay: pendiente sin vencer, o aceptada."""
    filas = almacen.con.execute(
        "SELECT * FROM videollamadas WHERE match_id = ? ORDER BY momento DESC",
        (match_id,),
    ).fetchall()
    for f in filas:
        if f["estado"] == ACEPTADA:
            return f
        if f["estado"] == PENDIENTE and not _vencida(f, ahora):
            return f
    return None


def _match_apto(almacen, perfil: Perfil, match_id: str):
    """El match existe, es mío, y no es una cita a ciegas sin revelar."""
    fila = almacen._match_de(match_id, perfil.id)
    es_ciego = bool(fila["ciego"]) if "ciego" in fila.keys() else False
    if es_ciego:
        from . import aciegas

        if not aciegas.estado(almacen, match_id, perfil.id)["revelado"]:
            raise DatosInvalidos(
                "en una cita a ciegas la videollamada se destraba recién cuando "
                "se revelan las fotos: escribí un poco más"
            )
    return fila


def estado(almacen, perfil: Perfil, match_id: str, ahora: datetime | None = None) -> dict:
    """Qué mostrar en el chat: la llamada viva (si hay) y el catálogo."""
    ahora = ahora or datetime.utcnow()
    almacen._match_de(match_id, perfil.id)
    try:
        _match_apto(almacen, perfil, match_id)
        disponible, motivo = True, ""
    except DatosInvalidos as e:
        disponible, motivo = False, str(e)
    viva = _abierta(almacen, match_id, ahora) if disponible else None
    return {
        "disponible": disponible,
        "motivo": motivo,
        "llamada": _a_dict(viva, perfil.id, ahora) if viva else None,
        "proveedores": catalogo(),
    }


def proponer(
    almacen,
    perfil: Perfil,
    match_id: str,
    proveedor: str,
    enlace: str = "",
    cuando: str = "",
    ahora: datetime | None = None,
) -> dict:
    ahora = ahora or datetime.utcnow()
    _match_apto(almacen, perfil, match_id)

    if proveedor not in PROVEEDORES:
        raise DatosInvalidos(
            f"proveedor desconocido: elegí uno de {', '.join(PROVEEDORES)}"
        )
    if _abierta(almacen, match_id, ahora):
        raise DatosInvalidos(
            "ya hay una videollamada propuesta en este chat; resolvela o "
            "cancelala antes de proponer otra"
        )

    if PROVEEDORES[proveedor]["crea_sala"]:
        sala, url = _sala_jitsi()
    else:
        sala, url = "", _validar_enlace(proveedor, enlace)

    cuando = (cuando or "").strip()[:60]
    llamada_id = uuid.uuid4().hex[:16]
    almacen.con.execute(
        "INSERT INTO videollamadas "
        "(id, match_id, de_id, proveedor, enlace, sala, estado, cuando, momento, resuelto) "
        "VALUES (?,?,?,?,?,?,?,?,?,'')",
        (llamada_id, match_id, perfil.id, proveedor, url, sala, PENDIENTE, cuando,
         ahora.isoformat()),
    )
    almacen.con.commit()
    return _a_dict(_fila(almacen, llamada_id), perfil.id, ahora)


def responder(
    almacen,
    perfil: Perfil,
    llamada_id: str,
    acepta: bool,
    ahora: datetime | None = None,
) -> dict:
    """Aceptar o rechazar. Sólo la contraparte: aceptar la propia propuesta
    sería el consentimiento de una sola persona, que es justo lo que este
    módulo existe para impedir."""
    ahora = ahora or datetime.utcnow()
    fila = _fila(almacen, llamada_id)
    if not fila:
        raise DatosInvalidos("esa videollamada no existe")
    almacen._match_de(fila["match_id"], perfil.id)
    if fila["de_id"] == perfil.id:
        raise DatosInvalidos("la videollamada la tiene que aceptar la otra persona")
    if fila["estado"] != PENDIENTE:
        raise DatosInvalidos("esa propuesta ya está resuelta")
    if _vencida(fila, ahora):
        raise DatosInvalidos("esa propuesta venció; pedile que la proponga de nuevo")

    almacen.con.execute(
        "UPDATE videollamadas SET estado = ?, resuelto = ? WHERE id = ?",
        (ACEPTADA if acepta else RECHAZADA, ahora.isoformat(), llamada_id),
    )
    almacen.con.commit()
    return _a_dict(_fila(almacen, llamada_id), perfil.id, ahora)


def cancelar(
    almacen, perfil: Perfil, llamada_id: str, ahora: datetime | None = None
) -> dict:
    """Cualquiera de los dos corta, en cualquier momento, incluso ya aceptada.

    Que se pueda cancelar DESPUÉS de aceptar no es un detalle: alguien se
    puede arrepentir entre que dijo que sí y la hora de la llamada, y sin este
    botón la única salida sería deshacer el match entero.
    """
    ahora = ahora or datetime.utcnow()
    fila = _fila(almacen, llamada_id)
    if not fila:
        raise DatosInvalidos("esa videollamada no existe")
    almacen._match_de(fila["match_id"], perfil.id)
    if fila["estado"] in (RECHAZADA, CANCELADA):
        raise DatosInvalidos("esa propuesta ya estaba cerrada")
    almacen.con.execute(
        "UPDATE videollamadas SET estado = ?, resuelto = ? WHERE id = ?",
        (CANCELADA, ahora.isoformat(), llamada_id),
    )
    almacen.con.commit()
    return _a_dict(_fila(almacen, llamada_id), perfil.id, ahora)
