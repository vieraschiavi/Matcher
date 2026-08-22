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
NSH = RAIZ / "assets" / "marca" / "instalador.nsh"


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


# ---------------------------------------------------------------------------
# Dónde se instala: el pedido es que NO vaya a C: por defecto
# ---------------------------------------------------------------------------
def test_el_instalador_propone_un_disco_que_no_es_el_del_sistema(config):
    """Sin script propio, electron-builder con `perMachine: false` propone
    %LOCALAPPDATA%\\Programs\\Matcher — o sea C:, siempre."""
    assert NSH.exists(), "falta el script que elige el disco"
    assert config["nsis"]["include"] == "assets/marca/instalador.nsh", (
        "el script existe pero no está enganchado: electron-builder no lo "
        "compila y el instalador vuelve a proponer C:"
    )


def test_el_script_del_disco_tiene_las_tres_guardas():
    """Cada una de las tres evita que el instalador quede inservible para
    alguien. Están explicadas en el encabezado del .nsh."""
    nsh = NSH.read_text(encoding="utf-8")

    # 1. Sólo discos fijos: un pendrive o una unidad de red que mañana no está
    #    deja un acceso directo que abre un error.
    assert '${GetDrives} "HDD"' in nsh, "enumera discos que no son fijos"

    # 2. Prueba de escritura: que el disco exista y tenga lugar no quiere decir
    #    que este usuario pueda escribir ahí (no hay administrador).
    assert "FileOpen" in nsh and "${Errors}" in nsh, "elige el disco sin probar a escribir"

    # 3. No pisa una instalación existente: hacerlo movería el programa de
    #    lugar en una actualización y dejaría la copia vieja ocupando disco.
    assert 'ReadRegStr $R9 HKCU "${INSTALL_REGISTRY_KEY}" "InstallLocation"' in nsh
    assert "${If} $R9 ==" in nsh, "no chequea si ya hay una instalación"


def test_la_letra_del_sistema_no_esta_cableada():
    """Windows no siempre está en C:. Cablear "C" daría por bueno el disco del
    sistema en una máquina donde el sistema está en otra letra — justo el disco
    que el dueño no quiere."""
    nsh = NSH.read_text(encoding="utf-8")
    assert "$WINDIR" in nsh, "no lee la letra del sistema, la asume"
    assert not re.search(r'\$R0\s*==\s*"C"', nsh), "cableó la letra C"


def test_si_no_hay_otro_disco_igual_instala():
    """La mayoría de las máquinas con Windows tienen un solo disco. Un
    instalador que se planta porque no encontró un D: no instala en el 80% de
    las computadoras: C: tiene que seguir siendo el respaldo."""
    nsh = NSH.read_text(encoding="utf-8")
    # La escritura del registro va ADENTRO del `${If} $MatcherDisco != ""`: sin
    # disco no se escribe nada y el default de electron-builder (C:) queda.
    assert '${If} $MatcherDisco != ""' in nsh
    cuerpo = nsh.split('${If} $MatcherDisco != ""', 1)[1]
    assert "WriteRegExpandStr" in cuerpo, (
        "la propuesta de disco no está condicionada a haber encontrado uno"
    )
    assert "Abort" not in nsh and "Quit" not in nsh, (
        "el instalador se planta en vez de caer en C:"
    )


def test_el_script_del_instalador_compila(tmp_path):
    """UN .NSH NO SE PRUEBA LEYÉNDOLO.

    Los tests de arriba miran que estén las guardas; éste comprueba que NSIS
    lo acepte. Un `${If}` mal cerrado, un registro pisado o un callback de
    `GetDrives` con la firma cambiada no se ven leyendo: se ven cuando el
    empaquetado explota, y para entonces el `.exe` no existe.

    Se compila con un arnés que define lo que define electron-builder e
    inserta `preInit` donde lo inserta su plantilla. Que ARRANQUE en Windows
    sigue sin verificarse acá — eso lo prueba correr el instalador de verdad.
    """
    import shutil
    import subprocess

    makensis = shutil.which("makensis")
    if not makensis:
        pytest.skip("makensis no instalado (apt-get install nsis)")

    arnes = tmp_path / "arnes.nsi"
    arnes.write_text(
        '!define INSTALL_REGISTRY_KEY "Software\\\\Matcher-prueba"\n'
        f'OutFile "{tmp_path / "salida.exe"}"\n'
        'InstallDir "$LOCALAPPDATA\\Programs\\Matcher"\n'
        "RequestExecutionLevel user\n"
        f'!include "{NSH}"\n'
        "Function .onInit\n  !insertmacro preInit\nFunctionEnd\n"
        'Section "Principal"\n  SetOutPath "$INSTDIR"\nSectionEnd\n',
        encoding="utf-8",
    )
    r = subprocess.run(
        [makensis, "-V4", str(arnes)], capture_output=True, text=True, timeout=180
    )
    assert r.returncode == 0, f"el script no compila:\n{r.stdout}\n{r.stderr}"
    assert "warning" not in r.stdout.lower(), f"NSIS avisa algo:\n{r.stdout}"
