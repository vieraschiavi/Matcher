"""La demo dejó de ser pública.

DECISIÓN COMERCIAL QUE ESTOS TESTS SOSTIENEN

Una demo abierta le regala el producto a la competencia: quien entra se lleva
las pantallas y los flujos sin dejar rastro y sin que nadie le venda nada. El
video de la landing muestra el RESULTADO; para ver la app andando hay que
pedirla, y así queda registrado quién pidió y con qué mail.

Lo que se protege acá:

- que las cuentas de demo NO aparezcan solas en la pantalla de entrada;
- que los pedidos no se pierdan aunque el mail no salga;
- que los datos de quien pide —que es un tercero, todavía no un cliente— no
  se filtren por ninguna ruta pública.
"""

from __future__ import annotations

import pytest

from matcher import solicitudes
from matcher.modelos import DatosInvalidos

BUENO = {
    "nombre": "Ana Pérez",
    "email": "ana@empresa.test",
    "empresa": "Empresa SA",
    "pais": "Uruguay",
    "mensaje": "Quiero verla para mi equipo",
}


def duenio(cliente, monkeypatch, email="jefa@test.local") -> dict:
    monkeypatch.setenv("MATCHER_CUENTAS_DUENIO", email)
    r = cliente.post(
        "/api/registro",
        json={
            "email": email, "clave": "clave-larga-12345", "nombre": "Jefa",
            "nacimiento": "1990-01-01", "genero": "mujer", "altura_cm": 170,
            "pais": "UY", "ciudad": "UY-MVD",
            "preferencias": {"generos": [], "edad_min": 18, "edad_max": 99},
        },
    )
    assert r.status_code == 200, r.text
    cliente.post("/api/login", json={"email": email, "clave": "clave-larga-12345"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


# ---------------------------------------------------------------------------
# La demo no se abre sola
# ---------------------------------------------------------------------------
def test_la_demo_no_es_publica_por_defecto(cliente):
    """Sin `MATCHER_DEMO_PUBLICA=1`, la pantalla de entrada no muestra las
    cuentas de demo. Es el default porque el default es lo que queda puesto."""
    assert cliente.get("/api/salud").json()["demo_publica"] is False


def test_la_clave_de_demo_no_viaja_en_el_bundle():
    """El bundle es público y el repositorio también. Si la contraseña está
    escrita en el código, la demo es pública aunque el botón esté escondido."""
    from pathlib import Path

    fuente = (
        Path(__file__).resolve().parents[1]
        / "webapp" / "frontend" / "src" / "paginas" / "Entrar.jsx"
    ).read_text(encoding="utf-8")
    assert "matcher2026" not in fuente, "la clave de demo quedó cableada en el frontend"
    assert "VITE_CLAVE_DEMO" in fuente


def test_el_bloque_de_demo_depende_del_servidor():
    """Una bandera del cliente se enciende editando el JavaScript. La decisión
    tiene que venir del servidor."""
    from pathlib import Path

    fuente = (
        Path(__file__).resolve().parents[1]
        / "webapp" / "frontend" / "src" / "paginas" / "Entrar.jsx"
    ).read_text(encoding="utf-8")
    assert "demoPublica" in fuente
    assert "demo_publica" in fuente, "no lee la bandera de /api/salud"


# ---------------------------------------------------------------------------
# Validación del formulario
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "cambio,motivo",
    [
        ({"nombre": "Ana"}, "nombre y apellido"),
        ({"nombre": ""}, "nombre y apellido"),
        ({"email": "no-es-un-mail"}, "email"),
        ({"email": ""}, "email"),
        ({"empresa": ""}, "empresa"),
        ({"pais": ""}, "país"),
    ],
)
def test_los_campos_obligatorios_se_exigen(cambio, motivo):
    datos = {**BUENO, **cambio}
    with pytest.raises(DatosInvalidos) as e:
        solicitudes.validar(datos)
    assert motivo in str(e.value)


def test_los_datos_se_limpian(almacen):
    solicitudes.crear(almacen, {**BUENO, "nombre": "  Ana   Pérez  ", "email": "ANA@Empresa.TEST"})
    fila = solicitudes.listar(almacen)[0]
    assert fila["nombre"] == "Ana Pérez", "no colapsó los espacios"
    assert fila["email"] == "ana@empresa.test", "no normalizó el mail a minúsculas"


def test_un_texto_larguisimo_no_entra_entero(almacen):
    solicitudes.crear(almacen, {**BUENO, "mensaje": "x" * 5000})
    assert len(solicitudes.listar(almacen)[0]["mensaje"]) <= solicitudes.LARGOS["mensaje"]


# ---------------------------------------------------------------------------
# El pedido no se pierde
# ---------------------------------------------------------------------------
def test_el_pedido_se_guarda_aunque_el_mail_no_salga(almacen, monkeypatch):
    """ES EL PUNTO. Si el aviso fallara y el pedido se perdiera, el prospecto
    cree que pidió y del otro lado no llegó nada."""
    def explota(_datos):
        raise RuntimeError("SMTP caído")

    monkeypatch.setattr(solicitudes, "_avisar", explota)
    with pytest.raises(RuntimeError):
        solicitudes.crear(almacen, BUENO)
    # Aun con la excepción, la fila ya está: se guarda ANTES de avisar.
    assert len(solicitudes.listar(almacen)) == 1


def test_sin_smtp_configurado_no_revienta(almacen, monkeypatch):
    for v in ("MATCHER_SMTP_HOST", "MATCHER_SMTP_USUARIO", "MATCHER_SMTP_CLAVE"):
        monkeypatch.delenv(v, raising=False)
    r = solicitudes.crear(almacen, BUENO)
    assert r["avisado"] is False
    assert len(solicitudes.listar(almacen)) == 1


def test_el_destino_del_aviso_es_el_del_dueño(monkeypatch):
    monkeypatch.delenv("MATCHER_EMAIL_DEMOS", raising=False)
    assert solicitudes.destino() == "vieraschiavi@gmail.com"
    monkeypatch.setenv("MATCHER_EMAIL_DEMOS", "otro@empresa.test")
    assert solicitudes.destino() == "otro@empresa.test"


def test_no_se_puede_inundar_la_bandeja(almacen):
    for _ in range(solicitudes.TOPE_POR_EMAIL):
        solicitudes.crear(almacen, BUENO)
    with pytest.raises(DatosInvalidos, match="ya tenemos tu pedido"):
        solicitudes.crear(almacen, BUENO)
    # Otra dirección sigue pudiendo pedir: el tope es por mail, no global.
    solicitudes.crear(almacen, {**BUENO, "email": "otra@empresa.test"})


# ---------------------------------------------------------------------------
# Por HTTP
# ---------------------------------------------------------------------------
def test_cualquiera_puede_pedir_la_demo(cliente):
    """Esta ruta SÍ es pública: si no, nadie podría pedirla."""
    r = cliente.post("/api/demo/solicitar", json=BUENO)
    assert r.status_code == 200, r.text
    assert r.json()["recibido"] is True


def test_la_respuesta_no_dice_si_el_mail_salio(cliente):
    """Es información interna. Y "no se pudo avisar" asusta al prospecto sin
    motivo: el pedido está guardado igual."""
    cuerpo = cliente.post("/api/demo/solicitar", json={**BUENO, "email": "x@y.test"}).json()
    assert "avisado" not in cuerpo
    assert "smtp" not in str(cuerpo).lower()


def test_el_robot_que_llena_todo_no_molesta(cliente, monkeypatch):
    """La trampa: un campo que la persona no ve. Se responde 200 igual —
    decirle "te detecté" al que raspa es enseñarle a esquivar la próxima."""
    cab = duenio(cliente, monkeypatch)
    antes = len(cliente.get("/api/panel/solicitudes", headers=cab).json()["solicitudes"])
    r = cliente.post("/api/demo/solicitar", json={**BUENO, "web": "http://spam.test"})
    assert r.status_code == 200
    despues = len(cliente.get("/api/panel/solicitudes", headers=cab).json()["solicitudes"])
    assert despues == antes, "el pedido del robot entró igual"


def test_los_datos_del_prospecto_no_son_publicos(cliente, monkeypatch):
    """Nombre, mail y empresa de alguien que todavía no es cliente. Ninguna
    ruta pública los devuelve."""
    cliente.post("/api/demo/solicitar", json=BUENO)

    assert cliente.get("/api/panel/solicitudes").status_code == 401

    monkeypatch.delenv("MATCHER_CUENTAS_DUENIO", raising=False)
    r = cliente.post(
        "/api/registro",
        json={
            "email": "curiosa@test.local", "clave": "clave-larga-12345", "nombre": "Curiosa",
            "nacimiento": "1990-01-01", "genero": "mujer", "altura_cm": 170,
            "pais": "UY", "ciudad": "UY-MVD",
            "preferencias": {"generos": [], "edad_min": 18, "edad_max": 99},
        },
    )
    cab = {"Authorization": f"Bearer {r.json()['token']}"}
    assert cliente.get("/api/panel/solicitudes", headers=cab).status_code == 404


def test_el_duenio_ve_quien_pidio(cliente, monkeypatch):
    cliente.post("/api/demo/solicitar", json=BUENO)
    cab = duenio(cliente, monkeypatch)
    r = cliente.get("/api/panel/solicitudes", headers=cab)
    assert r.status_code == 200
    pedido = r.json()["solicitudes"][0]
    assert pedido["nombre"] == "Ana Pérez"
    assert pedido["email"] == "ana@empresa.test"
    assert pedido["empresa"] == "Empresa SA"
    assert pedido["estado"] == "nueva"
    assert r.json()["destino"] == solicitudes.destino()


def test_el_pedido_se_puede_marcar_como_atendido(cliente, monkeypatch):
    cliente.post("/api/demo/solicitar", json=BUENO)
    cab = duenio(cliente, monkeypatch)
    id_ = cliente.get("/api/panel/solicitudes", headers=cab).json()["solicitudes"][0]["id"]

    assert cliente.post(
        f"/api/panel/solicitudes/{id_}", json={"estado": "agendada"}, headers=cab
    ).status_code == 200
    estados = [s["estado"] for s in
               cliente.get("/api/panel/solicitudes", headers=cab).json()["solicitudes"]]
    assert "agendada" in estados

    r = cliente.post(
        f"/api/panel/solicitudes/{id_}", json={"estado": "inventado"}, headers=cab
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# La landing
# ---------------------------------------------------------------------------
def test_la_landing_no_ofrece_descargas():
    """El artefacto no se regala. Si vuelve un botón de descarga, este test
    tiene que ponerse en rojo."""
    from marketing import generar_landing as gl

    for idioma in gl.IDIOMAS:
        html = gl.pagina(idioma)
        for prohibido in ("/api/descargar/", "Matcher.exe", ".apk"):
            assert prohibido not in html, f"{idioma}: la landing ofrece {prohibido}"


def test_la_landing_pide_los_datos_que_filtran(cliente=None):
    from marketing import generar_landing as gl

    for idioma in gl.IDIOMAS:
        html = gl.pagina(idioma)
        for campo in ("nombre", "email", "empresa", "pais"):
            assert f'name="{campo}"' in html, f"{idioma}: falta el campo {campo}"
        assert 'name="web"' in html, f"{idioma}: falta la trampa para robots"
        assert "/api/demo/solicitar" in html


def test_el_video_sigue_publico():
    """El video es el resultado visual y SÍ se muestra: es lo que atrae. Lo que
    no se regala es el artefacto."""
    from marketing import generar_landing as gl

    for idioma in gl.IDIOMAS:
        assert 'type="video/mp4"' in gl.pagina(idioma)
