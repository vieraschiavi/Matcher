"""La demo: dos cuentas full, población sintética marcada y determinismo."""

from matcher import avatares, demo, scoring
from matcher.almacen import Almacen


def test_crea_las_dos_cuentas_pedidas_con_todo_activado(almacen):
    demo.poblar(almacen, cantidad=30)
    for email in ("vieraschiavi@gmail.com", "arcortito@gmail.com"):
        p = almacen.buscar_por_email(email)
        assert p is not None, f"falta la cuenta demo {email}"
        assert p.plan == "gold"
        assert p.es_premium is True
        assert p.verificado is True
        assert p.completo                  # con portada: entra al deck de los demás
        assert 0 < len(p.fotos) <= 10      # con lugar libre para subir las propias
        assert p.sintetico is False        # son cuentas de prueba, no perfiles inventados
        assert almacen.login(email, demo.CLAVE_DEMO) is not None


def test_las_cuentas_demo_tienen_cupos_de_gold(almacen):
    demo.poblar(almacen, cantidad=30)
    p = almacen.buscar_por_email("vieraschiavi@gmail.com")
    cupos = almacen.cupos(p)
    assert cupos["likes_max"] is None            # ilimitados
    assert cupos["ver_quien_me_dio_like"] is True
    assert cupos["rebobinar"] is True
    assert cupos["modo_incognito"] is True


def test_los_perfiles_generados_se_declaran_sinteticos(almacen):
    demo.poblar(almacen, cantidad=40)
    generados = [p for p in almacen.todos() if p.email.endswith("@matcher.demo")]
    assert len(generados) > 20
    assert all(p.sintetico for p in generados)
    # Y la marca viaja en la vista pública, que es la que ve el usuario.
    assert all(p.a_dict()["sintetico"] for p in generados)


def test_las_fotos_generadas_llevan_el_sello_de_sintetico():
    svg = avatares.svg("demo001", "S", 0, "mujer")
    assert "PERFIL SINTÉTICO" in svg


def test_ningun_perfil_generado_tiene_datos_de_contacto_reales(almacen):
    demo.poblar(almacen, cantidad=40)
    for p in almacen.todos():
        if p.sintetico:
            assert p.email.endswith("@matcher.demo")


def test_es_determinista():
    a, b = Almacen(":memory:"), Almacen(":memory:")
    demo.poblar(a, cantidad=35)
    demo.poblar(b, cantidad=35)
    fa = [(p.id, p.nombre, p.pais, p.equipo, p.altura_cm) for p in sorted(a.todos(), key=lambda x: x.id)]
    fb = [(p.id, p.nombre, p.pais, p.equipo, p.altura_cm) for p in sorted(b.todos(), key=lambda x: x.id)]
    assert fa == fb
    a.cerrar()
    b.cerrar()


def test_poblar_dos_veces_no_duplica_ni_pisa_el_plan(almacen):
    r1 = demo.poblar(almacen, cantidad=30)
    total = r1["total_perfiles"]
    r2 = demo.poblar(almacen, cantidad=30)
    assert r2["creados"] == []
    assert sorted(r2["ya_existian"]) == sorted(demo.CUENTAS_DEMO)
    assert r2["total_perfiles"] == total


def test_hay_paises_y_equipos_variados(almacen):
    """Si la demo genera un solo país, el filtro de equipo no se puede probar
    y la regla de olas geográficas tampoco."""
    demo.poblar(almacen, cantidad=60)
    perfiles = [p for p in almacen.todos() if p.sintetico]
    assert len({p.pais for p in perfiles}) >= 4
    assert len({p.equipo for p in perfiles if p.equipo}) >= 8


def test_el_ranking_de_la_demo_no_empata_todo_arriba(almacen):
    """El "más votados" tiene que discriminar: si media población da 100, el
    ranking no dice nada."""
    demo.poblar(almacen, cantidad=60)
    top = scoring.top_votados(almacen.todos(), 20)
    valores = [t["popularidad"] for t in top]
    assert len(set(valores)) > 10
    assert max(valores) < 100


def test_las_cuentas_demo_tienen_likes_para_mostrar(almacen):
    demo.poblar(almacen, cantidad=50)
    p = almacen.buscar_por_email("vieraschiavi@gmail.com")
    assert almacen.quien_me_dio_like(p)["cantidad"] > 0


def test_el_deck_de_la_cuenta_demo_trae_perfiles(almacen):
    demo.poblar(almacen, cantidad=60)
    p = almacen.buscar_por_email("vieraschiavi@gmail.com")
    d = almacen.deck(p, limite=10)
    assert len(d["tarjetas"]) > 0
    for t in d["tarjetas"]:
        assert t["fotos"], "toda tarjeta del deck tiene que tener foto"
        assert 0 <= t["compatibilidad"] <= 100
