"""Que la suite se pueda RECOLECTAR en una máquina limpia.

POR QUÉ EXISTE

`requirements-dev.txt` no tenía Pillow. En esta máquina no se notaba —estaba
instalado de antes— pero en el CI, que arranca limpio, pytest se cortaba con
`ModuleNotFoundError: No module named 'PIL'` **durante la recolección**: no
falló un test, no corrió NINGUNO.

Es la peor forma de romperse, porque no dice "este test falla" sino "exit code
2", y hay que leer el log para entender que la suite entera no se ejecutó.

Estuvo así ocho días sin que nadie se enterara, porque el CI estaba mudo (regla
22). Apenas volvió a correr, esto fue lo primero que encontró.

Este test no mira una lista de nombres: importa de verdad todo lo que los tests
importan. Un test que enumere paquetes a mano se olvida del próximo igual que
se olvidó de Pillow.
"""

from __future__ import annotations

import importlib

import pytest

# Módulos del proyecto que un test importa y que arrastran dependencias de
# terceros en el import. Si mañana alguien agrega otro, que este test lo
# atrape antes que el CI.
MODULOS = [
    "matcher.almacen",
    "matcher.pagos",
    "matcher.solicitudes",
    "webapp.backend.api",
    "marketing.generar_landing",   # arrastra generar_kit -> PIL
    "marketing.generar_kit",       # PIL
    "marketing.generar_informe",   # openpyxl
    "marketing.modelo_negocio",
]


@pytest.mark.parametrize("nombre", MODULOS)
def test_se_puede_importar(nombre):
    """Si esto explota, la suite no se recolecta y NINGÚN test corre."""
    try:
        importlib.import_module(nombre)
    except ModuleNotFoundError as e:
        pytest.fail(
            f"`{nombre}` necesita `{e.name}`, que no está en requirements-dev.txt. "
            "En una máquina limpia pytest se corta en la recolección y no corre "
            "ni un test."
        )


def test_las_dependencias_de_terceros_estan_declaradas():
    """Las que se usan en el import de algo que los tests importan tienen que
    estar en requirements-dev.txt, no "estar instaladas por casualidad".

    OJO CON LOS COMENTARIOS. La primera versión de este test buscaba el nombre
    en el texto del archivo, y comentar `# Pillow>=10.0` lo dejaba pasar: la
    palabra seguía ahí. Lo descubrí saboteando el arreglo — el sabotaje no
    puso el test en rojo, que es justo la señal de que el test no servía.
    Por eso ahora se leen sólo las líneas que `pip` leería.
    """
    from pathlib import Path

    crudo = (
        Path(__file__).resolve().parents[1] / "requirements-dev.txt"
    ).read_text(encoding="utf-8")
    declarados = " ".join(
        linea.split("#")[0].strip().lower()
        for linea in crudo.splitlines()
        if linea.strip() and not linea.strip().startswith("#")
    )
    for paquete in ("pytest", "ruff", "pyyaml", "openpyxl", "pillow"):
        assert paquete in declarados, (
            f"falta `{paquete}` en requirements-dev.txt (comentado no cuenta)"
        )
