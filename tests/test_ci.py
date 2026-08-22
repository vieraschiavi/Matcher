"""Que el CI CORRA.

POR QUÉ EXISTE ESTE ARCHIVO

`ci.yml` —el que corre el linter y los más de 400 tests— estuvo filtrado a
`branches: [main]`, y este repositorio **no tiene** una rama `main`: la única
rama es la de trabajo, que además es la rama por defecto. Con ese filtro, cada
push se salteaba el linter y los tests **en silencio**.

Un CI que no corre es peor que no tener CI: la pestaña Actions vacía se lee
como "pasó todo". Nadie mira un workflow que nunca falla.

Estos tests no prueban el producto: prueban que lo que prueba el producto se
ejecute. Es la clase de error que sólo se ve mirando el archivo, porque no
rompe nada — simplemente no pasa nada.
"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

RAIZ = Path(__file__).resolve().parents[1]
FLUJOS = RAIZ / ".github" / "workflows"


def _cargar(nombre: str) -> dict:
    d = yaml.safe_load((FLUJOS / nombre).read_text(encoding="utf-8"))
    # PyYAML lee `on:` como el booleano True (es YAML 1.1: "on" == sí). No es
    # un bug del workflow, es del parser — pero si no se contempla, el test
    # busca una clave que no existe y "pasa" sin mirar nada.
    return d


def _disparadores(d: dict) -> dict:
    return d[True] if True in d else d["on"]


def test_el_ci_corre_en_la_rama_en_la_que_se_trabaja():
    """ES EL PUNTO. Un filtro por nombre de rama se desincroniza: la rama de
    trabajo cambia en cada tanda y el filtro se queda con el nombre viejo."""
    ramas = _disparadores(_cargar("ci.yml"))["push"]["branches"]
    assert ramas == ["**"], (
        f"el CI sólo corre en {ramas}; si esa rama no existe, no corre nunca "
        "y la pestaña Actions queda vacía, que se lee como 'pasó todo'"
    )


def test_el_ci_corre_el_linter_y_los_tests():
    """Que el workflow se dispare no sirve si no ejecuta nada."""
    pasos = _cargar("ci.yml")["jobs"]["motor"]["steps"]
    corridas = " ".join(p.get("run", "") for p in pasos)
    assert "ruff check" in corridas
    assert "pytest" in corridas


def test_el_ci_instala_nsis():
    """Sin NSIS, `test_el_script_del_instalador_compila` hace `skip` y el
    instalador de Windows queda sin verificar — verde por ausencia, que es el
    mismo engaño que el filtro de ramas en chiquito."""
    pasos = _cargar("ci.yml")["jobs"]["motor"]["steps"]
    assert any("nsis" in p.get("run", "") for p in pasos), (
        "el test del instalador se va a saltear en el CI"
    )


def test_ningun_workflow_apunta_a_un_dominio_que_no_existe():
    """`api.matcher.app` es un dominio de ejemplo que nunca se registró. Una app
    compilada contra él abre bien y muere con "Failed to fetch" en el login,
    sin ninguna pista. Ya pasó una vez, con el APK."""
    for archivo in FLUJOS.glob("*.yml"):
        texto = archivo.read_text(encoding="utf-8")
        for linea in texto.splitlines():
            if "api.matcher.app" in linea and not linea.strip().startswith("#"):
                pytest.fail(f"{archivo.name} apunta a api.matcher.app: {linea.strip()}")
