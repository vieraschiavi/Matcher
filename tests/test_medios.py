"""Hasta 10 fotos y 2 videos cortos por usuario."""

import pytest

from matcher import medios
from matcher.modelos import MAX_FOTOS, MAX_SEGUNDOS_VIDEO, MAX_VIDEOS, DatosInvalidos


def test_tope_de_diez_fotos(hacer_perfil):
    p = hacer_perfil()
    p.fotos = []
    for i in range(MAX_FOTOS):
        medios.agregar_foto(p, f"https://x.test/{i}.jpg")
    assert len(p.fotos) == 10
    with pytest.raises(DatosInvalidos, match="10 fotos"):
        medios.agregar_foto(p, "https://x.test/11.jpg")


def test_tope_de_dos_videos(hacer_perfil):
    p = hacer_perfil()
    for i in range(MAX_VIDEOS):
        medios.agregar_video(p, f"https://x.test/{i}.mp4", segundos=12)
    assert len(p.videos) == 2
    with pytest.raises(DatosInvalidos, match="2 videos"):
        medios.agregar_video(p, "https://x.test/3.mp4", segundos=5)


def test_video_largo_se_rechaza(hacer_perfil):
    p = hacer_perfil()
    with pytest.raises(DatosInvalidos, match="segundos"):
        medios.agregar_video(p, "https://x.test/a.mp4", segundos=MAX_SEGUNDOS_VIDEO + 1)
    # Justo en el límite entra.
    medios.agregar_video(p, "https://x.test/b.mp4", segundos=MAX_SEGUNDOS_VIDEO)


def test_formatos_invalidos(hacer_perfil):
    p = hacer_perfil()
    with pytest.raises(DatosInvalidos, match="formato de foto"):
        medios.agregar_foto(p, "https://x.test/a.pdf")
    with pytest.raises(DatosInvalidos, match="formato de video"):
        medios.agregar_video(p, "https://x.test/a.avi")


def test_data_uri_se_acepta(hacer_perfil):
    """La demo y el alta desde el navegador guardan las fotos como data-URI."""
    p = hacer_perfil()
    p.fotos = []
    medios.agregar_foto(p, "data:image/jpeg;base64,/9j/4AAQSkZJRg")
    assert len(p.fotos) == 1


def test_el_svg_sólo_entra_del_lado_de_adentro(hacer_perfil):
    """ESTE TEST CAMBIÓ DE SIGNO, Y VALE LA PENA SABER POR QUÉ.

    Antes decía que un `data:image/svg+xml` se acepta, a secas. Un SVG no es
    una imagen como las otras: es un documento XML que puede traer `<script>`
    adentro. En un `<img>` no se ejecuta, pero basta que alguien abra la URL en
    una pestaña —o que un cliente futuro la meta en un `<object>`— para que sea
    XSS con la cara de una foto de perfil.

    La app SÍ genera SVG: `avatares.py` arma el avatar de respaldo cuando no
    hay pack de caras. Eso es contenido nuestro y sigue entrando. Lo que ya no
    entra es un SVG que suba alguien, y el endpoint HTTP nunca pasa
    `confiable=True`.
    """
    p = hacer_perfil()
    p.fotos = []
    with pytest.raises(DatosInvalidos):
        medios.agregar_foto(p, "data:image/svg+xml;base64,AAAA")

    medios.agregar_foto(p, "data:image/svg+xml;base64,AAAA", confiable=True)
    assert len(p.fotos) == 1


def test_el_endpoint_de_fotos_no_marca_nada_como_confiable():
    """`confiable=True` en un handler HTTP sería exactamente el agujero que
    este parámetro existe para cerrar."""
    from pathlib import Path

    api = (
        Path(__file__).resolve().parents[1] / "webapp" / "backend" / "api.py"
    ).read_text(encoding="utf-8")
    assert "confiable=True" not in api, (
        "la API marca contenido de usuario como generado por el programa"
    )


def test_peso_maximo(hacer_perfil):
    p = hacer_perfil()
    p.fotos = []
    with pytest.raises(DatosInvalidos, match="8 MB"):
        medios.agregar_foto(p, "https://x.test/a.jpg", bytes_=9 * 1024 * 1024)
    with pytest.raises(DatosInvalidos, match="40 MB"):
        medios.agregar_video(p, "https://x.test/a.mp4", bytes_=41 * 1024 * 1024)


def test_borrar_renumera_para_no_dejar_huecos(hacer_perfil):
    p = hacer_perfil()
    p.fotos = []
    for i in range(4):
        medios.agregar_foto(p, f"https://x.test/{i}.jpg")
    del_id = p.fotos[1].id
    assert medios.borrar(p, del_id)
    assert [f.orden for f in p.fotos] == [0, 1, 2]
    assert not medios.borrar(p, "no-existe")


def test_reordenar_pone_la_portada_primero(hacer_perfil):
    p = hacer_perfil()
    p.fotos = []
    for i in range(3):
        medios.agregar_foto(p, f"https://x.test/{i}.jpg")
    tercera = p.fotos[2].id
    medios.reordenar(p, [tercera])
    assert p.fotos[0].id == tercera
    assert p.portada == "https://x.test/2.jpg"
    # Los que no vinieron en la lista quedan detrás, no se pierden.
    assert len(p.fotos) == 3


def test_perfil_sin_portada_no_esta_completo(hacer_perfil):
    p = hacer_perfil()
    assert p.completo
    p.fotos = []
    assert not p.completo
