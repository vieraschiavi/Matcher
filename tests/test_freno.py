"""El login tiene freno.

QUÉ SE PROTEGE ACÁ

Sin freno, `/api/login` acepta contraseñas a la velocidad que las mande quien
sea. En una app de citas eso no es un número en un tablero: adentro de una
cuenta hay conversaciones privadas, fotos y ubicación.

Y hay un segundo efecto que se pasa por alto: verificar una contraseña cuesta
260.000 iteraciones de PBKDF2, y las paga el SERVIDOR. Sin freno, unos pocos
pedidos por segundo con cualquier contraseña dejan la app sin responder para
todos. Por eso hay un test de que el frenado NO llega a hashear.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from matcher import freno, medios, seguridad
from matcher.modelos import DatosInvalidos, Perfil, Preferencias

ALTA = {
    "email": "victima@test.local", "clave": "clave-larga-12345", "nombre": "Vic",
    "nacimiento": "1990-01-01", "genero": "mujer", "altura_cm": 170,
    "pais": "UY", "ciudad": "UY-MVD",
    "preferencias": {"generos": [], "edad_min": 18, "edad_max": 99},
}


def _perfil(id_="x", email="a@b.test") -> Perfil:
    return Perfil(
        id=id_, email=email, nombre="A", nacimiento=date(1990, 1, 1),
        genero="mujer", altura_cm=170, pais="UY", ciudad="UY-MVD",
        preferencias=Preferencias(),
    )


def _errar(cliente, veces, email=ALTA["email"]):
    ultima = None
    for _ in range(veces):
        ultima = cliente.post(
            "/api/login", json={"email": email, "clave": "no-es-la-clave"}
        )
    return ultima


# ---------------------------------------------------------------------------
# El freno frena
# ---------------------------------------------------------------------------
def test_adivinar_la_contrasenia_se_corta(cliente):
    """ES EL PUNTO. Pasado el tope, deja de contestar 401 y contesta 429."""
    cliente.post("/api/registro", json=ALTA)

    for i in range(freno.TOPE_EMAIL):
        r = _errar(cliente, 1)
        assert r.status_code == 401, f"frenó antes de tiempo, en el intento {i + 1}"

    r = _errar(cliente, 1)
    assert r.status_code == 429, "sigue aceptando intentos después del tope"
    assert int(r.headers["Retry-After"]) > 0, "no dice cuánto hay que esperar"


def test_el_frenado_no_entra_ni_con_la_clave_buena(cliente):
    """Si el freno se salteara al acertar, adivinar seguiría siendo posible:
    bastaría con seguir probando y el freno sería decorativo."""
    cliente.post("/api/registro", json=ALTA)
    _errar(cliente, freno.TOPE_EMAIL)

    r = cliente.post("/api/login", json={"email": ALTA["email"], "clave": ALTA["clave"]})
    assert r.status_code == 429


def test_el_frenado_no_le_cuesta_cpu_al_servidor(cliente, monkeypatch):
    """El pedido frenado NO tiene que llegar a PBKDF2.

    Es la mitad del motivo por el que el freno existe: si el frenado igual
    hashea, se evita el acierto pero no que la CPU quede al palo.
    """
    cliente.post("/api/registro", json=ALTA)
    _errar(cliente, freno.TOPE_EMAIL)

    def no_deberia(*_a, **_k):
        raise AssertionError("el pedido frenado llegó a verificar la contraseña")

    monkeypatch.setattr(seguridad, "verificar", no_deberia)
    assert cliente.post(
        "/api/login", json={"email": ALTA["email"], "clave": "x"}
    ).status_code == 429


# ---------------------------------------------------------------------------
# El freno no se convierte en el problema
# ---------------------------------------------------------------------------
def test_entrar_bien_borra_los_fallos(cliente):
    """Si no, quien te sabe el mail te deja la cuenta trabada gritando
    contraseñas al aire, y el frenado terminás siendo vos."""
    cliente.post("/api/registro", json=ALTA)
    _errar(cliente, freno.TOPE_EMAIL - 1)

    assert cliente.post(
        "/api/login", json={"email": ALTA["email"], "clave": ALTA["clave"]}
    ).status_code == 200

    # Después del acierto vuelve a haber margen completo.
    for _ in range(freno.TOPE_EMAIL - 1):
        assert _errar(cliente, 1).status_code == 401


def test_frenar_una_cuenta_no_frena_a_las_demas(cliente):
    cliente.post("/api/registro", json=ALTA)
    otra = {**ALTA, "email": "otra@test.local"}
    cliente.post("/api/registro", json=otra)

    _errar(cliente, freno.TOPE_EMAIL + 1)
    assert _errar(cliente, 1).status_code == 429

    assert cliente.post(
        "/api/login", json={"email": otra["email"], "clave": otra["clave"]}
    ).status_code == 200, "el freno de una cuenta dejó afuera a otra"


def test_el_bloqueo_se_levanta_solo(almacen):
    """Con el tiempo, los intentos viejos salen de la ventana y el freno cede
    sin que nadie lo destrabe a mano."""
    llaves = freno.llaves("ana@test.local", "")
    ahora = datetime(2026, 1, 1, 12, 0, 0)
    for _ in range(freno.TOPE_EMAIL):
        freno.anotar_fallo(almacen, llaves, ahora=ahora)

    assert freno.espera(almacen, llaves, ahora=ahora) > 0
    despues = ahora + freno.VENTANA + timedelta(seconds=1)
    assert freno.espera(almacen, llaves, ahora=despues) == 0


def test_la_mayuscula_del_mail_no_duplica_el_cupo():
    """`Ana@X` y `ana@x` son la misma cuenta para el login. Si fueran cubetas
    distintas, el tope se duplica escribiendo el mail con otra caja."""
    assert freno.llaves("Ana@Test.Local", "") == freno.llaves("  ana@test.local ", "")


# ---------------------------------------------------------------------------
# El 429 no puede ser un delator
# ---------------------------------------------------------------------------
def test_el_freno_no_dice_si_la_cuenta_existe(cliente):
    """Si sólo se frenaran los emails registrados, un 429 contestaría "¿esta
    persona tiene cuenta acá?" — justo lo que el 401 de mensaje único se cuida
    de no decir. Una cuenta que NO existe tiene que frenarse igual."""
    r = _errar(cliente, freno.TOPE_EMAIL + 1, email="fantasma@test.local")
    assert r.status_code == 429


def test_errar_el_mail_cuesta_lo_mismo_que_errar_la_clave(almacen, monkeypatch):
    """El mensaje de error es el mismo para los dos casos, a propósito. Si el
    email inexistente volviera sin hashear, el RELOJ los distinguiría igual:
    ~200 ms contra ~0. Se cuenta cuántas veces se hashea, que es lo que se
    mide desde afuera como tiempo."""
    almacen.crear_perfil(_perfil("a1", "existe@test.local"), "clave-larga-12345")

    cuenta = {"n": 0}
    real = seguridad.verificar

    def contando(*a, **k):
        cuenta["n"] += 1
        return real(*a, **k)

    monkeypatch.setattr(seguridad, "verificar", contando)

    cuenta["n"] = 0
    almacen.login("existe@test.local", "mal")
    con_cuenta = cuenta["n"]

    cuenta["n"] = 0
    almacen.login("no-existe@test.local", "mal")
    sin_cuenta = cuenta["n"]

    assert con_cuenta == 1
    assert sin_cuenta == 1, (
        "el email inexistente no hashea: el tiempo de respuesta delata qué "
        "cuentas existen"
    )


# ---------------------------------------------------------------------------
# Lo que se acepta como foto
# ---------------------------------------------------------------------------
def test_un_data_uri_de_html_no_pasa_por_foto():
    """Antes pasaba cualquier cosa que empezara con `data:`. El comentario del
    código decía que el tipo iba en el prefijo, pero nadie lo miraba.

    Como `<img>` no ejecuta nada y la CSP no permite scripts, hoy no se
    renderiza — pero una URL de perfil termina en muchos lados con el tiempo
    (un enlace, un `open()`, un cliente futuro), y ahí sí importa.
    """
    p = _perfil()
    for veneno in (
        "data:text/html,<script>alert(1)</script>",
        "data:text/html;base64,PHNjcmlwdD4=",
        "data:application/javascript,alert(1)",
    ):
        with pytest.raises(DatosInvalidos):
            medios.agregar_foto(p, veneno)

    # Y lo legítimo sigue entrando: la demo entera son data-URI de JPEG.
    medios.agregar_foto(p, "data:image/jpeg;base64,/9j/4AAQSkZJRg")
    assert len(p.fotos) == 1


def test_un_video_no_entra_como_foto():
    """Los tipos no se mezclan: `data:video/mp4` no es una foto."""
    with pytest.raises(DatosInvalidos):
        medios.agregar_foto(_perfil(), "data:video/mp4;base64,AAAA")
