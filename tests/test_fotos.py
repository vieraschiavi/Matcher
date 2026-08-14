"""La fuente de fotos de la demo."""

from pathlib import Path

from matcher import demo, fotos
from matcher.almacen import Almacen


def _jpg_falso(ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(b"\xff\xd8\xff\xe0falso")


def test_el_pack_incluido_existe_y_esta_separado_por_genero():
    cat = fotos.catalogo(fotos.PACK_INCLUIDO)
    assert "mujer" in cat and "hombre" in cat
    assert len(cat["mujer"]) >= 20
    assert len(cat["hombre"]) >= 15


def test_las_tomas_de_una_misma_persona_quedan_agrupadas(tmp_path):
    """Si no se agrupan, el carrusel de un perfil mezcla caras distintas y se
    nota al instante que los perfiles son de mentira."""
    for n in ("mujer_01_1.jpg", "mujer_01_2.jpg", "mujer_02_1.jpg"):
        _jpg_falso(tmp_path / "mujer" / n)
    personas = fotos.catalogo(tmp_path)["mujer"]
    assert len(personas) == 2
    assert len(personas[0]) == 2 and len(personas[1]) == 1


def test_fotos_sueltas_son_una_persona_cada_una(tmp_path):
    for n in ("a.jpg", "b.png", "c.webp"):
        _jpg_falso(tmp_path / n)
    cat = fotos.catalogo(tmp_path)
    assert len(cat["todos"]) == 3


def test_ignora_archivos_que_no_son_imagenes(tmp_path):
    _jpg_falso(tmp_path / "a.jpg")
    (tmp_path / "notas.txt").write_text("hola")
    assert len(fotos.catalogo(tmp_path)["todos"]) == 1


def test_variable_de_entorno_manda(tmp_path, monkeypatch):
    _jpg_falso(tmp_path / "hombre" / "hombre_01_1.jpg")
    monkeypatch.setenv(fotos.VARIABLE, str(tmp_path))
    assert fotos.carpeta_configurada() == tmp_path

    # "ninguna" vuelve a los retratos ilustrados, sin tocar ningún archivo.
    monkeypatch.setenv(fotos.VARIABLE, "ninguna")
    assert fotos.carpeta_configurada() is None
    f = fotos.Fuente()
    assert f.reales is False
    urls = f.para("p1", "Ana", "mujer", 3)
    assert len(urls) == 3
    assert all(u.startswith("data:image/svg+xml") for u in urls)


def test_carpeta_inexistente_no_rompe(monkeypatch):
    monkeypatch.setenv(fotos.VARIABLE, "/no/existe/esta/carpeta")
    assert fotos.carpeta_configurada() is None
    assert fotos.Fuente().reales is False


def test_no_reparte_la_misma_cara_a_dos_perfiles():
    f = fotos.Fuente()
    vistas = [f.para(f"p{i}", "X", "mujer", 1)[0] for i in range(15)]
    assert len(set(vistas)) == 15


def test_un_perfil_no_mezcla_caras_distintas():
    f = fotos.Fuente()
    urls = f.para("p1", "Ana", "mujer", 5)
    # Sólo hay 2 tomas por persona: se devuelven 2, no se rellena con la cara
    # de otra ni se repite la misma foto.
    assert 1 <= len(urls) <= 2
    assert len(set(urls)) == len(urls)


def test_la_demo_usa_el_pack_y_lo_reporta():
    # Población completa: con 30 perfiles y 8% de peso, la semilla puede no
    # generar ningún perfil no binario y el chequeo de abajo quedaría vacío.
    a = Almacen(":memory:")
    r = demo.poblar(a, cantidad=60)
    assert "personas desde" in r["fuente_de_fotos"]
    perfiles = [p for p in a.todos() if p.sintetico]
    assert all(p.portada.startswith("data:image/jpeg") for p in perfiles)
    # Incluidos los no binarios, que no tienen carpeta propia: si caen al
    # retrato ilustrado se los distingue de un vistazo entre puras fotos.
    nb = [p for p in perfiles if p.genero == "no_binario"]
    assert nb, "la demo tiene que generar algún perfil no binario"
    assert all(p.portada.startswith("data:image/jpeg") for p in nb)
    a.cerrar()


def test_no_se_repite_una_cara_entre_generos():
    f = fotos.Fuente()
    portadas = [
        f.para(f"p{i}", "X", g, 1)[0]
        for i, g in enumerate(["mujer", "no_binario", "hombre"] * 8)
    ]
    assert len(set(portadas)) == len(portadas)


def test_al_agotarse_el_pack_no_clona_caras():
    """Con una población más grande que el pack, se cae a retratos generados
    en vez de repetir la misma cara en dos perfiles."""
    f = fotos.Fuente()
    portadas = [f.para(f"p{i}", "X", "mujer", 1)[0] for i in range(200)]
    assert len(set(portadas)) == len(portadas)
    assert any(u.startswith("data:image/svg+xml") for u in portadas)


def test_la_demo_sigue_andando_sin_ninguna_carpeta(monkeypatch):
    """El motor no puede depender de que existan archivos: si alguien clona sin
    los assets, la demo tiene que levantar igual con retratos generados."""
    monkeypatch.setenv(fotos.VARIABLE, "ninguna")
    a = Almacen(":memory:")
    demo.poblar(a, cantidad=25)
    perfiles = [p for p in a.todos() if p.sintetico]
    assert perfiles
    assert all(p.completo for p in perfiles)
    a.cerrar()
