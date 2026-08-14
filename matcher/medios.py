"""Fotos y videos del perfil: validación y orden.

Reglas del producto: hasta 10 fotos y 2 videos cortos por usuario. Se validan
acá y no en el backend porque el mismo límite tiene que valer para el alta por
API, para el seed de la demo y para cualquier importador futuro. Un límite que
vive sólo en el handler HTTP se saltea el primer día.
"""

from __future__ import annotations

import uuid

from .modelos import (
    MAX_FOTOS,
    MAX_SEGUNDOS_VIDEO,
    MAX_VIDEOS,
    DatosInvalidos,
    Media,
    Perfil,
)

FORMATOS_FOTO = (".jpg", ".jpeg", ".png", ".webp", ".heic")
FORMATOS_VIDEO = (".mp4", ".mov", ".webm")

# 8 MB por foto, 40 MB por video. No es una restricción técnica sino de
# experiencia: arriba de eso la tarjeta tarda en pintar en 4G y el usuario
# desliza antes de ver la foto.
MAX_BYTES_FOTO = 8 * 1024 * 1024
MAX_BYTES_VIDEO = 40 * 1024 * 1024


def _extension_valida(url: str, formatos: tuple[str, ...]) -> bool:
    limpio = url.split("?")[0].lower()
    if limpio.startswith("data:"):
        return True  # data-URI de la demo; el tipo va en el propio prefijo
    return limpio.endswith(formatos)


def agregar_foto(perfil: Perfil, url: str, *, bytes_: int | None = None) -> Media:
    if len(perfil.fotos) >= MAX_FOTOS:
        raise DatosInvalidos(f"ya tenés {MAX_FOTOS} fotos; borrá una para subir otra")
    if not _extension_valida(url, FORMATOS_FOTO):
        raise DatosInvalidos(f"formato de foto no soportado ({', '.join(FORMATOS_FOTO)})")
    if bytes_ is not None and bytes_ > MAX_BYTES_FOTO:
        raise DatosInvalidos("la foto pesa más de 8 MB")
    media = Media(id=uuid.uuid4().hex[:12], tipo="foto", url=url, orden=len(perfil.fotos))
    perfil.fotos.append(media)
    return media


def agregar_video(
    perfil: Perfil, url: str, *, segundos: float | None = None, bytes_: int | None = None
) -> Media:
    if len(perfil.videos) >= MAX_VIDEOS:
        raise DatosInvalidos(f"ya tenés {MAX_VIDEOS} videos; borrá uno para subir otro")
    if not _extension_valida(url, FORMATOS_VIDEO):
        raise DatosInvalidos(f"formato de video no soportado ({', '.join(FORMATOS_VIDEO)})")
    if segundos is not None and segundos > MAX_SEGUNDOS_VIDEO:
        raise DatosInvalidos(f"el video no puede pasar de {MAX_SEGUNDOS_VIDEO} segundos")
    if bytes_ is not None and bytes_ > MAX_BYTES_VIDEO:
        raise DatosInvalidos("el video pesa más de 40 MB")
    media = Media(
        id=uuid.uuid4().hex[:12],
        tipo="video",
        url=url,
        orden=len(perfil.videos),
        segundos=segundos,
    )
    perfil.videos.append(media)
    return media


def borrar(perfil: Perfil, id_media: str) -> bool:
    """Borra la foto o el video y **renumera**: si queda un hueco en `orden`,
    la portada puede terminar apuntando a nada y la tarjeta sale gris."""
    for coleccion in (perfil.fotos, perfil.videos):
        for i, m in enumerate(coleccion):
            if m.id == id_media:
                coleccion.pop(i)
                for j, resto in enumerate(coleccion):
                    resto.orden = j
                return True
    return False


def reordenar(perfil: Perfil, ids_en_orden: list[str]) -> None:
    """Reordena las fotos según la lista de ids. Los que no vengan quedan al
    final, en su orden actual — así un cliente viejo que manda una lista
    incompleta no borra fotos sin querer."""
    indice = {id_: i for i, id_ in enumerate(ids_en_orden)}
    perfil.fotos.sort(key=lambda m: (indice.get(m.id, 10_000), m.orden))
    for i, m in enumerate(perfil.fotos):
        m.orden = i


def resumen(perfil: Perfil) -> dict:
    return {
        "fotos": len(perfil.fotos),
        "fotos_max": MAX_FOTOS,
        "videos": len(perfil.videos),
        "videos_max": MAX_VIDEOS,
        "segundos_max_video": MAX_SEGUNDOS_VIDEO,
        "tiene_portada": perfil.portada is not None,
    }
