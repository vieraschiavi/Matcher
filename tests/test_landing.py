"""La web pública.

Lo que estos tests impiden, que es lo que rompe una landing en la práctica:

- que el precio de la web deje de ser el precio que cobra la app;
- que una función figure en un idioma y falte en otro;
- que se publique un precio de la competencia como si fuera un dato firme
  (eso trae una carta documento, no un mail);
- que un botón de descarga apunte a una URL que devuelve 404;
- que se filtren datos bancarios en una página pública.

La landing se GENERA. Estos tests corren el generador en memoria y miran el
HTML que sale, así que no dependen de que alguien se haya acordado de
regenerar antes de commitear.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from marketing import generar_landing as gl
from matcher import planes

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def paginas() -> dict[str, str]:
    return {idioma: gl.pagina(idioma) for idioma in gl.IDIOMAS}


def test_estan_los_tres_idiomas(paginas):
    assert set(paginas) == {"es", "pt", "en"}
    for idioma, html in paginas.items():
        assert f'<html lang="{idioma}"' in html


def test_el_precio_de_la_web_es_el_que_cobra_la_app(paginas):
    """La landing no puede prometer un precio que la pasarela no cobra. Sale de
    `matcher.planes`, la misma fuente del checkout."""
    for idioma, html in paginas.items():
        for codigo in ("plus", "gold"):
            p = planes.PLANES[codigo]
            esperado = gl._precio(p.precio_mes, idioma)
            assert esperado in html, f"{idioma}: no figura {esperado} para {codigo}"
            assert p.nombre in html


def test_el_separador_decimal_sigue_al_idioma():
    """`USD 3,99` en inglés se lee como un error de tipeo, y `USD 3.99` en
    español también. La primera versión formateaba siempre con coma: la página
    en inglés mostraba coma en las tarjetas y punto en la descripción."""
    assert gl._precio(3.99, "en") == "USD 3.99"
    assert gl._precio(3.99, "es") == "USD 3,99"
    assert gl._precio(3.99, "pt") == "USD 3,99"
    assert gl._precio(1234.5, "en") == "USD 1,234.50"
    assert gl._precio(1234.5, "es") == "USD 1.234,50"


def test_cada_pagina_usa_su_propio_separador(paginas):
    """Que no quede una tarjeta con coma y la de al lado con punto."""
    assert "USD 3.99" in paginas["en"] and "USD 3,99" not in paginas["en"]
    for idioma in ("es", "pt"):
        assert "USD 3,99" in paginas[idioma] and "USD 3.99" not in paginas[idioma]


def test_ningun_precio_cableado_a_mano():
    """Si alguien escribe un precio en los textos en vez de leerlo de `planes`,
    se desincroniza al primer cambio de tarifa. Se permite en la bajada de
    marketing (donde dice 'desde USD 3,99') SÓLO si coincide con el plan."""
    for idioma, t in gl.T.items():
        # Se compara contra el precio formateado EN ESE IDIOMA: el inglés usa
        # punto decimal y el español coma, así que un único valor esperado
        # marcaría como error el formato correcto de una de las dos páginas.
        desde = gl._precio(planes.PLANES["plus"].precio_mes, idioma)
        for clave, texto in t.items():
            if not isinstance(texto, str):
                continue
            for hallado in re.findall(r"USD\s?\d+[.,]\d\d", texto):
                assert hallado == desde, (
                    f"{idioma}.{clave} tiene el precio {hallado!r} escrito a mano "
                    f"y el plan cuesta {desde}"
                )


def test_todas_las_funciones_existen_en_el_codigo():
    """Cada ficha nombra el módulo que la implementa. Una función anunciada sin
    módulo es una promesa sin producto (regla 10)."""
    for modulo, _ico, nombres, textos in gl.FUNCIONES:
        assert (RAIZ / "matcher" / modulo).exists(), f"la landing anuncia {modulo}, que no existe"
        assert len(nombres) == len(textos) == 3, f"{modulo} no está en los tres idiomas"
        for texto in nombres + textos:
            assert texto.strip(), f"{modulo} tiene un texto vacío"


def test_las_funciones_nuevas_estan_anunciadas():
    """Las que se agregaron y hay que mostrar sí o sí."""
    modulos = {m for m, *_ in gl.FUNCIONES}
    for esperado in ("videollamada.py", "segundavuelta.py", "vitrinas.py", "aciegas.py",
                     "crushtime.py", "radar.py"):
        assert esperado in modulos, f"la landing no habla de {esperado}"


def test_la_misma_cantidad_de_funciones_en_los_tres_idiomas(paginas):
    cuentas = {i: h.count('class="ficha"') for i, h in paginas.items()}
    assert len(set(cuentas.values())) == 1, f"distinta cantidad de fichas por idioma: {cuentas}"
    assert cuentas["es"] == len(gl.FUNCIONES)


def test_los_precios_de_la_competencia_van_como_aproximados(paginas):
    """`REFERENCIA_COMPETENCIA` está marcada `verificado: False`. Publicarla
    como dato firme es exactamente lo que la regla 10 prohíbe."""
    assert all(not c["verificado"] for c in planes.REFERENCIA_COMPETENCIA)
    for idioma, html in paginas.items():
        assert "≈" in html, f"{idioma}: los precios de la competencia no están marcados"
        aviso = gl.T[idioma]["comp_b"].lower()
        assert any(p in aviso for p in ("no están verificados", "não estão verificados",
                                        "not verified")), f"{idioma}: falta el aviso"


def test_un_boton_sin_url_no_es_un_enlace_roto(monkeypatch):
    """Sin URL configurada el botón sale apagado, no apuntando a '#' ni a una
    URL que da 404."""
    monkeypatch.setattr(gl, "URL_EXE", "")
    html = gl.pagina("es")
    assert 'href="#"' not in html
    assert "btn-apagado" in html

    monkeypatch.setattr(gl, "URL_EXE", "https://example.test/Matcher.exe")
    html = gl.pagina("es")
    assert 'href="https://example.test/Matcher.exe"' in html


def test_los_videos_referenciados_existen(paginas):
    """Un `<source>` que apunta a un archivo que no está deja un rectángulo
    negro en la portada."""
    for idioma, html in paginas.items():
        fuentes = re.findall(r'<source src="\.\./media/([^"]+)"', html)
        assert fuentes, f"{idioma}: el video no tiene ninguna fuente"
        for nombre in fuentes:
            assert (gl.VIDEOS / nombre).exists() or (gl.MEDIA / nombre).exists(), (
                f"{idioma}: falta {nombre}. Corré `python3 -m marketing.generar_video`"
            )


def test_el_video_tiene_respaldo_sin_h264(paginas):
    """Hay Chromium armados sin H.264 (varias distros, el snap de Ubuntu). Ahí
    el MP4 solo no carga ni los metadatos: se ve un rectángulo negro y parece
    que la web está rota. Se detectó con el navegador de las pruebas."""
    for idioma, html in paginas.items():
        assert 'type="video/mp4"' in html, f"{idioma}: falta el MP4"
        assert 'type="video/webm"' in html, f"{idioma}: falta el respaldo WebM"
        assert html.index('type="video/mp4"') < html.index('type="video/webm"'), (
            "el MP4 va primero: es el que quiere Safari"
        )


def test_la_paleta_de_la_web_es_la_de_la_app():
    from marketing.generar_kit import PALETA

    css = gl._css()
    for token in ("navy-950", "coral", "brasa"):
        assert PALETA[token] in css, f"la web no usa el {token} de la app"
    assert "#8e5bef" not in css, "volvió el violeta de la paleta vieja"


def test_la_landing_no_publica_datos_bancarios(paginas):
    """El repositorio es público y una landing se indexa el mismo día. La
    cuenta de cobro se configura en el panel de la pasarela, nunca en el
    código ni en una página."""
    prohibido = re.compile(
        r"\b(iban|swift|bic)\b|\bcbu\b|\bnro\.?\s*de\s*cuenta\b|\bn[úu]mero\s+de\s+cuenta\b",
        re.I,
    )
    for idioma, html in paginas.items():
        assert not prohibido.search(html), f"{idioma}: hay algo que parece un dato bancario"
        # Una tira de 7+ dígitos seguidos no tiene por qué estar en una landing.
        for numero in re.findall(r"(?<!\d)\d{7,}(?!\d)", re.sub(r"<[^>]+>", " ", html)):
            pytest.fail(f"{idioma}: número sospechoso en el texto: {numero}")


def test_se_declara_que_los_perfiles_de_la_demo_son_sinteticos(paginas):
    """Regla 5 del producto, y también lo correcto: quien entra tiene que saber
    que las caras del pack son generadas."""
    for idioma, html in paginas.items():
        assert any(p in html.lower() for p in ("sintétic", "sintétic", "synthetic")), idioma


def test_el_indice_ofrece_los_tres_idiomas_sin_javascript():
    """El redirector usa JS. Sin `<noscript>`, un buscador o un navegador con
    JS apagado se queda en una página en blanco."""
    indice = gl._indice()
    assert "<noscript>" in indice
    for idioma in gl.IDIOMAS:
        assert f'href="{idioma}/"' in indice
