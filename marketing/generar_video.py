"""Videos de demostración de Matcher, en es/pt/en.

    python3 -m marketing.generar_video

Sale en `marketing/video/`:
  matcher_<idioma>_16x9.mp4    ~50 s, para la landing y YouTube
  matcher_<idioma>_9x16.mp4    ~35 s, para historias, Reels y TikTok

DE DÓNDE SALE LA IMAGEN
Las capturas son de la app CORRIENDO (`marketing/capturar.mjs`), no maquetas.
Un video de demo con pantallas dibujadas a mano envejece mal y miente sobre lo
que la app hace hoy; éste se regenera con dos comandos y queda al día.

LO QUE ESTE VIDEO NO TIENE, Y HAY QUE DECIRLO
**No tiene voz en off.** Se pidió con voz femenina y acá no hay ninguna voz
sintética que no suene a robot de 2005 — poner ésa es peor que no poner
ninguna. El video está armado para leerse sin audio, que además es como se
mira el 85 % del video en redes: el mensaje va en pantalla, con tiempo de
lectura calculado por largo de texto. Cuando haya una voz de verdad (locutora
o un TTS decente), se suma como pista de audio sin tocar la imagen.

Tampoco lleva música: una pista con licencia dudosa es un reclamo de derechos
en el primer video que ande bien.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from .generar_kit import PALETA, _degradado, _fuente, _rgb, logo

RAIZ = Path(__file__).resolve().parent.parent
CAPTURAS = RAIZ / "marketing" / "capturas"
SALIDA = RAIZ / "marketing" / "video"

FPS = 30

# Las escenas: qué captura se muestra y qué dice, en los tres idiomas.
#
# El texto NO son adjetivos ("la mejor app"): son los diferenciales reales,
# comprobables abriendo la app. Es la regla 10 del producto aplicada al
# marketing — lo que promete una pieza tiene que existir en el producto.
ESCENAS = [
    {
        "captura": "01-descubrir.png",
        "es": ("Los filtros se respetan", "Si pedís sólo hinchas de un equipo, no aparece nadie más."),
        "pt": ("Os filtros são respeitados", "Se você pedir só torcedores de um time, não aparece mais ninguém."),
        "en": ("Filters that actually hold", "Ask for one team's fans and nobody else shows up."),
    },
    {
        "captura": "02-filtros.png",
        "es": ("Todos los filtros, gratis", "Edad, altura, postura política, equipo, distancia. Sin muro de pago."),
        "pt": ("Todos os filtros, de graça", "Idade, altura, posição política, time, distância. Sem paywall."),
        "en": ("Every filter, free", "Age, height, politics, team, distance. No paywall."),
    },
    {
        "captura": "03-radar.png",
        "es": ("Quién hay cerca, ahora", "Mapa con las calles de cruce. Tu posición va redondeada."),
        "pt": ("Quem está perto, agora", "Mapa com as ruas do cruzamento. Sua posição vai arredondada."),
        "en": ("Who's nearby, right now", "A map down to the cross streets. Your position is rounded."),
    },
    {
        "captura": "05-crush.png",
        "es": ("Crush Time", "Adiviná cuál de las cuatro te dio like."),
        "pt": ("Crush Time", "Adivinhe qual das quatro te deu like."),
        "en": ("Crush Time", "Guess which of the four liked you."),
    },
    {
        "captura": "08-matches.png",
        "es": ("Cita a ciegas", "Primero la charla. Las fotos se revelan escribiendo."),
        "pt": ("Encontro às cegas", "Primeiro a conversa. As fotos se revelam conversando."),
        "en": ("Blind date", "Conversation first. Photos unlock as you both write."),
    },
    {
        "captura": "11-videollamada.png",
        "es": ("Videollamada antes de verse", "Jitsi, Meet, Zoom o Webex. El link aparece cuando aceptan los dos."),
        "pt": ("Videochamada antes de se ver", "Jitsi, Meet, Zoom ou Webex. O link aparece quando os dois aceitam."),
        "en": ("Video call before you meet", "Jitsi, Meet, Zoom or Webex. The link appears when both accept."),
    },
    {
        "captura": "06-vitrinas.png",
        "es": ("Segunda vuelta", "La gente que descartaste sin mirar, una semana después."),
        "pt": ("Segundo turno", "Quem você descartou sem olhar, uma semana depois."),
        "en": ("Second look", "The people you swiped past without looking, a week later."),
    },
    {
        "captura": "09-planes.png",
        "es": ("Desde USD 3,99", "Una fracción de lo que cobran las otras. Y podés no pagar nada."),
        "pt": ("A partir de USD 3,99", "Uma fração do que os outros cobram. E dá para não pagar nada."),
        "en": ("From USD 3.99", "A fraction of what the others charge. And you can pay nothing."),
    },
]

CIERRE = {
    "es": ("Matcher", "Web · Android · iOS · Windows"),
    "pt": ("Matcher", "Web · Android · iOS · Windows"),
    "en": ("Matcher", "Web · Android · iOS · Windows"),
}

# Tiempo en pantalla por escena. Se calcula por largo de texto y no es un
# número fijo: sin voz en off, la única forma de que una escena "dure lo que
# hay que leer" es medir lo que hay que leer. El piso es para que una frase
# corta no pase de largo antes de que el ojo llegue.
SEG_MINIMO = 3.4
SEG_POR_CARACTER = 0.030


def _segundos(titulo: str, bajada: str) -> float:
    return max(SEG_MINIMO, len(titulo + bajada) * SEG_POR_CARACTER)


def _sombra(caja: tuple[int, int], radio: int = 26) -> Image.Image:
    """Sombra difusa detrás del teléfono. Sin esto, la captura queda pegada al
    fondo como una calcomanía."""
    ancho, alto = caja
    borde = radio * 3
    img = Image.new("RGBA", (ancho + borde * 2, alto + borde * 2), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle(
        [borde, borde, borde + ancho, borde + alto], radius=38, fill=(0, 0, 0, 150)
    )
    return img.filter(ImageFilter.GaussianBlur(radio))


def _telefono(captura: Path, alto: int) -> Image.Image:
    """La captura dentro de un marco de teléfono, escalada a `alto` píxeles."""
    with Image.open(captura) as img:
        foto = img.convert("RGB")
    ancho = round(alto * foto.width / foto.height)
    foto = foto.resize((ancho, alto), Image.LANCZOS)

    marco = 10
    caja = Image.new("RGBA", (ancho + marco * 2, alto + marco * 2), (0, 0, 0, 0))
    ImageDraw.Draw(caja).rounded_rectangle(
        [0, 0, caja.width - 1, caja.height - 1], radius=44, fill=(24, 30, 38, 255)
    )
    # La captura se recorta con las mismas esquinas redondeadas que el marco:
    # pegarla cuadrada adentro de un marco redondo se ve en las cuatro puntas.
    mascara = Image.new("L", foto.size, 0)
    ImageDraw.Draw(mascara).rounded_rectangle(
        [0, 0, foto.width - 1, foto.height - 1], radius=34, fill=255
    )
    caja.paste(foto, (marco, marco), mascara)
    return caja


def _envolver(d: ImageDraw.ImageDraw, texto: str, fuente, ancho_max: int) -> list[str]:
    renglones, actual = [], ""
    for palabra in texto.split():
        prueba = f"{actual} {palabra}".strip()
        if d.textlength(prueba, font=fuente) <= ancho_max:
            actual = prueba
        else:
            renglones.append(actual)
            actual = palabra
    if actual:
        renglones.append(actual)
    return renglones


def _fondo(medida: tuple[int, int]) -> Image.Image:
    """Carbón con dos luces de fuego, igual que el `body::before` de la app."""
    ancho, alto = medida
    img = _degradado(medida, PALETA["navy-950"], PALETA["navy-900"], diagonal=False).convert("RGBA")
    luz = Image.new("RGBA", medida, (0, 0, 0, 0))
    d = ImageDraw.Draw(luz)
    for centro, color in (
        ((int(ancho * 0.08), int(alto * 0.04)), PALETA["coral-deep"]),
        ((int(ancho * 0.96), int(alto * 0.10)), PALETA["brasa"]),
    ):
        for i in range(34, 0, -1):
            r = ancho * 0.16 * i / 8
            d.ellipse(
                [centro[0] - r, centro[1] - r, centro[0] + r, centro[1] + r],
                fill=_rgb(color) + (3,),
            )
    return Image.alpha_composite(img, luz)


def cuadro_escena(medida: tuple[int, int], captura: Path, titulo: str, bajada: str,
                  vertical: bool) -> Image.Image:
    ancho, alto = medida
    img = _fondo(medida)
    d = ImageDraw.Draw(img)

    if vertical:
        alto_tel = int(alto * 0.55)
        tel = _telefono(captura, alto_tel)
        x = (ancho - tel.width) // 2
        y = int(alto * 0.34)
        f_tit = _fuente(int(ancho * 0.072), negrita=True)
        f_baj = _fuente(int(ancho * 0.040))
        margen = int(ancho * 0.09)
        tx, ty = margen, int(alto * 0.11)
        ancho_txt = ancho - margen * 2
    else:
        alto_tel = int(alto * 0.82)
        tel = _telefono(captura, alto_tel)
        x = int(ancho * 0.60)
        y = (alto - tel.height) // 2
        f_tit = _fuente(int(ancho * 0.050), negrita=True)
        f_baj = _fuente(int(ancho * 0.026))
        margen = int(ancho * 0.07)
        tx, ty = margen, int(alto * 0.30)
        ancho_txt = int(ancho * 0.48)

    sombra = _sombra(tel.size)
    img.alpha_composite(sombra, (x - (sombra.width - tel.width) // 2,
                                 y - (sombra.height - tel.height) // 2 + 14))
    img.alpha_composite(tel, (x, y))

    # Barrita de acento arriba del título: le da un ancla al bloque de texto,
    # que si no flota en el medio de la nada.
    d.rounded_rectangle([tx, ty - int(f_tit.size * 0.62), tx + int(f_tit.size * 1.5),
                         ty - int(f_tit.size * 0.42)], radius=6, fill=_rgb(PALETA["coral"]))

    yy = ty
    for renglon in _envolver(d, titulo, f_tit, ancho_txt):
        d.text((tx, yy), renglon, font=f_tit, fill=_rgb(PALETA["ink"]))
        yy += int(f_tit.size * 1.16)
    yy += int(f_tit.size * 0.28)
    for renglon in _envolver(d, bajada, f_baj, ancho_txt):
        d.text((tx, yy), renglon, font=f_baj, fill=_rgb(PALETA["muted"]))
        yy += int(f_baj.size * 1.36)

    return img.convert("RGB")


def cuadro_cierre(medida: tuple[int, int], titulo: str, bajada: str) -> Image.Image:
    ancho, alto = medida
    img = _fondo(medida)
    d = ImageDraw.Draw(img)

    marca = logo(int(min(ancho, alto) * 0.17), tinta="blanco", fondo="degradado")
    mascara = Image.new("L", marca.size, 0)
    ImageDraw.Draw(mascara).rounded_rectangle(
        [0, 0, marca.width - 1, marca.height - 1], radius=int(marca.width * 0.22), fill=255
    )
    img.paste(marca, ((ancho - marca.width) // 2, int(alto * 0.30)), mascara)

    f_tit = _fuente(int(min(ancho, alto) * 0.11), negrita=True)
    f_baj = _fuente(int(min(ancho, alto) * 0.037))
    for texto, fuente, dy, color in (
        (titulo, f_tit, 0.30 + 0.19, PALETA["ink"]),
        (bajada, f_baj, 0.30 + 0.32, PALETA["muted"]),
    ):
        an = d.textlength(texto, font=fuente)
        d.text(((ancho - an) / 2, alto * dy), texto, font=fuente, fill=_rgb(color))
    return img.convert("RGB")


def _escribir(cuadro: Image.Image, destino: Path, veces: int) -> None:
    """El mismo cuadro repetido: el video es de placas, no de animación.

    Se guarda UNA vez y se enlaza duro el resto. Escribir 90 PNG idénticos de
    2 MB por escena llenaba el disco del contenedor y tardaba más que el
    encode entero.
    """
    primero = destino.parent / f"{destino.stem}_000.png"
    cuadro.save(primero)
    for i in range(1, veces):
        copia = destino.parent / f"{destino.stem}_{i:03d}.png"
        if copia.exists():
            copia.unlink()
        copia.hardlink_to(primero)


def generar_video(idioma: str, vertical: bool, trabajo: Path) -> Path:
    medida = (1080, 1920) if vertical else (1920, 1080)
    sufijo = "9x16" if vertical else "16x9"
    cuadros = trabajo / f"{idioma}_{sufijo}"
    if cuadros.exists():
        shutil.rmtree(cuadros)
    cuadros.mkdir(parents=True)

    # En vertical se muestran menos escenas: un Reel de 50 segundos no lo mira
    # nadie. Se dejan las que más diferencian.
    escenas = ESCENAS if not vertical else [ESCENAS[i] for i in (0, 1, 5, 7)]

    n = 0
    for escena in escenas:
        titulo, bajada = escena[idioma]
        captura = CAPTURAS / escena["captura"]
        if not captura.exists():
            raise SystemExit(
                f"falta {captura}. Corré primero:\n"
                f"  python3 -m uvicorn webapp.backend.api:app --port 8899\n"
                f"  node marketing/capturar.mjs"
            )
        cuadro = cuadro_escena(medida, captura, titulo, bajada, vertical)
        _escribir(cuadro, cuadros / f"e{n:02d}", round(_segundos(titulo, bajada) * FPS))
        n += 1

    titulo, bajada = CIERRE[idioma]
    _escribir(cuadro_cierre(medida, titulo, bajada), cuadros / f"e{n:02d}", round(2.8 * FPS))

    SALIDA.mkdir(parents=True, exist_ok=True)
    destino = SALIDA / f"matcher_{idioma}_{sufijo}.mp4"
    lista = trabajo / f"{idioma}_{sufijo}.txt"
    lista.write_text(
        "".join(f"file '{p}'\n" for p in sorted(cuadros.glob("*.png"))), encoding="utf-8"
    )

    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-r", str(FPS), "-f", "concat", "-safe", "0", "-i", str(lista),
            # yuv420p + faststart: sin eso el video no abre en Safari ni en el
            # reproductor de Instagram, y "no se ve" es indistinguible de roto.
            "-c:v", "libx264", "-preset", "medium", "-crf", "21",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(destino),
        ],
        check=True,
    )

    # Copia en WebM/VP9 SÓLO del horizontal, que es el que va embebido en la
    # landing. No es un capricho: H.264 está patentado y hay Chromium armados
    # sin él (varias distros de Linux, el snap de Ubuntu, algunos navegadores
    # embebidos). En uno de esos, el `<video>` con MP4 solo no carga ni los
    # metadatos — se ve un rectángulo negro y parece que la web está rota.
    # Se detectó justamente así: el navegador de las pruebas devuelve "" para
    # `canPlayType('video/mp4; codecs=avc1')` y "probably" para VP9.
    # El MP4 va primero en el HTML igual, porque es el que quiere Safari.
    if not vertical:
        webm = destino.with_suffix(".webm")
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-r", str(FPS), "-f", "concat", "-safe", "0", "-i", str(lista),
                "-c:v", "libvpx-vp9", "-crf", "34", "-b:v", "0",
                "-deadline", "good", "-cpu-used", "4", "-row-mt", "1",
                "-pix_fmt", "yuv420p",
                str(webm),
            ],
            check=True,
        )
    return destino


def generar() -> list[Path]:
    if not shutil.which("ffmpeg"):
        raise SystemExit("falta ffmpeg: sudo apt-get install ffmpeg")
    trabajo = SALIDA / "_cuadros"
    hechos = []
    for idioma in ("es", "pt", "en"):
        for vertical in (False, True):
            hechos.append(generar_video(idioma, vertical, trabajo))
            print(f"  {hechos[-1].name}")
    shutil.rmtree(trabajo, ignore_errors=True)
    return hechos


if __name__ == "__main__":
    hechos = generar()
    print(f"\n{len(hechos)} videos en {SALIDA}", file=sys.stderr)
