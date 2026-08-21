"""Contra qué backend queda compilada la app empaquetada.

EL BUG QUE ESTE ARCHIVO EXISTE PARA IMPEDIR

El valor por defecto de `BASE` en `webapp/frontend/src/api.js` era
`https://api.matcher.app`: un dominio de ejemplo que nunca se registró. Como el
APK y el programa de escritorio se sirven desde el disco, ahí no hay
same-origin que valga y ESE valor es el que usan si nadie define
`VITE_API_URL`.

Resultado: la app instalada abría bien, mostraba la pantalla de entrada… y
cualquier cosa que hiciera la persona moría con "Failed to fetch". Ni siquiera
se podía entrar con las cuentas de demo. No fallaba el build, no fallaba
ningún test: fallaba en el teléfono del dueño.

Estos tests miran el archivo fuente, que es donde vive la decisión.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
API_JS = RAIZ / "webapp" / "frontend" / "src" / "api.js"

# Dominios reservados para ejemplos y documentación (RFC 2606/6761) más el que
# nos mordió. Ninguno resuelve a un servidor de verdad.
DE_EJEMPLO = (
    "api.matcher.app",
    "example.com",
    "example.org",
    "example.net",
    "midominio",
    "tu-dominio",
    "TU-DOMINIO",
    "localhost",
    "127.0.0.1",
)


@pytest.fixture(scope="module")
def fuente() -> str:
    return API_JS.read_text(encoding="utf-8")


def url_por_defecto(fuente: str) -> str:
    m = re.search(r'const POR_DEFECTO\s*=\s*"([^"]+)"', fuente)
    assert m, "no se encontró `POR_DEFECTO` en api.js: ¿se renombró?"
    return m.group(1)


def test_el_backend_por_defecto_no_es_un_dominio_de_ejemplo(fuente):
    url = url_por_defecto(fuente)
    for malo in DE_EJEMPLO:
        assert malo not in url, (
            f"el backend por defecto es {url!r}. Un APK compilado sin "
            f"VITE_API_URL va a apuntar ahí y morir con 'Failed to fetch' en "
            f"el teléfono, sin que falle ningún build."
        )


def test_el_backend_por_defecto_es_https(fuente):
    """Android bloquea el tráfico en claro desde SDK 28 y la app además tiene
    `usesCleartextTraffic=false`: un `http://` acá es una app que no conecta."""
    url = url_por_defecto(fuente)
    assert url.startswith("https://"), f"{url!r} no es https"
    assert not url.endswith("/"), "la barra final duplica la barra de cada ruta"


def test_se_puede_pisar_al_compilar(fuente):
    """`VITE_API_URL` tiene que seguir ganándole al valor por defecto: es cómo
    se apunta a otro backend sin tocar el código."""
    assert "VITE_API_URL" in fuente
    assert re.search(r"BASE\s*=\s*CONFIGURADA\s*\|\|", fuente), (
        "el valor configurado al compilar dejó de tener prioridad"
    )


def test_un_fallo_de_red_se_explica_en_castellano(fuente):
    """`fetch` tira TypeError("Failed to fetch") y ese texto no le dice nada a
    nadie. La app tiene que decir contra qué dirección está compilada."""
    assert "class ErrorSinRed" in fuente
    assert "No se puede conectar con el servidor" in fuente
    m = re.search(r"catch \(e\) \{[^}]*ErrorSinRed", fuente, re.S)
    assert m, "el fetch no está envuelto: el TypeError crudo sigue llegando a la UI"


def test_la_pantalla_de_entrada_avisa_si_no_hay_servidor():
    """Sin esto el aviso existe pero no se ve: el sondeo de salud se tragaba el
    error y la pantalla quedaba normal hasta que alguien apretaba Entrar."""
    entrar = (RAIZ / "webapp" / "frontend" / "src" / "paginas" / "Entrar.jsx").read_text(
        encoding="utf-8"
    )
    assert "sinServidor" in entrar
    assert "sinRed" in entrar, "el aviso no distingue 'no hay red' de otros errores"
