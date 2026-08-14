"""Retratos de la demo, generados.

Regla que no se rompe (la misma de MV Cliente IA): **nunca se generan personas
reales.** Los perfiles de la demo son inventados y sus fotos son retratos
**ilustrados** — vectoriales, dibujados por código. No hay fotografías, no hay
stock de gente real, no hay nada que pueda confundirse con alguien que existe.

Pero sí tienen que verse como personas: una app de citas con siluetas grises no
se puede ni mirar, y menos mostrar. Así que cada retrato compone tono de piel,
peinado, ropa, accesorios, fondo y encuadre, y cada perfil recibe una paleta
propia que se mantiene entre sus 10 fotos (es "la misma persona" en todas).

Determinista: la misma semilla da siempre el mismo retrato. Sin eso, cada vez
que se levanta la demo el mismo perfil cambia de cara y parece otro.
"""

from __future__ import annotations

import base64
import hashlib

# --------------------------------------------------------------------------
# Paletas. Tonos de piel y de pelo variados a propósito: una app de citas que
# genera 60 perfiles del mismo tono es un problema de producto, no un detalle.
# --------------------------------------------------------------------------
PIELES = [
    ("#f3d3bd", "#e0b89c"), ("#e8c39e", "#d1a77f"), ("#d7a87b", "#bd8b5e"),
    ("#c68642", "#a86c31"), ("#a8663c", "#8a4f2c"), ("#8d5524", "#6f4119"),
    ("#6b4327", "#523018"), ("#4a2f1c", "#38210f"), ("#ffdfc4", "#f0c6a4"),
]
# Tonos de pelo: naturales, más dos teñidos. Los violetas y verdes planos que
# había antes no se leían como pelo sino como tela — el retrato entero pasaba a
# parecer una capucha.
PELOS = [
    "#1b1b1f", "#2e211a", "#4a2c1a", "#6b4423", "#8d6748", "#b98b56",
    "#d9b380", "#e8d5a3", "#7a2f2f", "#3b3b45", "#8f8f9c", "#c94f7c",
]
ROPAS = [
    "#1f2a44", "#c9184a", "#0b6e4f", "#e07a2f", "#5b4bd6", "#0d3b66",
    "#d64550", "#2b8ca8", "#7d3c98", "#243447", "#b8860b", "#37474f",
]
FONDOS = [
    ("#ff9a8b", "#ff6a88"), ("#a1c4fd", "#c2e9fb"), ("#ffd26f", "#ff8f5e"),
    ("#84fab0", "#8fd3f4"), ("#d4a5ff", "#8e7dff"), ("#f6d365", "#fda085"),
    ("#5ee7df", "#66a6ff"), ("#ff8fab", "#c9184a"), ("#43e97b", "#38f9d7"),
    ("#30cfd0", "#330867"), ("#ffb199", "#ff0844"), ("#4facfe", "#00f2fe"),
]

PEINADOS = ("corto", "largo", "ondulado", "rodete", "rapado", "rulos", "flequillo")


# Probabilidad de barba por género. Es lo único que el género condiciona: el
# peinado, la ropa y los accesorios se sortean igual para todos. Antes no se
# miraba el género y la mitad de los perfiles de mujeres salían con barba.
PROB_BARBA = {"hombre": 45, "trans": 12, "otro": 12, "mujer": 0}


def _rasgos(clave: str, genero: str = "otro") -> dict:
    """Rasgos estables de una persona, derivados del id del perfil.

    Se calculan una sola vez por perfil (no por foto) para que las 10 fotos
    sean reconociblemente la misma persona. Cuando esto dependía del índice de
    la foto, el carrusel parecía diez personas distintas.
    """
    h = hashlib.sha256(clave.encode()).digest()
    n = list(h)
    piel = PIELES[n[0] % len(PIELES)]
    return {
        "piel": piel[0],
        "sombra": piel[1],
        "pelo": PELOS[n[1] % len(PELOS)],
        "peinado": PEINADOS[n[2] % len(PEINADOS)],
        "ropa": ROPAS[n[3] % len(ROPAS)],
        "barba": n[4] % 100 < PROB_BARBA.get(genero, 12),
        "anteojos": n[5] % 100 < 22,
        "aros": n[6] % 100 < 30,
        "pecas": n[7] % 100 < 18,
        # Encuadre de retrato: la cara tiene que ocupar el tercio superior de
        # la tarjeta. Con la cara chica (los valores originales) el resultado
        # eran 60 fotos de fondo de color con una cabecita al medio.
        "cara_ancho": 128 + n[8] % 24,    # semieje x de la cara
        "cara_alto": 155 + n[9] % 26,     # semieje y
        "ojos_sep": 44 + n[10] % 12,
        "sonrisa": 0.5 + (n[11] % 60) / 100,
        "ceja": n[12] % 6 - 3,
    }


def _fondo(clave: str, indice: int) -> tuple[str, str]:
    h = hashlib.sha256(f"{clave}#fondo{indice}".encode()).digest()
    return FONDOS[h[0] % len(FONDOS)]


def _pelo_svg(r: dict, cx: float, cy: float) -> str:
    """El pelo se dibuja en dos capas: una detrás de la cara (melena, rodete) y
    otra delante (flequillo, contorno). El SVG las devuelve juntas porque el
    orden de pintado ya está resuelto acá."""
    p, w, hh = r["pelo"], r["cara_ancho"], r["cara_alto"]
    estilo = r["peinado"]
    detras = ""
    if estilo == "largo":
        detras = (
            f'<path d="M{cx - w - 16} {cy + hh + 120} '
            f'C{cx - w - 30} {cy - hh * 0.4} {cx - w * 0.9} {cy - hh - 30} {cx} {cy - hh - 30} '
            f'C{cx + w * 0.9} {cy - hh - 30} {cx + w + 30} {cy - hh * 0.4} '
            f'{cx + w + 16} {cy + hh + 120} Z" fill="{p}"/>'
        )
    elif estilo == "ondulado":
        detras = (
            f'<path d="M{cx - w - 12} {cy + hh + 60} '
            f'Q{cx - w - 34} {cy - hh * 0.2} {cx - w * 0.7} {cy - hh - 26} '
            f'Q{cx} {cy - hh - 56} {cx + w * 0.7} {cy - hh - 26} '
            f'Q{cx + w + 34} {cy - hh * 0.2} {cx + w + 12} {cy + hh + 60} Z" fill="{p}"/>'
        )
    elif estilo == "rodete":
        detras = f'<circle cx="{cx}" cy="{cy - hh - 34}" r="46" fill="{p}"/>'
    elif estilo == "rulos":
        detras = "".join(
            f'<circle cx="{cx + dx}" cy="{cy - hh + dy}" r="{rr}" fill="{p}"/>'
            for dx, dy, rr in (
                (-w * 0.95, 18, 40), (-w * 0.55, -26, 44), (0, -44, 46),
                (w * 0.55, -26, 44), (w * 0.95, 18, 40),
            )
        )

    if estilo == "rapado":
        delante = (
            f'<path d="M{cx - w - 2} {cy - hh * 0.18} '
            f'A{w + 2} {hh + 2} 0 0 1 {cx + w + 2} {cy - hh * 0.18} '
            f'L{cx + w + 2} {cy - hh * 0.34} '
            f'A{w + 2} {hh + 2} 0 0 0 {cx - w - 2} {cy - hh * 0.34} Z" '
            f'fill="{p}" opacity="0.85"/>'
        )
    elif estilo == "flequillo":
        delante = (
            f'<path d="M{cx - w - 4} {cy - hh * 0.12} '
            f'C{cx - w} {cy - hh - 40} {cx + w} {cy - hh - 40} {cx + w + 4} {cy - hh * 0.12} '
            f'C{cx + w * 0.5} {cy - hh * 0.5} {cx - w * 0.5} {cy - hh * 0.5} '
            f'{cx - w - 4} {cy - hh * 0.12} Z" fill="{p}"/>'
        )
    else:
        # Nacimiento del pelo alto: cuando la capa de adelante bajaba hasta
        # cy − hh*0.1 tapaba las cejas y el conjunto se leía como una capucha,
        # no como un peinado.
        delante = (
            f'<path d="M{cx - w - 6} {cy - hh * 0.36} '
            f'C{cx - w - 6} {cy - hh - 46} {cx + w + 6} {cy - hh - 46} '
            f'{cx + w + 6} {cy - hh * 0.36} '
            f'C{cx + w * 0.6} {cy - hh * 0.86} {cx - w * 0.6} {cy - hh * 0.86} '
            f'{cx - w - 6} {cy - hh * 0.36} Z" fill="{p}"/>'
        )
    return detras, delante


def svg(clave: str, inicial: str, indice: int = 0, genero: str = "otro") -> str:
    """Retrato de 800×1000 (proporción de tarjeta de citas).

    `indice` cambia fondo, encuadre y pose — misma persona, otra foto.
    """
    r = _rasgos(clave, genero)
    c1, c2 = _fondo(clave, indice)
    h = hashlib.sha256(f"{clave}#pose{indice}".encode()).digest()
    # Los ids de gradiente tienen que ser únicos por retrato: si dos SVGs
    # inline comparten `id="bg"`, el navegador resuelve `url(#bg)` al primero
    # del documento y todas las fotos salen con el mismo fondo.
    uid = hashlib.sha1(f"{clave}#{indice}".encode()).hexdigest()[:8]

    # Encuadre: alterna plano medio y primer plano, con un corrimiento lateral
    # chico. Diez fotos idénticas de frente se ven a robot.
    zoom = 1.02 + (h[0] % 20) / 100
    dx = (h[1] % 44) - 22
    cx, cy = 400 + dx, 400
    w, hh = r["cara_ancho"], r["cara_alto"]
    ojo_y = cy - hh * 0.06
    sep = r["ojos_sep"]
    pelo_detras, pelo_delante = _pelo_svg(r, cx, cy)

    pecas = ""
    if r["pecas"]:
        pecas = "".join(
            f'<circle cx="{cx + px}" cy="{cy + py}" r="2.6" fill="{r["sombra"]}" '
            f'opacity="0.75"/>'
            for px, py in ((-38, 14), (-26, 24), (-14, 12), (16, 14), (28, 24), (40, 12))
        )

    barba = ""
    if r["barba"]:
        barba = (
            f'<path d="M{cx - w * 0.92} {cy + hh * 0.1} '
            f'C{cx - w * 0.86} {cy + hh * 0.92} {cx + w * 0.86} {cy + hh * 0.92} '
            f'{cx + w * 0.92} {cy + hh * 0.1} '
            f'C{cx + w * 0.5} {cy + hh * 0.52} {cx - w * 0.5} {cy + hh * 0.52} '
            f'{cx - w * 0.92} {cy + hh * 0.1} Z" fill="{r["pelo"]}" opacity="0.92"/>'
        )

    anteojos = ""
    if r["anteojos"]:
        anteojos = (
            f'<g fill="none" stroke="#20242e" stroke-width="5" opacity="0.9">'
            f'<circle cx="{cx - sep}" cy="{ojo_y}" r="26"/>'
            f'<circle cx="{cx + sep}" cy="{ojo_y}" r="26"/>'
            f'<line x1="{cx - sep + 26}" y1="{ojo_y}" x2="{cx + sep - 26}" y2="{ojo_y}"/>'
            f"</g>"
        )

    aros = ""
    if r["aros"]:
        aros = (
            f'<circle cx="{cx - w - 2}" cy="{cy + hh * 0.28}" r="9" fill="#ffd166"/>'
            f'<circle cx="{cx + w + 2}" cy="{cy + hh * 0.28}" r="9" fill="#ffd166"/>'
        )

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="1000" '
        'viewBox="0 0 800 1000">'
        "<defs>"
        f'<linearGradient id="bg{uid}" x1="0" y1="0" x2="0.4" y2="1">'
        f'<stop offset="0%" stop-color="{c1}"/><stop offset="100%" stop-color="{c2}"/>'
        "</linearGradient>"
        f'<linearGradient id="vig{uid}" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="62%" stop-color="#0a1020" stop-opacity="0"/>'
        '<stop offset="100%" stop-color="#0a1020" stop-opacity="0.42"/>'
        "</linearGradient>"
        "</defs>"
        f'<rect width="800" height="1000" fill="url(#bg{uid})"/>'
        # Formas suaves de fondo: dan profundidad y evitan el fondo plano.
        f'<circle cx="{140 + h[2] % 520}" cy="{170 + h[3] % 200}" r="{110 + h[4] % 90}" '
        f'fill="#ffffff" opacity="0.16"/>'
        f'<circle cx="{80 + h[5] % 640}" cy="{760 + h[6] % 160}" r="{130 + h[7] % 110}" '
        f'fill="#ffffff" opacity="0.10"/>'
        f'<g transform="translate(400 500) scale({zoom:.3f}) translate(-400 -500)">'
        # Orden de pintado, y es lo que hace que el retrato se lea:
        # melena → cuello → torso → orejas → cara. Cuando la melena iba encima
        # del torso rellenaba el hueco entre el mentón y los hombros, y todas
        # las mujeres de pelo largo parecían tener barba.
        f"{pelo_detras}"
        f'<rect x="{cx - 44}" y="{cy + hh * 0.5}" width="88" height="150" rx="38" '
        f'fill="{r["sombra"]}"/>'
        # Torso: hombros anchos con escote en V. El semicírculo que había antes
        # se leía como un globo, no como una persona.
        f'<path d="M{cx - 360} 1000 C{cx - 350} {cy + hh + 130} {cx - 210} '
        f'{cy + hh + 34} {cx - 78} {cy + hh + 8} '
        f'L{cx} {cy + hh + 74} L{cx + 78} {cy + hh + 8} '
        f'C{cx + 210} {cy + hh + 34} {cx + 350} {cy + hh + 130} {cx + 360} 1000 Z" '
        f'fill="{r["ropa"]}"/>'
        # Orejas
        f'<ellipse cx="{cx - w}" cy="{cy + hh * 0.12}" rx="17" ry="26" fill="{r["piel"]}"/>'
        f'<ellipse cx="{cx + w}" cy="{cy + hh * 0.12}" rx="17" ry="26" fill="{r["piel"]}"/>'
        # Cara
        f'<ellipse cx="{cx}" cy="{cy}" rx="{w}" ry="{hh}" fill="{r["piel"]}"/>'
        f"{barba}"
        f"{pecas}"
        # Cejas
        f'<path d="M{cx - sep - 24} {ojo_y - 30 + r["ceja"]} q24 -12 48 0" stroke="{r["pelo"]}" '
        f'stroke-width="8" fill="none" stroke-linecap="round"/>'
        f'<path d="M{cx + sep - 24} {ojo_y - 30 + r["ceja"]} q24 -12 48 0" stroke="{r["pelo"]}" '
        f'stroke-width="8" fill="none" stroke-linecap="round"/>'
        # Ojos
        f'<ellipse cx="{cx - sep}" cy="{ojo_y}" rx="15" ry="10" fill="#ffffff"/>'
        f'<ellipse cx="{cx + sep}" cy="{ojo_y}" rx="15" ry="10" fill="#ffffff"/>'
        f'<circle cx="{cx - sep}" cy="{ojo_y}" r="6.5" fill="#23262e"/>'
        f'<circle cx="{cx + sep}" cy="{ojo_y}" r="6.5" fill="#23262e"/>'
        # Nariz y boca
        f'<path d="M{cx - 6} {cy + 24} q8 16 14 2" stroke="{r["sombra"]}" stroke-width="5" '
        f'fill="none" stroke-linecap="round"/>'
        f'<path d="M{cx - 26} {cy + hh * 0.42} q26 {18 * r["sonrisa"]:.0f} 52 0" '
        f'stroke="#8a3a48" stroke-width="7" fill="none" stroke-linecap="round"/>'
        f"{pelo_delante}"
        f"{anteojos}"
        f"{aros}"
        "</g>"
        f'<rect width="800" height="1000" fill="url(#vig{uid})"/>'
        # Sello: en la demo, todo perfil generado se identifica como tal.
        '<g opacity="0.9">'
        '<rect x="24" y="24" width="196" height="38" rx="19" fill="#0a1020" opacity="0.55"/>'
        '<text x="122" y="49" font-family="system-ui,sans-serif" font-size="17" '
        'font-weight="700" fill="#ffffff" text-anchor="middle" letter-spacing="1">'
        "PERFIL SINTÉTICO</text></g>"
        "</svg>"
    )


def data_uri(clave: str, inicial: str, indice: int = 0, genero: str = "otro") -> str:
    crudo = svg(clave, inicial, indice, genero).encode("utf-8")
    return "data:image/svg+xml;base64," + base64.b64encode(crudo).decode("ascii")
