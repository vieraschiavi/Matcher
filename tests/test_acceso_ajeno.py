"""Que nadie lea ni toque lo de otra persona.

POR QUÉ ESTE ARCHIVO EXISTE

Es el agujero clásico de una app así, y el más caro: acceder a un recurso ajeno
cambiando un id en la URL. En una app de citas eso no es "un bug de permisos",
es leer conversaciones privadas de desconocidos.

La app pasa el perfil de la sesión a cada función del motor, y las guardas
están adentro (`almacen._match_de`, `videollamada._fila` + chequeo). Leerlas y
darlas por buenas no alcanza: este archivo las EJERCITA desde HTTP, que es por
donde entraría el ataque.

Se prueba contra el id REAL de un recurso ajeno —no contra uno inventado—
porque un id inexistente puede fallar por el motivo equivocado y dar un test
verde que no probó nada.

Y se verifica que el mensaje sea el MISMO para "no existe" y "no es tuyo": si
se distinguen, el error se vuelve un buscador de matches ajenos.
"""

from __future__ import annotations

import pytest

ALTA = {
    "clave": "clave-larga-12345", "nacimiento": "1990-01-01", "genero": "mujer",
    "altura_cm": 170, "pais": "UY", "ciudad": "UY-MVD",
    "preferencias": {"generos": [], "edad_min": 18, "edad_max": 99},
}


def cuenta(cliente, email, nombre="Alguien") -> dict:
    r = cliente.post("/api/registro", json={**ALTA, "email": email, "nombre": nombre})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def match_ajeno(cliente):
    """Un match REAL entre dos personas, y una tercera que no tiene nada que
    ver. Devuelve (match_id, cabeceras de la intrusa)."""
    a = cuenta(cliente, "ana@test.local", "Ana")
    b = cuenta(cliente, "beto@test.local", "Beto")
    intrusa = cuenta(cliente, "intrusa@test.local", "Intrusa")

    id_a = cliente.get("/api/yo", headers=a).json()["perfil"]["id"]
    id_b = cliente.get("/api/yo", headers=b).json()["perfil"]["id"]

    cliente.post("/api/interacciones", json={"a_id": id_b, "tipo": "like"}, headers=a)
    r = cliente.post("/api/interacciones", json={"a_id": id_a, "tipo": "like"}, headers=b)
    assert r.json().get("match"), f"no se armó el match: {r.text}"

    matches = cliente.get("/api/matches", headers=a).json()["matches"]
    assert matches, "la cuenta no ve su propio match"
    return matches[0]["id"], intrusa, a, b


# ---------------------------------------------------------------------------
# El chat
# ---------------------------------------------------------------------------
def test_no_se_lee_el_chat_de_otros(cliente, match_ajeno):
    """ES EL PUNTO DEL ARCHIVO. Conversaciones privadas de desconocidos."""
    match_id, intrusa, a, _b = match_ajeno
    cliente.post(f"/api/matches/{match_id}/mensajes",
                 json={"texto": "algo privado"}, headers=a)

    r = cliente.get(f"/api/matches/{match_id}/mensajes", headers=intrusa)
    assert r.status_code != 200, "una tercera persona leyó el chat"
    assert "algo privado" not in r.text


def test_no_se_escribe_en_el_chat_de_otros(cliente, match_ajeno):
    """Escribir en un chat ajeno es hacerse pasar por alguien."""
    match_id, intrusa, a, _b = match_ajeno
    r = cliente.post(f"/api/matches/{match_id}/mensajes",
                     json={"texto": "hola soy otra persona"}, headers=intrusa)
    assert r.status_code != 200

    mensajes = cliente.get(f"/api/matches/{match_id}/mensajes", headers=a).json()["mensajes"]
    assert all("otra persona" not in m["texto"] for m in mensajes)


def test_no_se_deshace_el_match_de_otros(cliente, match_ajeno):
    """Borrar el match ajeno borra también sus mensajes: es destrucción de
    datos de terceros, no sólo una lectura indebida."""
    match_id, intrusa, a, _b = match_ajeno
    assert cliente.delete(f"/api/matches/{match_id}", headers=intrusa).status_code != 200
    assert cliente.get("/api/matches", headers=a).json()["matches"], (
        "el match de otra persona desapareció"
    )


# ---------------------------------------------------------------------------
# La videollamada
# ---------------------------------------------------------------------------
def test_no_se_mira_la_videollamada_de_otros(cliente, match_ajeno):
    match_id, intrusa, _a, _b = match_ajeno
    r = cliente.get(f"/api/matches/{match_id}/videollamada", headers=intrusa)
    assert r.status_code != 200, "una tercera persona vio el estado de la llamada"


def test_un_tercero_no_acepta_una_videollamada_ajena(cliente, match_ajeno):
    """Aceptar por otro es entregar SU cara y SU voz. El consentimiento es de
    los dos que están en el match, de nadie más (regla 12)."""
    match_id, intrusa, a, b = match_ajeno
    prop = cliente.post(
        f"/api/matches/{match_id}/videollamada",
        json={"proveedor": "jitsi"}, headers=a,
    )
    assert prop.status_code == 200, prop.text
    llamada_id = prop.json()["llamada"]["id"]

    r = cliente.post(f"/api/videollamadas/{llamada_id}/responder",
                     json={"acepta": True}, headers=intrusa)
    assert r.status_code != 200, "un tercero aceptó la videollamada de otros"

    # Y el enlace sigue sin existir para nadie mientras no acepte quien debe.
    estado = cliente.get(f"/api/matches/{match_id}/videollamada", headers=b).json()
    assert estado["llamada"]["enlace"] is None


def test_un_tercero_no_cancela_una_videollamada_ajena(cliente, match_ajeno):
    match_id, intrusa, a, _b = match_ajeno
    llamada_id = cliente.post(
        f"/api/matches/{match_id}/videollamada",
        json={"proveedor": "jitsi"}, headers=a,
    ).json()["llamada"]["id"]

    assert cliente.delete(
        f"/api/videollamadas/{llamada_id}", headers=intrusa
    ).status_code != 200


# ---------------------------------------------------------------------------
# El error no puede ser un buscador
# ---------------------------------------------------------------------------
def test_no_se_distingue_inexistente_de_ajeno(cliente, match_ajeno):
    """Si "no existe" y "no es tuyo" dan mensajes distintos, probar ids al azar
    dice cuáles son matches reales de otra gente."""
    match_id, intrusa, _a, _b = match_ajeno
    ajeno = cliente.get(f"/api/matches/{match_id}/mensajes", headers=intrusa)
    fantasma = cliente.get("/api/matches/noexistenada/mensajes", headers=intrusa)

    assert ajeno.status_code == fantasma.status_code
    assert ajeno.json().get("detail") == fantasma.json().get("detail")


# ---------------------------------------------------------------------------
# Sin sesión no se toca nada
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("metodo,ruta", [
    ("get", "/api/matches/{}/mensajes"),
    ("post", "/api/matches/{}/mensajes"),
    ("get", "/api/matches/{}/videollamada"),
    ("delete", "/api/matches/{}"),
])
def test_sin_sesion_no_se_entra(cliente, match_ajeno, metodo, ruta):
    match_id, _i, _a, _b = match_ajeno
    # `json=` sólo en POST: el TestClient rechaza cuerpo en GET/DELETE, y ese
    # TypeError hacía fallar el test por el motivo equivocado — verde o rojo
    # por algo que no tiene que ver con la autenticación.
    extra = {"json": {"texto": "x"}} if metodo == "post" else {}
    r = getattr(cliente, metodo)(ruta.format(match_id), **extra)
    assert r.status_code == 401, f"{metodo.upper()} {ruta} contestó {r.status_code}"
