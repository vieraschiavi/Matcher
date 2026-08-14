"""Fábricas de perfiles para los tests.

Todos los tests arrancan de un almacén en memoria: son rápidos y no dejan un
`.db` colgado que haga pasar el test siguiente por datos viejos.
"""

from datetime import date, timedelta

import pytest

from matcher.almacen import Almacen
from matcher.modelos import Media, Perfil, Preferencias


@pytest.fixture
def almacen():
    a = Almacen(":memory:")
    yield a
    a.cerrar()


def nacido_hace(años: int) -> date:
    # −40 días para que el test no se caiga el día del cumpleaños.
    return date.today() - timedelta(days=años * 365 + 40)


@pytest.fixture
def hacer_perfil():
    contador = {"n": 0}

    def fabrica(**kw) -> Perfil:
        contador["n"] += 1
        n = contador["n"]
        base = {
            "id": kw.pop("id", f"p{n:03d}"),
            "email": kw.pop("email", f"p{n:03d}@test.local"),
            "nombre": kw.pop("nombre", f"Persona {n}"),
            "nacimiento": nacido_hace(kw.pop("edad", 30)),
            "genero": kw.pop("genero", "mujer"),
            "altura_cm": kw.pop("altura_cm", 170),
            "pais": kw.pop("pais", "UY"),
            "ciudad": kw.pop("ciudad", "UY-MVD"),
            "politica": kw.pop("politica", "neutro"),
            "equipo": kw.pop("equipo", ""),
        }
        preferencias = kw.pop("preferencias", None)
        p = Perfil(**base, **kw)
        if preferencias:
            p.preferencias = (
                preferencias
                if isinstance(preferencias, Preferencias)
                else Preferencias.desde_dict(preferencias)
            )
        # Toda fábrica devuelve un perfil que YA puede entrar al deck: sin
        # portada `completo` es False y media suite fallaría por eso y no por
        # lo que cada test quiere probar.
        if not p.fotos:
            p.fotos = [Media(id=f"m{n}", tipo="foto", url="https://x.test/f.jpg", orden=0)]
        return p

    return fabrica
