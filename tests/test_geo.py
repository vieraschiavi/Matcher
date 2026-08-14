"""El catálogo geográfico es relativo al país del usuario, nunca cableado."""

import pytest

from matcher import geo


def test_todo_pais_del_catalogo_tiene_equipos_y_region():
    for codigo, pais in geo.CATALOGO.items():
        assert pais.equipos, f"{codigo} sin equipos"
        assert pais.region != "desconocida"
        assert len(codigo) == 2


def test_equipos_son_del_pais_pedido():
    # La razón de ser del filtro: cada país trae SUS equipos.
    assert "Peñarol" in geo.equipos_de("UY")
    assert "Peñarol" not in geo.equipos_de("MX")
    assert "Chivas de Guadalajara" in geo.equipos_de("MX")
    assert "Boca Juniors" in geo.equipos_de("AR")
    assert geo.equipos_de("ZZ") == []


def test_toda_ciudad_pertenece_a_un_pais_del_catalogo():
    for clave in geo.CIUDADES:
        assert clave.split("-")[0] in geo.CATALOGO, f"{clave} sin país"


def test_cada_pais_tiene_al_menos_una_ciudad():
    for codigo in geo.CATALOGO:
        assert geo.ciudades_de(codigo), f"{codigo} sin ciudades"


def test_distancia_conocida():
    mvd = geo.coordenadas("UY-MVD")
    bue = geo.coordenadas("AR-BUE")
    # Montevideo–Buenos Aires son ~200 km en línea recta.
    assert 190 < geo.distancia_km(mvd, bue) < 220
    assert geo.distancia_km(mvd, mvd) == 0.0


def test_olas_son_relativas_al_pais_base():
    # Para un uruguayo, Argentina es "región"; para un español, "mundo".
    assert geo.ola_entre("UY", "UY-MVD", "UY", "UY-MVD") == "ciudad"
    assert geo.ola_entre("UY", "UY-MVD", "UY", "UY-SAL") == "pais"
    assert geo.ola_entre("UY", "UY-MVD", "AR", "AR-BUE") == "region"
    assert geo.ola_entre("ES", "ES-MAD", "AR", "AR-BUE") == "mundo"
    # Y se da vuelta al cambiar el país base: esto es lo que impide volver a
    # cablear un país.
    assert geo.ola_entre("AR", "AR-BUE", "UY", "UY-MVD") == "region"
    assert geo.ola_entre("MX", "MX-MEX", "UY", "UY-MVD") == "mundo"


def test_pesos_de_ola_decrecen():
    assert (
        geo.PESO_OLA["ciudad"]
        > geo.PESO_OLA["pais"]
        > geo.PESO_OLA["region"]
        > geo.PESO_OLA["mundo"]
    )


@pytest.mark.parametrize(
    "crudo,esperado",
    [("Peñarol", "penarol"), ("PEÑAROL", "penarol"), ("  São Paulo ", "sao paulo"), ("", "")],
)
def test_normalizar_ignora_tildes_y_mayusculas(crudo, esperado):
    assert geo.normalizar(crudo) == esperado
