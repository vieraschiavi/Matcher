"""La edición OWNER: el `.exe` que trae el backend adentro.

QUÉ ATRAPA ESTE ARCHIVO Y QUÉ NO

Que el instalador ARRANQUE en Windows no se prueba desde acá, igual que el
`.nsh` (ver `test_escritorio.py`). Lo que sí se atrapa es la clase de error que
sólo se ve cuando alguien ya bajó 90 MB e instaló:

- que el `.exe` empaquetado no se reconozca a sí mismo como edición owner y
  abra contra el servidor de producción — que es exactamente lo que esta
  edición existe para no hacer;
- que el backend local escuche en todas las interfaces y le abra la base al
  resto del wifi;
- que la base quede adentro de la carpeta de instalación, donde el
  desinstalador de electron-builder la borra en cada actualización, en silencio;
- que falte una carpeta en `extraResources` y el servidor muera con
  `ModuleNotFoundError` recién en la máquina del dueño;
- que alguien meta un token de owner adentro del instalador para "desbloquear
  la versión paga" (reglas 15 y 20).

El último no es hipotético: es el patrón que trae el repositorio que se usó de
modelo, y publica una credencial válida en un repo público.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

RAIZ = Path(__file__).resolve().parents[1]
CONFIG = RAIZ / "electron-builder-owner.yml"
SERVIDOR = RAIZ / "electron" / "servidor-local.js"
MAIN = RAIZ / "electron" / "main.js"
PRELOAD = RAIZ / "electron" / "preload.js"
API_JS = RAIZ / "webapp" / "frontend" / "src" / "api.js"
FLUJO = RAIZ / ".github" / "workflows" / "owner.yml"
LEEME = RAIZ / "descargas-owner" / "LEEME.md"


@pytest.fixture(scope="module")
def config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def paquete() -> dict:
    return json.loads((RAIZ / "package.json").read_text(encoding="utf-8"))


def sin_comentarios(js: str) -> str:
    """El JS sin comentarios.

    Hace falta de verdad, no es prolijidad: estos archivos explican en el
    encabezado lo que NO hacen —"nunca en 0.0.0.0", "la primera versión leía
    `MATCHER_EDICION`"— y un test que busca esas cadenas en el texto crudo
    falla por culpa del comentario que documenta el arreglo. La alternativa
    (borrar la explicación para que pase el test) es peor que el test.
    """
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return "\n".join(re.sub(r"//.*$", "", linea) for linea in js.splitlines())


@pytest.fixture(scope="module")
def servidor() -> str:
    return sin_comentarios(SERVIDOR.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Que la edición owner se reconozca a sí misma
# ---------------------------------------------------------------------------
def test_la_edicion_se_reconoce_por_el_contenido_no_por_una_variable(servidor):
    """La primera versión leía `process.env.MATCHER_EDICION`, y en el `.exe`
    empaquetado esa variable no la pone nadie: electron-builder no inyecta
    entorno en tiempo de ejecución. La edición owner nunca se hubiera
    reconocido y habría abierto contra el servidor remoto.

    Ahora decide `ubicaciones().empaquetado`, o sea que exista la carpeta
    `servidor/` — que sólo la deja `electron-builder-owner.yml`.
    """
    assert "function esOwner()" in servidor
    assert "ubicaciones().empaquetado" in servidor, (
        "esOwner no mira el contenido del paquete: en el .exe instalado no se "
        "va a reconocer y va a hablarle al servidor de producción"
    )
    assert "MATCHER_EDICION" not in servidor, (
        "volvió la bandera por variable de entorno, que el .exe no tiene"
    )
    assert "servidorLocal.esOwner()" in sin_comentarios(MAIN.read_text(encoding="utf-8"))


def test_el_paquete_owner_deja_la_carpeta_que_lo_delata(config):
    """El corolario del test de arriba: si `extraResources` dejara de mapear a
    `servidor/…`, `esOwner()` devolvería false y la edición owner se
    comportaría como la normal — con el backend empaquetado adentro, sin usar."""
    destinos = [r["to"] for r in config["extraResources"]]
    assert all(d.startswith("servidor/") for d in destinos), destinos


# ---------------------------------------------------------------------------
# Seguridad del backend local
# ---------------------------------------------------------------------------
def test_el_backend_local_escucha_solo_en_la_maquina(servidor):
    """Un backend de escritorio escuchando en 0.0.0.0 le expone la base —
    perfiles, chats, ubicación— al resto de la red wifi: el bar, la oficina, el
    aeropuerto. Y nadie se entera, porque desde la propia máquina se ve igual."""
    assert '"--host", "127.0.0.1"' in servidor
    assert "0.0.0.0" not in servidor
    # El sondeo de puerto libre también: `listen(0)` sin dirección escucha en
    # todas las interfaces por un instante.
    assert 's.listen(0, "127.0.0.1"' in servidor


def test_el_puerto_no_esta_cableado(servidor):
    """Un puerto fijo choca con cualquier otra cosa que lo esté usando y el
    arranque falla con un error que no dice nada."""
    assert "puertoLibre" in servidor
    assert not re.search(r'"--port",\s*"\d+"', servidor), "cableó el puerto"
    assert '"--port", String(puerto)' in servidor


def test_la_base_va_a_la_carpeta_de_datos_y_no_a_la_instalacion(servidor):
    """El desinstalador de electron-builder hace `RMDir /r` sobre `$INSTDIR` en
    CADA actualización. Con la base ahí adentro se pierden la cuenta y los
    matches en cada update, en silencio y sin error."""
    assert "MATCHER_BD: path.join(datos, " in servidor
    assert 'app.getPath("userData")' in MAIN.read_text(encoding="utf-8")


def test_al_desinstalar_no_se_borra_la_base(config):
    """Al revés que en la edición normal, y a propósito: allá lo único local es
    el token de sesión (dejarlo en una PC compartida es dejar la cuenta
    abierta); acá adentro está la base entera."""
    assert config["nsis"]["deleteAppDataOnUninstall"] is False


def test_si_el_servidor_local_no_arranca_la_app_abre_igual(servidor):
    """Peor que no tener servidor local es tener uno que no responde y una app
    que le habla igual: la app se queda muda con un error de red que no se
    entiende."""
    assert "return null;" in servidor, "no hay salida sin excepción"
    assert "esperarSalud" in servidor, (
        "no espera a que el backend conteste: la primera pantalla muestra un "
        "error de red que se arregla solo al recargar"
    )
    # `levantar` envuelve todo en try/catch: una excepción acá dejaría al dueño
    # sin poder abrir su propio programa.
    cuerpo = servidor.split("async function levantar(", 1)[1]
    assert "try {" in cuerpo and "} catch {" in cuerpo


def test_el_servidor_local_se_baja_al_cerrar():
    """Sin esto queda un proceso de Python huérfano con el archivo de la base
    tomado, y el próximo arranque no puede escribir — se ve como "la app dejó
    de guardar", que no se parece en nada a la causa."""
    main = MAIN.read_text(encoding="utf-8")
    assert 'app.on("will-quit"' in main
    assert "servidor.detener()" in main


# ---------------------------------------------------------------------------
# Que el frontend le hable al backend local y no al de producción
# ---------------------------------------------------------------------------
def test_la_url_local_gana_sobre_la_compilada():
    """El build de owner se compila como cualquier otro y puede llevar
    `VITE_API_URL` puesta. Si `apiLocal` no fuera primero en la cadena, la app
    andaría —contra la base de PRODUCCIÓN— con el backend local levantado y sin
    usar: el peor de los dos mundos, y sin ningún síntoma visible."""
    api = API_JS.read_text(encoding="utf-8")
    m = re.search(r"export const BASE\s*=\s*([^;]+);", api)
    assert m, "no se encontró la definición de BASE"
    cadena = m.group(1)
    assert cadena.strip().startswith("API_LOCAL"), (
        f"API_LOCAL no va primero en la cadena: {cadena.strip()}"
    )
    assert "matcherEscritorio?.apiLocal" in api
    assert "apiLocal:" in PRELOAD.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Que el paquete traiga todo lo que el backend necesita
# ---------------------------------------------------------------------------
def test_el_paquete_trae_el_motor_el_backend_y_el_python(config):
    """Falta una y el servidor muere con `ModuleNotFoundError` recién en la
    máquina del dueño, después de instalar 90 MB."""
    origenes = {r["from"] for r in config["extraResources"]}
    for necesario in ("matcher", "webapp/backend", "dist-owner/python"):
        assert necesario in origenes, f"falta `{necesario}` en extraResources"


def test_el_pack_de_caras_viaja_donde_el_motor_lo_busca(config):
    """`fotos.PACK_INCLUIDO` es `matcher/../assets/personas`. Empaquetado, el
    motor queda en `servidor/matcher`, así que el pack tiene que estar en
    `servidor/assets/personas` o la demo abre con avatares de respaldo."""
    mapa = {r["from"]: r["to"] for r in config["extraResources"]}
    assert mapa.get("assets/personas") == "servidor/assets/personas"
    assert mapa.get("matcher") == "servidor/matcher"


def test_el_instalador_no_se_lleva_el_sdk_de_android(config):
    """Las dependencias de este package.json son las de Capacitor: el SDK de
    Android entero, con sus `.dex`, viajaría adentro del instalador de
    Windows. Ya pasó en el primer empaquetado de la edición normal."""
    assert "!node_modules/**/*" in config["files"]


def test_el_python_embebido_queda_con_los_imports_de_sitio_prendidos():
    """El Python embebido de python.org trae `import site` COMENTADO en el
    `._pth`: sin descomentarlo no encuentra nada de lo que instale pip y el
    servidor muere apenas arranca."""
    flujo = FLUJO.read_text(encoding="utf-8")
    assert "import site" in flujo and "._pth" in flujo
    assert "Lib\\site-packages" in flujo


def test_el_flujo_comprueba_que_el_backend_importa_antes_de_empaquetar():
    """Falla ACÁ, con un mensaje claro, en vez de fallar en la máquina del
    dueño después de instalar."""
    flujo = FLUJO.read_text(encoding="utf-8")
    assert "from webapp.backend.api import app" in flujo


def test_hay_comandos_para_correr_y_empaquetar_la_edicion_owner(paquete):
    for guion in ("pc:owner", "pc:owner:windows"):
        assert guion in paquete["scripts"], f"falta `npm run {guion}`"
    assert "--owner" in paquete["scripts"]["pc:owner"], (
        "sin la bandera, `npm run pc:owner` corre la edición normal desde el "
        "repo (no hay carpeta `servidor/` que la delate)"
    )
    assert "electron-builder-owner.yml" in paquete["scripts"]["pc:owner:windows"]


def test_la_edicion_owner_no_pisa_a_la_normal(config, ):
    """Cada una con su `appId` y su carpeta: conviven en la misma PC, cada una
    con su base. Con el mismo appId, instalar una desinstalaría la otra."""
    normal = yaml.safe_load((RAIZ / "electron-builder.yml").read_text(encoding="utf-8"))
    assert config["appId"] != normal["appId"]
    assert config["productName"] != normal["productName"]


def test_el_instalador_owner_tampoco_propone_el_disco_c(config):
    """El pedido del dueño (regla 19) vale para las dos ediciones: es el mismo
    `.nsh`."""
    assert config["nsis"]["include"] == "assets/marca/instalador.nsh"
    assert config["nsis"]["oneClick"] is False
    assert config["nsis"]["allowToChangeInstallationDirectory"] is True
    assert config["nsis"]["createDesktopShortcut"] is True
    assert config["nsis"]["createStartMenuShortcut"] is True


# ---------------------------------------------------------------------------
# Lo que la edición owner NO puede ser (reglas 15 y 20)
# ---------------------------------------------------------------------------
def test_no_hay_ningun_token_ni_licencia_adentro_del_instalador():
    """ESTE ES EL TEST QUE MOTIVÓ EL ARCHIVO.

    El patrón que se usó de modelo mete un token de owner en texto plano
    adentro del script del instalador, en un repositorio público. Eso no es una
    licencia: es una credencial filtrada. La firma impide inventar licencias
    nuevas, no impide copiar la que está publicada.

    Acá no hace falta ninguna: Matcher vende suscripción, no licencias (regla
    15), el plan vive en el servidor, y la edición owner es una instancia
    propia con su propia base vacía — no hay nada que desbloquear.
    """
    sospechosos = re.compile(
        r"(token|licencia|license|serial|activaci[oó]n|clave)\s*[:=]\s*['\"][A-Za-z0-9+/_.\-]{16,}",
        re.IGNORECASE,
    )
    for archivo in (CONFIG, SERVIDOR, MAIN, PRELOAD, FLUJO, LEEME):
        texto = archivo.read_text(encoding="utf-8")
        m = sospechosos.search(texto)
        assert not m, f"{archivo.name} parece traer una credencial: {m.group(0)!r}"


def test_la_edicion_owner_no_toca_el_camino_de_los_planes(servidor):
    """El Gold del dueño sale de `MATCHER_CUENTAS_DUENIO`, la MISMA ruta de
    código que en el servidor real (`matcher/duenio.py`). Si la edición owner
    tuviera un atajo propio para ponerse en Gold, estaría probando algo que no
    es el producto: el `.exe` andaría y el servidor seguiría roto.

    Se mira el bloque `env:` del `spawn`, que es lo único que esta edición le
    puede decir al backend.
    """
    assert "MATCHER_CUENTAS_DUENIO: cuentasDuenio" in servidor
    entorno = servidor.split("env: {", 1)[1].split("},", 1)[0]
    claves = set(re.findall(r"^\s*([A-Z_][A-Z0-9_]*):", entorno, re.M))
    permitidas = {
        "PYTHONPATH",
        "MATCHER_BD",
        "MATCHER_EFIMERO",
        "MATCHER_DEMO",
        "MATCHER_CUENTAS_DUENIO",
        "MATCHER_PASARELA",
    }
    assert claves <= permitidas, (
        f"la edición owner le pasa al backend algo que no está previsto: "
        f"{claves - permitidas}"
    )


def test_no_se_cobra_ni_se_simula_un_cobro_en_local(servidor):
    """Sin pasarela configurada. La `demo` dice en pantalla que no mueve plata
    (regla 10); poner una pasarela real acá sería cobrar de verdad probando."""
    assert 'MATCHER_PASARELA: "demo"' in servidor


def test_la_cuenta_de_duenio_no_viene_puesta_de_fabrica(servidor):
    """La cuenta privilegiada de fábrica es el bug con el que se cuelan la
    mitad de los productos. El archivo se crea VACÍO, con instrucciones."""
    assert "PLANTILLA_DUENIO" in servidor
    plantilla = servidor.split("const PLANTILLA_DUENIO = [", 1)[1].split("].join", 1)[0]
    assert "@" not in plantilla.replace("# ", ""), (
        "la plantilla de duenio.txt trae un mail adentro"
    )
    assert 'return "";' in servidor, "leerDuenio no tiene salida vacía"


# ---------------------------------------------------------------------------
# La carpeta que se pidió, y que diga dónde está el .exe
# ---------------------------------------------------------------------------
def test_la_carpeta_de_descargas_owner_explica_donde_bajarlo():
    """El `.exe` no se commitea (infla el clon para siempre). Entonces la
    carpeta tiene que decir de dónde sale, o es una carpeta vacía."""
    assert LEEME.exists(), "falta descargas-owner/LEEME.md"
    texto = LEEME.read_text(encoding="utf-8")
    for pista in ("Releases", "owner-v", "Actions", "pc:owner:windows"):
        assert pista in texto, f"el LEEME no dice cómo obtenerlo: falta `{pista}`"
    assert "duenio.txt" in texto, "no explica cómo marcar la cuenta de dueño"


def test_el_flujo_publica_la_release_con_la_etiqueta():
    flujo = FLUJO.read_text(encoding="utf-8")
    assert "owner-v*" in flujo
    assert "gh release create" in flujo
    assert "upload-artifact" in flujo, (
        "sin artefacto, una corrida sin etiqueta no deja nada que bajar"
    )
