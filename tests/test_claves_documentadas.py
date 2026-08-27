"""Que toda variable de entorno que el código lee esté documentada.

POR QUÉ EXISTE

`docs/CLAVES.md` es lo que alguien lee para poner el producto en producción. Si
el código lee una variable que ese documento no menciona, esa variable es
invisible: quien despliega no puede saber que existe, y cuando hace falta el
síntoma no se parece a la causa.

Pasó con seis a la vez —`MATCHER_EFIMERO`, `MATCHER_HOST`, `MATCHER_PUERTO`,
`MATCHER_URL_APP`, `STRIPE_API_KEY`— y ninguna rompía un test: simplemente no
estaban escritas en ningún lado.

Este test recorre el CÓDIGO en vez de comparar contra una lista escrita a mano.
Una lista se olvida de la próxima igual que se olvidó de éstas.

LO QUE ESTE TEST **NO** HACE, Y NO DEBE HACER
No verifica valores. Ninguna clave, token ni secreto se escribe en el
repositorio: acá viven los NOMBRES y de dónde sale cada valor. El repo es
público — una credencial commiteada queda indexada para siempre, aunque después
se borre del archivo.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CLAVES = RAIZ / "docs" / "CLAVES.md"
FUENTES = ("matcher", "webapp/backend", "marketing")

# Las que inyecta la plataforma, no una persona. No van en la tabla de "qué
# cargar" porque no se cargan: se reciben.
DE_LA_PLATAFORMA = {"PORT", "PYTHONPATH", "HOME", "PATH"}


def variables_del_codigo() -> set[str]:
    encontradas: set[str] = set()
    for carpeta in FUENTES:
        for archivo in (RAIZ / carpeta).rglob("*.py"):
            encontradas |= set(
                re.findall(
                    r'getenv\(\s*["\']([A-Z][A-Z0-9_]+)["\']',
                    archivo.read_text(encoding="utf-8"),
                )
            )
    return encontradas - DE_LA_PLATAFORMA


def test_toda_variable_que_se_lee_esta_documentada():
    """ES EL PUNTO. Una variable sin documentar es una variable invisible."""
    texto = CLAVES.read_text(encoding="utf-8")
    faltan = sorted(v for v in variables_del_codigo() if v not in texto)
    assert not faltan, (
        "el código lee estas variables y docs/CLAVES.md no las menciona:\n  "
        + "\n  ".join(faltan)
        + "\n\nQuien despliega no puede saber que existen."
    )


def test_el_documento_no_trae_ningun_secreto():
    """Los VALORES no van al repo. El repositorio es público: una credencial
    commiteada queda indexada para siempre, aunque después se borre del
    archivo. Acá van los nombres y de dónde sale cada valor.

    Se buscan los prefijos que usan los proveedores para sus credenciales
    reales, que es lo que se copia y pega sin pensar.
    """
    texto = CLAVES.read_text(encoding="utf-8")
    sospechosos = [
        (r"APP_USR-[A-Za-z0-9_-]{20,}", "access token de producción de MercadoPago"),
        (r"\bTEST-[A-Za-z0-9_-]{20,}", "access token de prueba de MercadoPago"),
        (r"\bre_[A-Za-z0-9_-]{20,}", "API key de Resend"),
        (r"\bsk_(live|test)_[A-Za-z0-9]{20,}", "clave secreta de Stripe"),
        (r"\bghp_[A-Za-z0-9]{30,}", "token de GitHub"),
        (r"AIza[A-Za-z0-9_-]{30,}", "clave de Google"),
    ]
    for patron, que in sospechosos:
        m = re.search(patron, texto)
        assert not m, f"docs/CLAVES.md parece traer un {que}: {m.group(0)[:12]}…"


def test_ningun_modulo_trae_una_credencial_cableada():
    """La misma regla, del lado del código: un valor por defecto que sea una
    credencial de verdad es una credencial publicada."""
    for carpeta in FUENTES:
        for archivo in (RAIZ / carpeta).rglob("*.py"):
            texto = archivo.read_text(encoding="utf-8")
            for patron in (r"APP_USR-[A-Za-z0-9_-]{20,}", r"\bre_[A-Za-z0-9_-]{20,}",
                           r"\bsk_(live|test)_[A-Za-z0-9]{20,}"):
                m = re.search(patron, texto)
                assert not m, f"{archivo} tiene una credencial cableada: {m.group(0)[:12]}…"
