"""Kit de marca y de redes de Matcher.

Genera todo a partir de UNA fuente: la paleta y el logo que ya usa la app. No
se dibujan piezas a mano en un editor porque a la segunda semana el coral del
banner no es el coral de la app y nadie sabe cuál está bien. Si cambia
`theme.css`, se corre esto de nuevo y el kit entero queda al día.

    python3 -m marketing.generar_kit

Sale en `marketing/kit/`:
  logo/      el logo en varias tintas y tamaños, más el ícono de la app
  redes/     posts 1080×1080, historias/reels 1080×1920, portada OG 1200×630
  paleta/    muestrario de color con los códigos
  MARCA.md   qué es cada cosa y cómo usarla

Los textos de las piezas van en es/pt/en, igual que la app: el nombre del
producto no cambia, pero el claim sí.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "marketing" / "kit"

# ---------------------------------------------------------------------------
# Paleta — los mismos valores que `webapp/frontend/src/theme.css`
# ---------------------------------------------------------------------------
PALETA = {
    "coral": "#ff4d6d",
    "coral-deep": "#c9184a",
    "violeta": "#8e5bef",
    "azul": "#5b8def",
    "navy-950": "#120d1c",
    "navy-900": "#1a1226",
    "navy-800": "#241a33",
    "ink": "#fbf5f7",
    "muted": "#b6a5c4",
    "amber": "#f2b441",
    "green": "#7cc242",
}

CLAIMS = {
    "es": [
        ("Los filtros se respetan.", "Si pedís hinchas de Peñarol, no aparece nadie más."),
        ("Todos los filtros, gratis.", "Se cobra volumen y visibilidad. Nunca el derecho a filtrar."),
        ("Desde USD 3,99.", "Una fracción de lo que cobran las otras."),
        ("Quién hay cerca, ahora.", "Mapa y cruces reales, con tu posición redondeada."),
    ],
    "pt": [
        ("Os filtros são respeitados.", "Se você pedir torcedores de um time, não aparece mais ninguém."),
        ("Todos os filtros, de graça.", "Cobra-se volume e visibilidade. Nunca o direito de filtrar."),
        ("A partir de USD 3,99.", "Uma fração do que os outros cobram."),
        ("Quem está perto, agora.", "Mapa e cruzamentos reais, com sua posição arredondada."),
    ],
    "en": [
        ("Filters that actually hold.", "Ask for one team's fans and nobody else shows up."),
        ("Every filter, free.", "You pay for volume and visibility. Never for filtering."),
        ("From USD 3.99.", "A fraction of what the others charge."),
        ("Who's nearby, right now.", "A real map and real crossings, with your position rounded."),
    ],
}


def _fuente(tam: int, negrita: bool = False):
    """La fuente del sistema. Se prueban varias rutas porque el contenedor de
    CI no tiene las mismas que una máquina de escritorio; si no hay ninguna,
    Pillow cae a su bitmap interna y las piezas salen igual (feas, pero salen)
    en vez de reventar el build."""
    candidatas = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if negrita
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if negrita
        else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for ruta in candidatas:
        if Path(ruta).exists():
            return ImageFont.truetype(ruta, tam)
    return ImageFont.load_default(tam)


def _rgb(hexa: str) -> tuple[int, int, int]:
    hexa = hexa.lstrip("#")
    return tuple(int(hexa[i: i + 2], 16) for i in (0, 2, 4))


def _degradado(tam: tuple[int, int], desde: str, hasta: str, diagonal: bool = True) -> Image.Image:
    """Degradado lineal. Pillow no trae uno, y hacerlo por píxel en una pieza
    de 1080×1920 tarda segundos: se dibuja chico y se escala."""
    ancho, alto = 64, 64
    base = Image.new("RGB", (ancho, alto))
    d = ImageDraw.Draw(base)
    a, b = _rgb(desde), _rgb(hasta)
    for i in range(ancho + alto):
        t = i / (ancho + alto - 1)
        color = tuple(round(a[c] + (b[c] - a[c]) * t) for c in range(3))
        if diagonal:
            d.line([(i, 0), (0, i)], fill=color)
        else:
            d.line([(0, i), (ancho, i)], fill=color)
    return base.resize(tam, Image.LANCZOS)


def _corazon_partido(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float, color, hueco: int = 0):
    """El logo: un corazón partido al medio, con las dos mitades separadas.

    Es la idea de la marca en una forma — dos partes que se encuentran. Se
    dibuja con la paramétrica del corazón y no con curvas a mano para que
    escale a cualquier tamaño sin deformarse.
    """
    for signo in (-1, 1):
        puntos = []
        for paso in range(0, 181):
            ang = math.radians(paso if signo > 0 else 360 - paso)
            x = 16 * math.sin(ang) ** 3
            y = 13 * math.cos(ang) - 5 * math.cos(2 * ang) - 2 * math.cos(3 * ang) - math.cos(4 * ang)
            puntos.append((cx + x * r / 16 + signo * hueco, cy - y * r / 16))
        # Se cierra por el eje para que cada mitad sea un polígono lleno.
        puntos.append((cx + signo * hueco, cy + r))
        d.polygon(puntos, fill=color)


def logo(tam: int = 512, fondo: str | None = None, tinta: str = "blanco") -> Image.Image:
    img = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    if fondo == "degradado":
        img.paste(_degradado((tam, tam), PALETA["coral"], PALETA["violeta"]).convert("RGBA"), (0, 0))
    elif fondo:
        img.paste(Image.new("RGBA", (tam, tam), _rgb(PALETA[fondo]) + (255,)), (0, 0))

    d = ImageDraw.Draw(img)
    color = {
        "blanco": _rgb(PALETA["ink"]),
        "coral": _rgb(PALETA["coral"]),
        "navy": _rgb(PALETA["navy-950"]),
    }[tinta]
    _corazon_partido(d, tam / 2, tam * 0.47, tam * 0.30, color + (255,), hueco=round(tam * 0.05))
    return img


def _texto_envuelto(d, xy, texto, fuente, ancho_max, relleno, interlineado=1.22):
    """Rompe en renglones por ancho real. Sin esto el claim se sale de la pieza
    en portugués, que es sistemáticamente más largo que el español."""
    palabras, renglones, actual = texto.split(), [], ""
    for p in palabras:
        prueba = f"{actual} {p}".strip()
        if d.textlength(prueba, font=fuente) <= ancho_max:
            actual = prueba
        else:
            renglones.append(actual)
            actual = p
    renglones.append(actual)
    x, y = xy
    alto = fuente.size * interlineado
    for r in renglones:
        d.text((x, y), r, font=fuente, fill=relleno)
        y += alto
    return y


def pieza(ancho: int, alto: int, titulo: str, bajada: str, etiqueta: str) -> Image.Image:
    img = _degradado((ancho, alto), PALETA["navy-950"], PALETA["navy-800"], diagonal=False).convert("RGBA")
    d = ImageDraw.Draw(img)

    # Un halo coral arriba a la derecha: rompe el fondo plano sin tapar el
    # texto, que es donde termina cualquier pieza hecha con un degradado solo.
    halo = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    hd = ImageDraw.Draw(halo)
    for i in range(28, 0, -1):
        r = ancho * 0.10 * i / 6
        hd.ellipse(
            [ancho * 0.82 - r, alto * 0.13 - r, ancho * 0.82 + r, alto * 0.13 + r],
            fill=_rgb(PALETA["coral"]) + (4,),
        )
    img.alpha_composite(halo)

    margen = round(ancho * 0.085)
    marca = logo(round(ancho * 0.13), tinta="coral")
    img.alpha_composite(marca, (margen, margen))

    d.text(
        (margen + round(ancho * 0.155), margen + round(ancho * 0.035)),
        "Matcher",
        font=_fuente(round(ancho * 0.062), negrita=True),
        fill=_rgb(PALETA["ink"]),
    )

    y = alto * (0.60 if alto > ancho else 0.44)
    y = _texto_envuelto(
        d, (margen, y), titulo,
        _fuente(round(ancho * 0.088), negrita=True), ancho - margen * 2, _rgb(PALETA["ink"]),
    )
    _texto_envuelto(
        d, (margen, y + ancho * 0.022), bajada,
        _fuente(round(ancho * 0.040)), ancho - margen * 2, _rgb(PALETA["muted"]),
    )

    # Etiqueta al pie, para saber de un vistazo qué pieza es cuál.
    f = _fuente(round(ancho * 0.030), negrita=True)
    largo = d.textlength(etiqueta, font=f)
    caja = [margen, alto - margen - round(ancho * 0.062), margen + largo + round(ancho * 0.05),
            alto - margen]
    d.rounded_rectangle(caja, radius=round(ancho * 0.031), fill=_rgb(PALETA["coral-deep"]))
    d.text((margen + round(ancho * 0.025), alto - margen - round(ancho * 0.048)),
           etiqueta, font=f, fill=_rgb(PALETA["ink"]))
    return img


def muestrario() -> Image.Image:
    ancho, alto, fila = 1200, 130 * len(PALETA) + 140, 130
    img = Image.new("RGB", (ancho, alto), _rgb(PALETA["navy-950"]))
    d = ImageDraw.Draw(img)
    d.text((60, 46), "Matcher · paleta", font=_fuente(46, negrita=True), fill=_rgb(PALETA["ink"]))
    y = 130
    for nombre, hexa in PALETA.items():
        d.rounded_rectangle([60, y, 260, y + 92], radius=16, fill=_rgb(hexa))
        d.text((300, y + 16), nombre, font=_fuente(34, negrita=True), fill=_rgb(PALETA["ink"]))
        d.text((300, y + 56), hexa.upper(), font=_fuente(28), fill=_rgb(PALETA["muted"]))
        y += fila
    return img


def generar() -> list[Path]:
    hechos: list[Path] = []
    for sub in ("logo", "redes", "paleta"):
        (SALIDA / sub).mkdir(parents=True, exist_ok=True)

    # -- logo -------------------------------------------------------------
    for nombre, kw in {
        "logo_coral": {"tinta": "coral"},
        "logo_blanco": {"tinta": "blanco"},
        "logo_navy": {"tinta": "navy"},
        "logo_app": {"tinta": "blanco", "fondo": "degradado"},
        "logo_sobre_navy": {"tinta": "coral", "fondo": "navy-950"},
    }.items():
        for tam in (256, 512, 1024):
            ruta = SALIDA / "logo" / f"{nombre}_{tam}.png"
            logo(tam, **kw).save(ruta)
            hechos.append(ruta)

    # -- redes ------------------------------------------------------------
    medidas = {
        "post": (1080, 1080),      # feed cuadrado
        "historia": (1080, 1920),  # historias y reels
        "portada": (1200, 630),    # Open Graph / link en X y LinkedIn
    }
    for idioma, claims in CLAIMS.items():
        for i, (titulo, bajada) in enumerate(claims, 1):
            for tipo, (an, al) in medidas.items():
                ruta = SALIDA / "redes" / f"{tipo}_{idioma}_{i}.png"
                pieza(an, al, titulo, bajada, idioma.upper()).save(ruta)
                hechos.append(ruta)

    # -- paleta -----------------------------------------------------------
    ruta = SALIDA / "paleta" / "paleta.png"
    muestrario().save(ruta)
    hechos.append(ruta)

    (SALIDA / "MARCA.md").write_text(_guia(), encoding="utf-8")
    hechos.append(SALIDA / "MARCA.md")
    return hechos


def _guia() -> str:
    filas = "\n".join(f"| `{n}` | `{h.upper()}` |" for n, h in PALETA.items())
    return f"""# Matcher · kit de marca

> Generado por `python3 -m marketing.generar_kit`. **No edites estos archivos a
> mano**: se regeneran y perdés el cambio. Si hay que tocar un color, se toca
> en `webapp/frontend/src/theme.css` y en `PALETA` de este script, que son la
> misma paleta que usa la app.

## Logo

Un corazón partido al medio, con las dos mitades separadas: dos partes que se
encuentran. Se dibuja con la paramétrica del corazón, así que escala a
cualquier tamaño sin deformarse.

| Archivo | Cuándo |
|---|---|
| `logo_coral_*.png` | Por defecto, sobre fondo claro u oscuro |
| `logo_blanco_*.png` | Sobre foto o sobre el coral |
| `logo_navy_*.png` | Sobre fondo claro, cuando el coral compite con la foto |
| `logo_app_*.png` | Ícono de la app: el logo blanco sobre el degradado |
| `logo_sobre_navy_*.png` | Avatar de redes |

Aire mínimo alrededor: la mitad del ancho del logo. Nunca lo estires, ni le
cambies el color a uno que no esté en la paleta, ni lo pongas sobre una foto
sin oscurecerla antes.

## Paleta

| Token | Hex |
|---|---|
{filas}

El navy es la base heredada de Kobra; el coral y el violeta son propios de
Matcher. **No inventar colores fuera de esta tabla** — es la misma regla que
tiene la app en `theme.css`.

## Piezas de redes

Tres medidas, en los tres idiomas del producto (es/pt/en):

| Archivo | Medida | Para |
|---|---|---|
| `post_<idioma>_<n>.png` | 1080×1080 | Feed de Instagram, Facebook |
| `historia_<idioma>_<n>.png` | 1080×1920 | Historias, Reels, TikTok |
| `portada_<idioma>_<n>.png` | 1200×630 | Open Graph: el link en X, LinkedIn, WhatsApp |

Los cuatro mensajes son los diferenciales reales del producto, no adjetivos:
los filtros se respetan, todos los filtros están en el plan gratis, el precio,
y el mapa de quién hay cerca.

## Lo que NO se promete

Los precios de la competencia que aparecen en la app van marcados como
referencia aproximada y sin verificar. **No los pongas como dato duro en una
pieza de redes** — es el tipo de afirmación que trae una carta documento.
"""


if __name__ == "__main__":
    for ruta in generar():
        print(ruta.relative_to(RAIZ))
