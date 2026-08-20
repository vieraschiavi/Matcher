"""El kit de marca sale de la MISMA paleta que la app.

Cuando cambió el tema (fuera el violeta, entra carbón y fuego) el generador del
kit se quedó con los valores viejos, y el ícono que se ve en el escritorio de
Windows y en el cajón de Android era rosa y violeta mientras la app abría en
grafito y coral. Dos productos distintos según dónde lo mires.

Este test compara los dos archivos. No se puede "arreglar" tocando uno solo.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
TEMA = RAIZ / "webapp" / "frontend" / "src" / "theme.css"


def tokens_del_tema() -> dict[str, str]:
    """Los `--token: #hex;` del bloque `:root` de theme.css."""
    css = TEMA.read_text(encoding="utf-8")
    raiz = css.split(":root {", 1)[1].split("\n}", 1)[0]
    return {
        n: h.lower() for n, h in re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;", raiz)
    }


def test_la_paleta_del_kit_es_la_de_la_app():
    from marketing.generar_kit import PALETA

    tema = tokens_del_tema()
    for nombre, hexa in PALETA.items():
        if nombre not in tema:
            continue  # tokens propios del kit, si algún día hay
        assert hexa.lower() == tema[nombre], (
            f"`{nombre}` es {hexa} en el kit y {tema[nombre]} en theme.css: "
            "el ícono y los banners salen de otro producto que la app"
        )


def test_no_quedo_ningun_color_de_la_paleta_vieja():
    """La base violácea y el acento violeta eran EL pedido del dueño. Si
    reaparecen en el tema o en el kit, es que alguien revirtió el cambio sin
    darse cuenta."""
    from marketing.generar_kit import PALETA

    viejos = {"#8e5bef", "#ff4d6d", "#c9184a", "#120d1c", "#1a1226", "#241a33"}
    en_kit = {h.lower() for h in PALETA.values()} & viejos
    assert not en_kit, f"colores de la paleta vieja en el kit: {en_kit}"
    en_tema = set(tokens_del_tema().values()) & viejos
    assert not en_tema, f"colores de la paleta vieja en theme.css: {en_tema}"


def test_los_iconos_de_la_app_estan_y_son_los_que_esperan_los_empaquetadores():
    Image = pytest.importorskip("PIL.Image", reason="Pillow no instalado")
    marca = RAIZ / "assets" / "marca"

    with Image.open(marca / "icono_1024.png") as img:
        assert img.size == (1024, 1024)
        assert img.mode == "RGBA", "el ícono de escritorio necesita alfa por las esquinas"

    # Play Store rechaza en la subida un 512 con transparencia o con esquinas
    # redondeadas: lo quiere cuadrado y opaco.
    with Image.open(marca / "icono_play_512.png") as img:
        assert img.size == (512, 512)
        assert img.mode == "RGB", "Play Store exige el ícono sin canal alfa"

    assert (marca / "icono.ico").exists(), "falta el ícono de Windows"


def test_el_icono_esta_pintado_con_el_fuego_y_no_con_el_violeta():
    """Mira el píxel de arriba a la izquierda del ícono, que es donde arranca
    el degradado. Con la paleta vieja ahí había rosa; ahora tiene que haber
    brasa (mucho más rojo que azul)."""
    Image = pytest.importorskip("PIL.Image", reason="Pillow no instalado")
    with Image.open(RAIZ / "assets" / "marca" / "icono_play_512.png") as img:
        r, g, b = img.convert("RGB").getpixel((6, 6))
    assert r > 200 and b < 120, f"el ícono arranca en rgb({r},{g},{b}), que no es fuego"
    assert r - b > 100, "el degradado del ícono no es cálido"
