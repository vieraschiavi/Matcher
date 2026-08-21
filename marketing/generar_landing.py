"""La web pública de Matcher, en es/pt/en.

    python3 -m marketing.generar_landing

Sale en `landing/<idioma>/index.html`, más `landing/media/` con los videos y
las capturas. `landing/index.html` redirige al idioma del navegador.

POR QUÉ SE GENERA Y NO SE EDITA A MANO
Tres HTML, tres idiomas, y los precios y las funciones cambian todas las
semanas. Editados a mano, a la segunda semana el precio del inglés no es el
del español y una función nueva figura en uno solo. Acá:

  · los PRECIOS y los cupos salen de `matcher.planes` — la misma fuente que
    cobra de verdad, así que la web no puede prometer un plan que no existe;
  · los COLORES salen de `theme.css` vía `generar_kit.PALETA`;
  · los VIDEOS y las capturas salen de la app corriendo.

Si tocás la landing, tocá este archivo y regenerá. Editar los HTML es perder
el cambio en la próxima corrida.

LA DEMO NO ES PÚBLICA NI DESCARGABLE
Decisión comercial: una demo abierta le regala el producto a la competencia.
Acá va el VIDEO (el resultado visual, que es lo que atrae) y un formulario para
pedir la demo en vivo. No hay botones de descarga, y no tienen que volver:
`tests/test_solicitudes.py::test_la_landing_no_ofrece_descargas` lo fija.

`URL_APP` es la del backend, a donde el formulario postea el pedido:

    MATCHER_URL_APP=https://tu-backend python3 -m marketing.generar_landing
"""

from __future__ import annotations

import html
import json
import os
import shutil
import subprocess
from pathlib import Path

from matcher import planes

from .generar_kit import PALETA

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "landing"
MEDIA = SALIDA / "media"
VIDEOS = RAIZ / "marketing" / "video"
CAPTURAS = RAIZ / "marketing" / "capturas"

IDIOMAS = ("es", "pt", "en")

URL_APP = os.getenv("MATCHER_URL_APP", "").strip()

# Capturas que se muestran en la galería. Se copian a `landing/media/`.
GALERIA = ["01-descubrir.png", "03-radar.png", "11-videollamada.png", "05-crush.png"]


# ---------------------------------------------------------------------------
# Textos
# ---------------------------------------------------------------------------
T = {
    "es": {
        "lang": "es",
        "titulo": "Matcher · los filtros se respetan",
        "meta": "App de citas con filtros duros —edad, altura, política, equipo, distancia— "
                "todos gratis, y planes pagos desde USD 3,99. Web, Android, iOS y Windows.",
        "hero_t": "Los filtros se respetan.",
        "hero_b": "Si pedís sólo hinchas de un equipo, no aparece nadie más. "
                  "Todos los filtros están en el plan gratis: se cobra volumen y "
                  "visibilidad, nunca el derecho a filtrar.",
        "ver_video": "Ver la demo",
        "descargas": "Descargar",
        "d_web": "Abrir en el navegador",
        "d_apk": "Android (APK)",
        "d_exe": "Windows (instalador)",
        "preparacion": "en preparación",
        "func_t": "Todo lo que hace",
        "func_b": "Nada de esto es una promesa: está en la app y se ve en el video de arriba.",
        "gal_t": "Cómo se ve",
        "planes_t": "Los planes",
        "planes_b": "El plan gratis alcanza para usar la app en serio. Se paga por volumen y "
                    "visibilidad, no por filtrar.",
        "mes": "por mes",
        "anual": "o {p} al año",
        "gratis": "Gratis",
        "comp_t": "Contra lo que cobran las otras",
        "comp_b": "Precios de lista aproximados en dólares, tomados de las páginas públicas de "
                  "cada app. <b>No están verificados</b> y cambian por país y por promoción: "
                  "están para dar una idea de escala, no como dato firme.",
        "comp_app": "App",
        "comp_precio": "Precio aproximado",
        "sint_t": "Los perfiles de la demo son sintéticos",
        "sint_b": "Las caras del pack son rostros generados, de personas que no existen, y cada "
                  "perfil de demostración va marcado como sintético dentro de la app. No hay "
                  "fotos de personas reales.",
        "demo_t": "Ver la demo",
        "demo_b": "La demo no es pública ni descargable: se muestra en vivo, uno a uno. Dejá tus datos y coordinamos.",
        "f_nombre": "Nombre y apellido",
        "f_email": "Email",
        "f_empresa": "Empresa",
        "f_pais": "País",
        "f_mensaje": "¿Qué te gustaría ver? (opcional)",
        "f_enviar": "Pedir la demo",
        "f_enviando": "Enviando…",
        "f_ok": "Recibimos tu pedido. Te escribimos para coordinar la demo.",
        "f_privacidad": "Usamos tus datos sólo para contactarte por la demo. Nada más.",
        "pie": "Matcher · web, Android, iOS y Windows",
        "nota_video": "Los videos no tienen voz en off ni música: se leen sin audio.",
    },
    "pt": {
        "lang": "pt",
        "titulo": "Matcher · os filtros são respeitados",
        "meta": "App de namoro com filtros duros —idade, altura, política, time, distância— "
                "todos de graça, e planos pagos a partir de USD 3,99. Web, Android, iOS e Windows.",
        "hero_t": "Os filtros são respeitados.",
        "hero_b": "Se você pedir só torcedores de um time, não aparece mais ninguém. "
                  "Todos os filtros estão no plano gratuito: cobra-se volume e "
                  "visibilidade, nunca o direito de filtrar.",
        "ver_video": "Ver a demo",
        "descargas": "Baixar",
        "d_web": "Abrir no navegador",
        "d_apk": "Android (APK)",
        "d_exe": "Windows (instalador)",
        "preparacion": "em preparação",
        "func_t": "Tudo o que faz",
        "func_b": "Nada disso é promessa: está no app e aparece no vídeo acima.",
        "gal_t": "Como fica",
        "planes_t": "Os planos",
        "planes_b": "O plano gratuito dá para usar o app de verdade. Paga-se por volume e "
                    "visibilidade, não por filtrar.",
        "mes": "por mês",
        "anual": "ou {p} por ano",
        "gratis": "Grátis",
        "comp_t": "Contra o que os outros cobram",
        "comp_b": "Preços de tabela aproximados em dólares, tirados das páginas públicas de cada "
                  "app. <b>Não estão verificados</b> e mudam por país e por promoção: servem "
                  "para dar noção de escala, não como dado firme.",
        "comp_app": "App",
        "comp_precio": "Preço aproximado",
        "sint_t": "Os perfis da demo são sintéticos",
        "sint_b": "Os rostos do pacote são gerados, de pessoas que não existem, e cada perfil de "
                  "demonstração vai marcado como sintético dentro do app. Não há fotos de "
                  "pessoas reais.",
        "demo_t": "Ver a demo",
        "demo_b": "A demo não é pública nem para baixar: mostramos ao vivo, um a um. Deixe seus dados e combinamos.",
        "f_nombre": "Nome e sobrenome",
        "f_email": "E-mail",
        "f_empresa": "Empresa",
        "f_pais": "País",
        "f_mensaje": "O que gostaria de ver? (opcional)",
        "f_enviar": "Pedir a demo",
        "f_enviando": "Enviando…",
        "f_ok": "Recebemos seu pedido. Entraremos em contato para combinar a demo.",
        "f_privacidad": "Usamos seus dados só para falar sobre a demo. Nada mais.",
        "pie": "Matcher · web, Android, iOS e Windows",
        "nota_video": "Os vídeos não têm narração nem música: leem-se sem áudio.",
    },
    "en": {
        "lang": "en",
        "titulo": "Matcher · filters that actually hold",
        "meta": "Dating app with hard filters —age, height, politics, team, distance— all free, "
                "and paid plans from USD 3.99. Web, Android, iOS and Windows.",
        "hero_t": "Filters that actually hold.",
        "hero_b": "Ask for one team's fans and nobody else shows up. Every filter is in the free "
                  "plan: you pay for volume and visibility, never for the right to filter.",
        "ver_video": "Watch the demo",
        "descargas": "Download",
        "d_web": "Open in the browser",
        "d_apk": "Android (APK)",
        "d_exe": "Windows (installer)",
        "preparacion": "coming soon",
        "func_t": "Everything it does",
        "func_b": "None of this is a promise: it is in the app and you can see it in the video above.",
        "gal_t": "What it looks like",
        "planes_t": "The plans",
        "planes_b": "The free plan is enough to use the app for real. You pay for volume and "
                    "visibility, not for filtering.",
        "mes": "per month",
        "anual": "or {p} a year",
        "gratis": "Free",
        "comp_t": "Against what the others charge",
        "comp_b": "Approximate list prices in dollars, taken from each app's public pages. "
                  "<b>They are not verified</b> and change by country and promotion: they are "
                  "here to give a sense of scale, not as hard data.",
        "comp_app": "App",
        "comp_precio": "Approximate price",
        "sint_t": "The demo profiles are synthetic",
        "sint_b": "The faces in the pack are generated — people who do not exist — and every demo "
                  "profile is marked as synthetic inside the app. There are no photos of real "
                  "people.",
        "demo_t": "See the demo",
        "demo_b": "The demo is not public and not downloadable: we show it live, one to one. Leave your details and we'll set it up.",
        "f_nombre": "Full name",
        "f_email": "Email",
        "f_empresa": "Company",
        "f_pais": "Country",
        "f_mensaje": "What would you like to see? (optional)",
        "f_enviar": "Request the demo",
        "f_enviando": "Sending…",
        "f_ok": "We got your request. We'll email you to set up the demo.",
        "f_privacidad": "We use your details only to contact you about the demo. Nothing else.",
        "pie": "Matcher · web, Android, iOS and Windows",
        "nota_video": "The videos have no voice-over and no music: they read without audio.",
    },
}

# Las funciones. Cada una tiene que existir en el producto — el módulo que la
# implementa va al lado a propósito, para que agregar una fila acá sin escribir
# el código sea evidente.
FUNCIONES = [
    ("filtros.py", "🎯",
     ("Filtros duros", "Filtros duros", "Hard filters"),
     ("Edad, altura, postura política, equipo de fútbol y distancia. El filtro descarta; "
      "no se compensa con ninguna otra afinidad.",
      "Idade, altura, posição política, time e distância. O filtro descarta; não se compensa "
      "com nenhuma outra afinidade.",
      "Age, height, politics, football team and distance. The filter discards; it is never "
      "traded off against some other affinity.")),
    ("planes.py", "🔓",
     ("Todos los filtros, gratis", "Todos os filtros, de graça", "Every filter, free"),
     ("El plan gratis tiene los filtros completos. Se cobra volumen, visibilidad y ver quién "
      "te dio like.",
      "O plano gratuito tem os filtros completos. Cobra-se volume, visibilidade e ver quem te "
      "deu like.",
      "The free plan has the complete set. You pay for volume, visibility and seeing who "
      "liked you.")),
    ("geo.py", "🌎",
     ("Tu ciudad primero", "Sua cidade primeiro", "Your city first"),
     ("Ciudad, país, región y mundo, en ese orden. Alguien de tu ciudad aparece antes que "
      "alguien de otro continente con más puntaje.",
      "Cidade, país, região e mundo, nessa ordem. Alguém da sua cidade aparece antes de alguém "
      "de outro continente com pontuação maior.",
      "City, country, region, world — in that order. Someone from your city comes before "
      "someone from another continent with a higher score.")),
    ("radar.py", "📍",
     ("Radar y mapa", "Radar e mapa", "Radar and map"),
     ("Quién hay cerca, con el mapa hasta las calles de cruce. Tu posición viaja redondeada a "
      "una celda, nunca exacta.",
      "Quem está perto, com o mapa até as ruas do cruzamento. Sua posição vai arredondada para "
      "uma célula, nunca exata.",
      "Who is nearby, with the map down to the cross streets. Your position travels rounded to "
      "a cell, never exact.")),
    ("cruces.py", "🔁",
     ("Te cruzaste con", "Você cruzou com", "You crossed paths with"),
     ("La gente con la que coincidiste en el mismo lugar, y cuántas veces.",
      "As pessoas com quem você coincidiu no mesmo lugar, e quantas vezes.",
      "The people you were in the same place as, and how many times.")),
    ("videollamada.py", "🎥",
     ("Videollamada antes de verse", "Videochamada antes de se ver", "Video call before you meet"),
     ("Jitsi, Meet, Zoom o Webex desde el chat del match. El link no existe hasta que aceptan "
      "los dos — ni para quien la propuso.",
      "Jitsi, Meet, Zoom ou Webex a partir do chat do match. O link não existe até os dois "
      "aceitarem — nem para quem propôs.",
      "Jitsi, Meet, Zoom or Webex from the match chat. The link does not exist until both "
      "accept — not even for whoever proposed it.")),
    ("aciegas.py", "🎭",
     ("Cita a ciegas", "Encontro às cegas", "Blind date"),
     ("Primero la charla. Las fotos no salen del servidor hasta que los dos escribieron lo "
      "suficiente.",
      "Primeiro a conversa. As fotos não saem do servidor até os dois escreverem o suficiente.",
      "Conversation first. Photos do not leave the server until you have both written enough.")),
    ("crushtime.py", "🎯",
     ("Crush Time", "Crush Time", "Crush Time"),
     ("Cuatro caras, una te dio like. Si acertás, es match instantáneo.",
      "Quatro rostos, um te deu like. Se acertar, é match instantâneo.",
      "Four faces, one of them liked you. Guess right and it is an instant match.")),
    ("segundavuelta.py", "↩️",
     ("Segunda vuelta", "Segundo turno", "Second look"),
     ("La gente que descartaste hace más de una semana y que sigue pasando tus filtros de hoy. "
      "Mirarla es gratis.",
      "Quem você descartou há mais de uma semana e que ainda passa nos seus filtros de hoje. "
      "Olhar é de graça.",
      "The people you passed on over a week ago who still pass today's filters. Looking is free.")),
    ("vitrinas.py", "🔥",
     ("Disponible hoy · Más likeados", "Disponível hoje · Mais curtidos", "Available today · Most liked"),
     ("Quién dijo que está libre hoy, y el top 200 por barrio, por ciudad o del mundo.",
      "Quem disse que está livre hoje, e o top 200 por bairro, por cidade ou do mundo.",
      "Who said they are free today, and the top 200 by neighbourhood, by city or worldwide.")),
    ("automatch.py", "✨",
     ("Match automático", "Match automático", "Automatic match"),
     ("El algoritmo empareja sin que nadie deslice, cuando la compatibilidad es alta de los dos "
      "lados.",
      "O algoritmo emparelha sem ninguém deslizar, quando a compatibilidade é alta dos dois lados.",
      "The algorithm pairs you up with nobody swiping, when compatibility is high on both sides.")),
    ("almacen.py", "🗑️",
     ("Borrar la cuenta de verdad", "Apagar a conta de verdade", "Really delete your account"),
     ("Se borran las fotos, la bio, la ubicación y los mensajes, y el email queda libre para "
      "volver a registrarte. No es un flag.",
      "Apagam-se as fotos, a bio, a localização e as mensagens, e o e-mail fica livre para você "
      "se registrar de novo. Não é um flag.",
      "Photos, bio, location and messages are deleted, and the email is freed so you can sign up "
      "again. It is not a flag.")),
]


def _e(texto: str) -> str:
    return html.escape(texto, quote=True)


def _precio(valor: float, idioma: str = "es") -> str:
    """El separador decimal cambia con el idioma.

    En inglés `USD 3,99` se lee como tres mil noventa y nueve o directamente
    como un error de tipeo; en español y portugués, `USD 3.99` es lo mismo al
    revés. La primera versión formateaba siempre con coma y la página en
    inglés mostraba el precio con coma en las tarjetas y con punto en la
    descripción — dos precios distintos para el mismo plan, en la misma
    página.
    """
    texto = f"{valor:,.2f}"  # 1,234.56 al estilo inglés
    if idioma != "en":
        texto = texto.replace(",", "@").replace(".", ",").replace("@", ".")
    return f"USD {texto}"


def _css() -> str:
    p = PALETA
    return f"""
:root {{
  --navy-950: {p['navy-950']}; --navy-900: {p['navy-900']}; --navy-800: {p['navy-800']};
  --ink: {p['ink']}; --muted: {p['muted']};
  --coral: {p['coral']}; --coral-deep: {p['coral-deep']}; --brasa: {p['brasa']};
  --line: #2c3947;
  --sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; background: var(--navy-950); color: var(--ink); font-family: var(--sans);
  font-size: 16px; line-height: 1.6; -webkit-font-smoothing: antialiased;
}}
/* Las dos luces de fuego del fondo de la app: la web y el producto tienen que
   verse del mismo lugar. */
body::before {{
  content: ""; position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background:
    radial-gradient(58vw 42vh at 12% -8%, rgba(216, 31, 61, .17), transparent 62%),
    radial-gradient(52vw 40vh at 96% 4%, rgba(255, 138, 61, .15), transparent 60%);
}}
main, header, footer {{ position: relative; z-index: 1; }}
a {{ color: inherit; }}
.envoltorio {{ max-width: 1080px; margin: 0 auto; padding: 0 22px; }}
header {{ padding: 22px 0; }}
.barra {{ display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }}
.marca {{ display: flex; align-items: center; gap: 11px; font-weight: 800; font-size: 20px; }}
.marca img {{ width: 34px; height: 34px; border-radius: 9px; }}
.idiomas {{ margin-left: auto; display: flex; gap: 8px; }}
.idiomas a {{
  text-decoration: none; color: var(--muted); font-size: 13px; font-weight: 700;
  border: 1px solid var(--line); border-radius: 999px; padding: 5px 12px;
}}
.idiomas a[aria-current] {{ color: var(--ink); border-color: var(--coral); }}
h1 {{ font-size: clamp(34px, 6vw, 60px); line-height: 1.06; letter-spacing: -.025em; margin: 26px 0 16px; }}
h2 {{ font-size: clamp(24px, 3.4vw, 34px); letter-spacing: -.02em; margin: 0 0 10px; }}
.bajada {{ color: var(--muted); font-size: clamp(16px, 2vw, 19px); max-width: 62ch; }}
section {{ padding: 56px 0; border-top: 1px solid var(--line); }}
section:first-of-type {{ border-top: none; }}
.btn {{
  display: inline-block; text-decoration: none; font-weight: 700; font-size: 15px;
  border: 1px solid var(--line); background: var(--navy-800); color: var(--ink);
  border-radius: 12px; padding: 13px 20px;
}}
.btn:hover {{ border-color: var(--muted); }}
.btn-primario {{
  background: linear-gradient(100deg, var(--brasa), var(--coral) 45%, var(--coral-deep));
  border-color: transparent; color: #fff;
}}
.btn-apagado {{ opacity: .5; cursor: not-allowed; }}
.btn-apagado em {{ font-style: normal; font-weight: 500; color: var(--muted); }}
.botones {{ display: flex; gap: 11px; flex-wrap: wrap; margin-top: 24px; }}
video {{
  width: 100%; border-radius: 16px; border: 1px solid var(--line);
  background: var(--navy-900); display: block; margin-top: 28px;
}}
.nota {{ color: var(--muted); font-size: 13.5px; margin-top: 10px; }}
.formulario {{
  display: grid; gap: 14px; margin-top: 26px;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}}
.formulario label {{ display: flex; flex-direction: column; gap: 6px; font-size: 13.5px; color: var(--muted); }}
.formulario .ancho {{ grid-column: 1 / -1; }}
.formulario input, .formulario textarea {{
  background: var(--navy-900); border: 1px solid var(--line); color: var(--ink);
  border-radius: 11px; padding: 12px 13px; font: inherit; font-size: 15px; width: 100%;
}}
.formulario input:focus, .formulario textarea:focus {{ outline: none; border-color: var(--coral); }}
/* La trampa para robots se saca de la vista SIN `display:none`: varios bots
   detectan el `display:none` y saltean el campo, que es justo lo que no
   queremos. Así lo llenan y quedan marcados. */
.formulario .trampa {{
  position: absolute; left: -9999px; width: 1px; height: 1px; opacity: 0;
}}
.rejilla {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(268px, 1fr)); margin-top: 28px; }}
.ficha {{ background: var(--navy-900); border: 1px solid var(--line); border-radius: 16px; padding: 20px; }}
.ficha .ico {{ font-size: 24px; }}
.ficha h3 {{ margin: 10px 0 7px; font-size: 17px; }}
.ficha p {{ margin: 0; color: var(--muted); font-size: 14.5px; }}
.ficha code {{ display: block; margin-top: 12px; color: #6f8296; font-size: 11.5px; }}
.galeria {{ display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); margin-top: 26px; }}
/* Recorte y tope de alto. Las capturas son de 412×900 (un teléfono entero):
   puestas a ancho completo daban cajas de 900 px de alto y la sección ocupaba
   tres pantallas de scroll con cuatro imágenes. */
.galeria img {{
  /* `height: auto` no es decorativo: el atributo `height` del <img> gana sobre
     `aspect-ratio` mientras la altura no sea auto. Sin esto la caja quedaba de
     249×900, la imagen entraba recortada A LO ANCHO y las capturas se veían
     con los bordes del teléfono cortados. */
  width: 100%; height: auto; aspect-ratio: 412 / 620;
  object-fit: cover; object-position: top;
  border-radius: 14px; border: 1px solid var(--line); display: block; background: var(--navy-900);
}}
.planes {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(270px, 1fr)); margin-top: 28px; align-items: start; }}
.plan {{ background: var(--navy-900); border: 1px solid var(--line); border-radius: 18px; padding: 24px; }}
.plan.destacado {{ border-color: var(--coral); }}
.plan h3 {{ margin: 0 0 4px; font-size: 18px; }}
.precio {{ font-size: 34px; font-weight: 800; letter-spacing: -.02em; }}
.precio small {{ font-size: 14px; font-weight: 600; color: var(--muted); }}
.plan ul {{ list-style: none; padding: 0; margin: 16px 0 0; }}
.plan li {{ color: var(--muted); font-size: 14.5px; padding: 6px 0 6px 22px; position: relative; }}
.plan li::before {{ content: "✓"; position: absolute; left: 0; color: var(--coral); font-weight: 800; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 22px; font-size: 15px; }}
th, td {{ text-align: left; padding: 11px 12px; border-bottom: 1px solid var(--line); }}
th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .06em; }}
.aviso {{
  margin-top: 22px; padding: 16px 18px; border-radius: 14px;
  border: 1px solid var(--line); background: var(--navy-900); color: var(--muted); font-size: 14.5px;
}}
footer {{ padding: 34px 0 48px; border-top: 1px solid var(--line); color: var(--muted); font-size: 14px; }}
@media (max-width: 640px) {{ section {{ padding: 40px 0; }} }}
"""


def pagina(idioma: str) -> str:
    t = T[idioma]
    i = IDIOMAS.index(idioma)

    fichas = "\n".join(
        f"""      <article class="ficha">
        <div class="ico" aria-hidden="true">{ico}</div>
        <h3>{_e(nombres[i])}</h3>
        <p>{_e(textos[i])}</p>
        <code>matcher/{_e(modulo)}</code>
      </article>"""
        for modulo, ico, nombres, textos in FUNCIONES
    )

    galeria = "\n".join(
        f'      <img src="../media/{_e(n)}" alt="" loading="lazy" width="824" height="1800">'
        for n in GALERIA
        if (CAPTURAS / n).exists()
    )

    tarjetas = []
    for codigo in ("gratis", "plus", "gold"):
        p = planes.PLANES[codigo]
        if p.precio_mes == 0:
            precio = f'<div class="precio">{_e(t["gratis"])}</div>'
        else:
            precio = (
                f'<div class="precio">{_e(_precio(p.precio_mes, idioma))} '
                f'<small>{_e(t["mes"])}</small></div>'
                f'<div class="nota">{_e(t["anual"].format(p=_precio(p.precio_anual, idioma)))}</div>'
            )
        items = "\n".join(f"          <li>{_e(d)}</li>" for d in p.destacados)
        tarjetas.append(
            f"""      <article class="plan{' destacado' if codigo == 'plus' else ''}">
        <h3>{_e(p.nombre)}</h3>
        {precio}
        <ul>
{items}
        </ul>
      </article>"""
        )

    filas = "\n".join(
        f"        <tr><td>{_e(c['app'])}</td>"
        f"<td>≈ {_e(_precio(c['precio_mes_aprox'], idioma))} / {_e(t['mes'])}</td></tr>"
        for c in planes.REFERENCIA_COMPETENCIA
    )
    filas += (
        f"\n        <tr><td><b>Matcher Plus</b></td>"
        f"<td><b>{_e(_precio(planes.PLANES['plus'].precio_mes, idioma))} / {_e(t['mes'])}</b></td></tr>"
    )

    # El formulario postea al backend, que vive en OTRO dominio que la
    # landing (la landing es estática). Sin `URL_APP` configurada no hay a
    # dónde mandar el pedido: se usa una ruta relativa para que al menos
    # funcione si algún día la landing se sirve desde el mismo proceso.
    api_js = json.dumps(URL_APP.rstrip("/") if URL_APP else "")
    enviando_js = json.dumps(t["f_enviando"])
    ok_js = json.dumps(t["f_ok"])

    # El `aria-current` se arma aparte y no dentro de la f-string: una f-string
    # no admite backslashes adentro de la expresión y las comillas escapadas lo
    # rompían en tiempo de importación.
    def _enlace_idioma(o: str) -> str:
        actual = ' aria-current="page"' if o == idioma else ""
        return f'<a href="../{o}/" hreflang="{o}"{actual}>{o.upper()}</a>'

    otros = "\n".join(_enlace_idioma(o) for o in IDIOMAS)

    return f"""<!doctype html>
<html lang="{t['lang']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(t['titulo'])}</title>
<meta name="description" content="{_e(t['meta'])}">
<meta name="theme-color" content="{PALETA['navy-950']}">
<meta property="og:title" content="{_e(t['titulo'])}">
<meta property="og:description" content="{_e(t['meta'])}">
<meta property="og:image" content="../media/portada.png">
<meta property="og:type" content="website">
<link rel="icon" href="../media/icono.png">
<style>{_css()}</style>
</head>
<body>
<header>
  <div class="envoltorio barra">
    <span class="marca"><img src="../media/icono.png" alt="">Matcher</span>
    <nav class="idiomas">{otros}</nav>
  </div>
</header>

<main>
<section class="envoltorio">
  <h1>{_e(t['hero_t'])}</h1>
  <p class="bajada">{_e(t['hero_b'])}</p>
  <div class="botones">
    <a class="btn btn-primario" href="#demo">{_e(t['demo_t'])}</a>
  </div>
  <!-- MP4 primero (lo que quiere Safari/iOS) y WebM detrás: hay Chromium
       armados sin H.264 y ahí el MP4 solo no carga ni los metadatos. El
       navegador se queda con el primero que puede reproducir. -->
  <video controls preload="metadata" poster="../media/poster_{idioma}.png"
         playsinline width="1920" height="1080">
    <source src="../media/matcher_{idioma}_16x9.mp4" type="video/mp4">
    <source src="../media/matcher_{idioma}_16x9.webm" type="video/webm">
  </video>
  <p class="nota">{_e(t['nota_video'])}</p>
</section>

<section class="envoltorio">
  <h2>{_e(t['func_t'])}</h2>
  <p class="bajada">{_e(t['func_b'])}</p>
  <div class="rejilla">
{fichas}
  </div>
</section>

<section class="envoltorio">
  <h2>{_e(t['gal_t'])}</h2>
  <div class="galeria">
{galeria}
  </div>
</section>

<section class="envoltorio">
  <h2>{_e(t['planes_t'])}</h2>
  <p class="bajada">{_e(t['planes_b'])}</p>
  <div class="planes">
{chr(10).join(tarjetas)}
  </div>
</section>

<section class="envoltorio">
  <h2>{_e(t['comp_t'])}</h2>
  <p class="bajada">{t['comp_b']}</p>
  <table>
    <thead><tr><th>{_e(t['comp_app'])}</th><th>{_e(t['comp_precio'])}</th></tr></thead>
    <tbody>
{filas}
    </tbody>
  </table>
</section>

<section class="envoltorio">
  <h2>{_e(t['sint_t'])}</h2>
  <p class="bajada">{_e(t['sint_b'])}</p>
</section>

<!-- LA DEMO NO ES PÚBLICA NI DESCARGABLE.
     El video de arriba muestra el resultado; la app andando se muestra en vivo.
     Una demo abierta le regala el producto a la competencia: quien entra se
     lleva las pantallas y los flujos sin dejar rastro y sin que nadie le venda
     nada. Acá queda registrado quién pidió y con qué mail. -->
<section class="envoltorio" id="demo">
  <h2>{_e(t['demo_t'])}</h2>
  <p class="bajada">{_e(t['demo_b'])}</p>
  <form class="formulario" id="form-demo" novalidate>
    <label>{_e(t['f_nombre'])}<input name="nombre" required autocomplete="name"></label>
    <label>{_e(t['f_email'])}<input name="email" type="email" required autocomplete="email"></label>
    <label>{_e(t['f_empresa'])}<input name="empresa" required autocomplete="organization"></label>
    <label>{_e(t['f_pais'])}<input name="pais" required autocomplete="country-name"></label>
    <label class="ancho">{_e(t['f_mensaje'])}<textarea name="mensaje" rows="3"></textarea></label>
    <!-- Trampa para robots: la persona no lo ve, así que no lo llena. -->
    <input name="web" class="trampa" tabindex="-1" autocomplete="off" aria-hidden="true">
    <div class="ancho">
      <button class="btn btn-primario" type="submit">{_e(t['f_enviar'])}</button>
      <span id="demo-estado" class="nota" role="status"></span>
    </div>
  </form>
  <p class="nota">{_e(t['f_privacidad'])}</p>
</section>
</main>

<script>
(function () {{
  var API = {api_js};
  var f = document.getElementById("form-demo");
  var estado = document.getElementById("demo-estado");
  if (!f) return;
  f.addEventListener("submit", function (e) {{
    e.preventDefault();
    var boton = f.querySelector("button[type=submit]");
    boton.disabled = true;
    estado.textContent = {enviando_js};
    var datos = {{}};
    new FormData(f).forEach(function (v, k) {{ datos[k] = v; }});
    fetch(API + "/api/demo/solicitar", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify(datos),
    }})
      .then(function (r) {{ return r.json().then(function (j) {{ return {{ ok: r.ok, j: j }}; }}); }})
      .then(function (r) {{
        if (!r.ok) throw new Error((r.j && r.j.detail) || "error");
        f.reset();
        estado.textContent = {ok_js};
      }})
      .catch(function (err) {{ estado.textContent = err.message; }})
      .finally(function () {{ boton.disabled = false; }});
  }});
}})();
</script>

<footer><div class="envoltorio">{_e(t['pie'])}</div></footer>
</body>
</html>
"""


def _indice() -> str:
    """Redirige al idioma del navegador. Sin JS quedaría siempre en español,
    así que hay un <noscript> con los tres enlaces a mano."""
    return """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Matcher</title>
<link rel="canonical" href="es/">
<script>
  var l = (navigator.language || "es").slice(0, 2).toLowerCase();
  location.replace((["es", "pt", "en"].indexOf(l) >= 0 ? l : "es") + "/");
</script>
</head>
<body>
<noscript>
  <p><a href="es/">Español</a> · <a href="pt/">Português</a> · <a href="en/">English</a></p>
</noscript>
</body>
</html>
"""


def generar() -> list[Path]:
    from .generar_kit import logo

    MEDIA.mkdir(parents=True, exist_ok=True)
    hechos: list[Path] = []

    for idioma in IDIOMAS:
        for nombre in (
            f"matcher_{idioma}_16x9.mp4",
            f"matcher_{idioma}_16x9.webm",
            f"matcher_{idioma}_9x16.mp4",
        ):
            origen = VIDEOS / nombre
            if origen.exists():
                shutil.copy2(origen, MEDIA / nombre)
                hechos.append(MEDIA / nombre)
    for nombre in GALERIA:
        if (CAPTURAS / nombre).exists():
            shutil.copy2(CAPTURAS / nombre, MEDIA / nombre)
            hechos.append(MEDIA / nombre)

    marca = logo(256, tinta="blanco", fondo="degradado")
    marca.save(MEDIA / "icono.png")
    hechos.append(MEDIA / "icono.png")

    # Poster del video: un CUADRO REAL del video, no una composición aparte.
    # La primera versión pegaba la captura sobre un lienzo vacío y el
    # reproductor mostraba un rectángulo medio vacío que no se parecía en nada
    # a lo que arrancaba al darle play — parecía que la web estaba rota.
    # Se saca del segundo 1: el 0 puede caer en el primer cuadro del fundido.
    for idioma in IDIOMAS:
        video = VIDEOS / f"matcher_{idioma}_16x9.mp4"
        if not video.exists():
            continue
        poster = MEDIA / f"poster_{idioma}.png"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", "1", "-i", str(video),
             "-frames:v", "1", str(poster)],
            check=True,
        )
        hechos.append(poster)
    if (MEDIA / "poster_es.png").exists():
        shutil.copy2(MEDIA / "poster_es.png", MEDIA / "portada.png")
        hechos.append(MEDIA / "portada.png")

    for idioma in IDIOMAS:
        carpeta = SALIDA / idioma
        carpeta.mkdir(parents=True, exist_ok=True)
        destino = carpeta / "index.html"
        destino.write_text(pagina(idioma), encoding="utf-8")
        hechos.append(destino)

    indice = SALIDA / "index.html"
    indice.write_text(_indice(), encoding="utf-8")
    hechos.append(indice)
    return hechos


if __name__ == "__main__":
    for ruta in generar():
        print(f"  {ruta.relative_to(RAIZ)}")
