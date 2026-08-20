"""El programa de escritorio (Electron/Windows) y su instalador.

Un instalador no se prueba leyéndolo, igual que un `.bat`: que ARRANQUE lo
verifica correr el empaquetado de verdad. Lo que estos tests sí atrapan desde
acá es la clase de error que no se ve hasta que alguien ya bajó el `.exe`:

- que el instalador deje de preguntar dónde instalar (una sola opción en
  `false` y la opción de elegir carpeta se ignora en silencio);
- que el programa de Windows se quede sin botón de comprar, porque la app lo
  confunda con una app de tienda;
- que la ventana se abra con Node expuesto a una página que muestra texto y
  links escritos por desconocidos;
- que el ícono del escritorio quede con la paleta vieja mientras la app abre
  con la nueva.

Los tres primeros ya pasaron o estuvieron a un renglón de pasar.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

RAIZ = Path(__file__).resolve().parents[1]
CONFIG = RAIZ / "electron-builder.yml"
MAIN = RAIZ / "electron" / "main.js"
PRELOAD = RAIZ / "electron" / "preload.js"


@pytest.fixture(scope="module")
def config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def paquete() -> dict:
    return json.loads((RAIZ / "package.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Lo que pidió el dueño, opción por opción
# ---------------------------------------------------------------------------
def test_el_instalador_es_un_exe_con_pantallas(config):
    """`oneClick: false` es la que manda: con `true`, NSIS instala solo donde
    él quiere y `allowToChangeInstallationDirectory` no hace nada."""
    assert config["win"]["target"] == ["nsis"]
    assert config["nsis"]["oneClick"] is False, (
        "con oneClick en true no hay pantallas y no se puede elegir la carpeta"
    )


def test_se_puede_elegir_donde_instalar(config):
    assert config["nsis"]["allowToChangeInstallationDirectory"] is True


def test_icono_en_el_escritorio_y_en_el_menu_inicio(config):
    assert config["nsis"]["createDesktopShortcut"] is True
    assert config["nsis"]["createStartMenuShortcut"] is True


def test_no_pide_administrador(config):
    """`perMachine: true` exige elevación, y en una máquina del trabajo eso
    significa que la mitad de la gente no lo puede instalar."""
    assert config["nsis"]["perMachine"] is False


def test_al_desinstalar_no_queda_la_sesion_abierta(config):
    """Lo único que el programa guarda en la máquina es el token de sesión.
    Dejarlo después de desinstalar, en una computadora compartida, es dejarle
    la cuenta abierta al que venga después."""
    assert config["nsis"]["deleteAppDataOnUninstall"] is True


def test_los_iconos_del_instalador_existen(config):
    for clave in ("installerIcon", "uninstallerIcon", "installerHeaderIcon"):
        ruta = RAIZ / config["nsis"][clave]
        assert ruta.exists(), f"{clave} apunta a {ruta}, que no está"
    ico = RAIZ / config["win"]["icon"]
    assert ico.exists() and ico.suffix == ".ico", "Windows necesita un .ico de verdad"


def test_el_ico_trae_varias_medidas():
    """Con una sola medida adentro, el explorador escala a lo bruto y el ícono
    chico de la barra de tareas sale con los bordes sucios."""
    Image = pytest.importorskip("PIL.Image", reason="Pillow no instalado")
    with Image.open(RAIZ / "assets" / "marca" / "icono.ico") as img:
        # Un .ico es un contenedor: las medidas se leen de `img.ico.sizes()`,
        # no de `n_frames` (que en este formato es siempre 1 y hace pasar el
        # test por el motivo equivocado).
        medidas = img.ico.sizes()
    assert len(medidas) >= 5, f"el .ico trae una sola medida: {medidas}"
    assert (16, 16) in medidas, "falta la medida chica, la de la barra de tareas"
    assert (256, 256) in medidas, "falta la grande, la del escritorio con íconos grandes"


# ---------------------------------------------------------------------------
# Que el .exe pese lo que tiene que pesar
# ---------------------------------------------------------------------------
def test_el_instalador_no_se_lleva_el_sdk_de_android(config):
    """El primer empaquetado metió 2249 archivos en el asar: electron-builder
    incluye las dependencias de producción por su cuenta, y las de este
    package.json son las de Capacitor — el SDK de Android entero, con sus
    `.dex`, viajando adentro del instalador de Windows. `electron/main.js` no
    requiere nada de npm."""
    assert "!node_modules/**/*" in config["files"]


def test_el_programa_arranca_por_el_main_correcto(paquete):
    assert paquete["main"] == "electron/main.js"
    assert MAIN.exists()


def test_hay_comandos_para_empaquetar(paquete):
    for guion in ("pc", "pc:windows"):
        assert guion in paquete["scripts"], f"falta `npm run {guion}`"
    assert "electron-builder" in paquete["scripts"]["pc:windows"]


# ---------------------------------------------------------------------------
# Seguridad de la ventana
# ---------------------------------------------------------------------------
def test_la_ventana_no_le_da_node_a_la_pagina():
    """Una app de citas pinta bios, fotos y links de desconocidos. Con
    `nodeIntegration`, un XSS en una bio deja de ser un problema de la página y
    pasa a ser código corriendo en la máquina de la persona."""
    codigo = MAIN.read_text(encoding="utf-8")
    assert re.search(r"contextIsolation:\s*true", codigo)
    assert re.search(r"nodeIntegration:\s*false", codigo)
    assert "webSecurity: false" not in codigo


def test_los_links_externos_salen_al_navegador_del_sistema():
    """Sin esto, un link en una bio convierte la ventana de Matcher en un
    navegador sin barra de direcciones: el escenario ideal para una pantalla de
    login falsa."""
    codigo = MAIN.read_text(encoding="utf-8")
    assert "setWindowOpenHandler" in codigo
    assert "will-navigate" in codigo
    assert "shell.openExternal" in codigo


def test_el_puente_del_preload_no_expone_el_modulo_entero():
    """`contextBridge` con `shell` o `ipcRenderer` enteros adentro es lo mismo
    que no tener aislamiento."""
    codigo = PRELOAD.read_text(encoding="utf-8")
    assert "contextBridge.exposeInMainWorld" in codigo
    assert not re.search(r"exposeInMainWorld\([^)]*,\s*(shell|ipcRenderer)\s*\)", codigo)
    assert re.search(r"https:", codigo), "abrirAfuera tiene que exigir https"


def test_el_esquema_del_login_esta_registrado(config):
    """Es lo que hace que el login de Google vuelva al programa: el navegador
    del sistema termina en `com.matcher.app://auth/...` y Windows se lo entrega
    a esta app."""
    esquemas = [e for p in config["protocols"] for e in p["schemes"]]
    assert "com.matcher.app" in esquemas
    assert "setAsDefaultProtocolClient" in MAIN.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Escritorio ≠ tienda: en Windows SÍ se vende
# ---------------------------------------------------------------------------
def test_el_escritorio_no_se_confunde_con_una_app_de_tienda():
    """Apple y Google exigen su pasarela; Microsoft no cobra nada por un `.exe`
    que se baja de nuestra web. El programa de Windows carga con `file:`, y el
    respaldo por protocolo de `api.js` lo marcaría como app de tienda: con eso
    el .exe quedaría sin botón de comprar, que es lo mismo que no tener
    producto."""
    api = (RAIZ / "webapp" / "frontend" / "src" / "api.js").read_text(encoding="utf-8")
    assert "matcherEscritorio" in api, "api.js no detecta el escritorio"
    assert re.search(r"!ESCRITORIO\s*&&", api), (
        "el respaldo por protocolo tiene que excluir al escritorio, "
        "o el .exe se comporta como una app de tienda"
    )
    assert "escritorio: true" in PRELOAD.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Política de contenido
# ---------------------------------------------------------------------------
def test_la_pagina_trae_csp_sin_eval_ni_scripts_en_linea():
    html = (RAIZ / "webapp" / "frontend" / "index.html").read_text(encoding="utf-8")
    m = re.search(r'http-equiv="Content-Security-Policy"\s*\n?\s*content="([^"]+)"', html)
    assert m, "falta la CSP"
    csp = m.group(1)
    script = re.search(r"script-src ([^;]+)", csp).group(1)
    assert "unsafe-eval" not in script and "unsafe-inline" not in script, (
        f"script-src permisiva: {script}"
    )
    for regla in ("object-src 'none'", "frame-src 'none'", "base-uri 'none'"):
        assert regla in csp, f"falta `{regla}`"
