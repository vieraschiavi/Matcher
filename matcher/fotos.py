"""De dónde salen las fotos de los perfiles de la demo.

Hay tres fuentes, en este orden:

1. **La carpeta que le indiques** (`MATCHER_FOTOS=/ruta`): tus fotos, las de un
   pack con licencia, o las de usuarios que aceptaron. Es lo que se usa para
   una demo comercial o una prueba con usuarios reales.
2. **El pack incluido** (`assets/personas/`): 61 rostros **sintéticos**
   fotorrealistas, generados con StyleGAN. No son personas que existan.
   Ver `assets/personas/LEEME.md` para procedencia y licencia.
3. **Retratos ilustrados generados por código** (`avatares.py`), si no hay
   ninguna carpeta o si pedís `MATCHER_FOTOS=ninguna`.

Lo que NUNCA es el default son fotos de personas reales: un perfil de citas con
la cara de alguien que no dio su consentimiento es una identidad falsa, y la
licencia comercial de un banco de imágenes no cubre ese uso.

Las fotos se leen a data-URI, igual que las que sube un usuario desde la app,
así que la demo no necesita storage de objetos para funcionar.
"""

from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path

from . import avatares

EXTENSIONES = (".jpg", ".jpeg", ".png", ".webp")
VARIABLE = "MATCHER_FOTOS"
GENEROS_CARPETA = ("mujer", "hombre", "no_binario")
PACK_INCLUIDO = Path(__file__).resolve().parent.parent / "assets" / "personas"


def carpeta_configurada() -> Path | None:
    """La carpeta a usar, o None para caer en los retratos ilustrados."""
    ruta = os.getenv(VARIABLE, "").strip()
    if ruta.lower() in ("ninguna", "none", "0"):
        return None
    if ruta:
        p = Path(ruta).expanduser()
        return p if p.is_dir() else None
    return PACK_INCLUIDO if PACK_INCLUIDO.is_dir() else None


def _listar(carpeta: Path) -> list[Path]:
    return sorted(f for f in carpeta.iterdir() if f.is_file() and f.suffix.lower() in EXTENSIONES)


def _agrupar_por_persona(archivos: list[Path]) -> list[list[Path]]:
    """Agrupa las tomas de la misma persona.

    Convención: `<lo que sea>_<N>.jpg` donde N es el número de toma; el prefijo
    identifica a la persona (`mujer_07_1.jpg` y `mujer_07_2.jpg` son la misma).
    Si los nombres no siguen la convención, cada archivo es una persona — que
    es lo correcto para una carpeta de fotos sueltas.

    Esto importa: sin agrupar, el carrusel de un perfil mezcla caras distintas
    y se nota al instante que los perfiles son de mentira.
    """
    grupos: dict[str, list[Path]] = {}
    for f in archivos:
        tallo = f.stem
        if "_" in tallo and tallo.rsplit("_", 1)[1].isdigit():
            tallo = tallo.rsplit("_", 1)[0]
        grupos.setdefault(tallo, []).append(f)
    return [grupos[k] for k in sorted(grupos)]


def catalogo(carpeta: Path | None = None) -> dict[str, list[list[Path]]]:
    """Personas disponibles por género: `{genero: [[tomas de una persona], …]}`."""
    carpeta = carpeta or carpeta_configurada()
    if not carpeta:
        return {}
    salida: dict[str, list[list[Path]]] = {}
    for genero in GENEROS_CARPETA:
        sub = carpeta / genero
        if sub.is_dir():
            archivos = _listar(sub)
            if archivos:
                salida[genero] = _agrupar_por_persona(archivos)
    sueltas = _listar(carpeta)
    if sueltas:
        salida["todos"] = _agrupar_por_persona(sueltas)
    return salida


def a_data_uri(archivo: Path) -> str:
    tipo = mimetypes.guess_type(archivo.name)[0] or "image/jpeg"
    return f"data:{tipo};base64," + base64.b64encode(archivo.read_bytes()).decode("ascii")


class Fuente:
    """Reparte personas entre los perfiles del seed.

    El reparto es **determinista** (por índice de perfil, no al azar): dos
    corridas de la demo le dan la misma cara a la misma persona, que es la
    única forma de poder testear el deck y el ranking.
    """

    def __init__(self, carpeta: Path | None = None):
        self.catalogo = catalogo(carpeta)
        self.reales = bool(self.catalogo)
        self._usadas: set[str] = set()

    def _pool(self, genero: str) -> list[list[Path]]:
        """Personas candidatas para ese género.

        Si no hay carpeta propia para el género, se usa el pool completo en
        vez de caer a los retratos ilustrados. Importa para `no_binario`: con
        el fallback anterior esos perfiles salían dibujados en medio de una
        demo de fotos y se los distinguía de un vistazo, que es justo lo que
        no tiene que pasar.
        """
        if genero in self.catalogo:
            return self.catalogo[genero]
        if "todos" in self.catalogo:
            return self.catalogo["todos"]
        return [grupo for pools in self.catalogo.values() for grupo in pools]

    def para(self, clave: str, nombre: str, genero: str, cuantas: int) -> list[str]:
        """URLs de las fotos de un perfil. Devuelve `cuantas` como máximo: si la
        persona elegida tiene menos tomas, devuelve las que tiene — repetir la
        misma foto en el carrusel se ve peor que tener una sola."""
        pool = self._pool(genero)
        if not pool:
            return [avatares.data_uri(clave, nombre, k, genero) for k in range(cuantas)]
        # Primera persona del pool que no se haya usado. El registro es global
        # y no por género: los pools se solapan (un perfil no binario sale del
        # pool completo) y dos perfiles con la misma cara arruinan la demo.
        elegida = next((g for g in pool if str(g[0]) not in self._usadas), None)
        if elegida is None:
            # Se agotó el pack: se vuelve a los retratos generados en vez de
            # repetir caras. Pasa sólo si se pide una población más grande que
            # el pack, y es preferible a una demo con clones.
            return [avatares.data_uri(clave, nombre, k, genero) for k in range(cuantas)]
        self._usadas.add(str(elegida[0]))
        return [a_data_uri(t) for t in elegida[:cuantas]]

    def descripcion(self) -> str:
        if not self.reales:
            return "retratos ilustrados generados por código (sin archivos)"
        personas = sum(len(v) for v in self.catalogo.values())
        carpeta = carpeta_configurada()
        origen = "pack incluido" if carpeta == PACK_INCLUIDO else str(carpeta)
        return f"{personas} personas desde {origen}"
