// Matcher para Windows (y Linux/macOS): la MISMA app React, en una ventana
// de escritorio.
//
// Qué es y qué no es
// ------------------
// Esto NO es un segundo producto: carga `webapp/frontend/dist`, el mismo build
// que sirve la web y que empaqueta el APK. Es la regla que MV Cliente IA
// aprendió a los golpes — dos interfaces se desincronizan a la semana y hay que
// mantener dos apps. Acá el escritorio es una ventana, no una versión.
//
// El backend NO viaja adentro del .exe, y es a propósito: una app de citas
// necesita la base compartida de todo el mundo, no una copia local. El programa
// habla con el mismo servidor que el APK y la web, así que la cuenta, los
// matches y los chats son los mismos abriendo el .exe, el teléfono o el
// navegador.
//
// Seguridad de la ventana (lo importante de este archivo)
// -------------------------------------------------------
// Una app de citas muestra fotos, bios y links escritos por desconocidos. Si
// eso corre con `nodeIntegration`, un XSS deja de ser un problema de la web y
// pasa a ser código ejecutándose en la máquina de la persona. Entonces:
//   · `contextIsolation: true` y `nodeIntegration: false` (los valores por
//     defecto de Electron moderno; van explícitos para que nadie los "arregle")
//   · Todo lo que la página puede tocar del sistema pasa por `preload.js`
//   · Navegar fuera de la app está prohibido: cualquier `http(s)` se abre en el
//     navegador del sistema y la ventana se queda donde estaba
//   · `window.open` no abre ventanas de Electron: abre el navegador

const path = require("path");
const { app, BrowserWindow, Menu, shell, dialog } = require("electron");
const servidorLocal = require("./servidor-local");

// EDICIÓN OWNER: el .exe trae su propio backend y lo levanta al abrir.
//
// Se reconoce por su CONTENIDO (`servidorLocal.esOwner()`), no por una
// bandera: la carpeta `servidor/` sólo la deja el empaquetado con
// `electron-builder-owner.yml`. Está explicado en `servidor-local.js`.
//
// Que esto exista NO le da acceso a nadie a la versión paga: el plan de un
// cliente vive en el servidor y se decide al entrar (regla 15). Acá se levanta
// una instancia propia, con su propia base vacía, en la máquina del dueño.
const ES_OWNER = servidorLocal.esOwner();
let servidor = null;

const ESQUEMA = "com.matcher.app";
const DIST = path.join(__dirname, "..", "webapp", "frontend", "dist");
const INDEX = path.join(DIST, "index.html");
const ICONO = path.join(__dirname, "..", "assets", "marca", "icono_1024.png");

let ventana = null;

/** Un enlace `com.matcher.app://…` que llegó del sistema (vuelta del login). */
function entregarEnlace(url) {
  if (!url || !url.startsWith(`${ESQUEMA}://`)) return;
  if (ventana) {
    if (ventana.isMinimized()) ventana.restore();
    ventana.focus();
    ventana.webContents.send("matcher:enlace", url);
  }
}

function crearVentana() {
  ventana = new BrowserWindow({
    width: 1180,
    height: 820,
    minWidth: 380, // el CSS móvil arranca en 860px: angostando se ve el modo teléfono
    minHeight: 560,
    // Que el fondo de la ventana sea el de la app y no blanco: sin esto hay un
    // flash blanco de medio segundo al abrir que se ve barato en una app oscura.
    backgroundColor: "#0b1016",
    icon: ICONO,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      // La app pide cámara y ubicación. `webSecurity` queda prendida: la API
      // manda CORS correcto, así que no hace falta bajarla (y bajarla sería
      // abrirle la puerta a cualquier origen).
      spellcheck: false,
    },
  });

  // `ready-to-show` en vez de mostrar de una: la ventana aparece con la app ya
  // pintada, no con un rectángulo vacío que se va llenando.
  ventana.once("ready-to-show", () => ventana.show());

  ventana.loadFile(INDEX).catch((e) => {
    dialog.showErrorBox(
      "Matcher",
      `No se pudo cargar la aplicación.\n\n${e.message}\n\n` +
        "Si estás corriendo desde el código, falta compilar el frontend:\n" +
        "  npm run build:web"
    );
  });

  // Cualquier navegación a un sitio externo sale al navegador del sistema. La
  // ventana de Matcher muestra Matcher y nada más: sin esto, un link en una bio
  // convierte la app en un navegador sin barra de direcciones, que es la
  // situación ideal para una pantalla de login falsa.
  const afuera = (url) => {
    if (/^https?:\/\//i.test(url)) shell.openExternal(url);
  };
  ventana.webContents.setWindowOpenHandler(({ url }) => {
    afuera(url);
    return { action: "deny" };
  });
  ventana.webContents.on("will-navigate", (evento, url) => {
    if (!url.startsWith("file://")) {
      evento.preventDefault();
      afuera(url);
    }
  });

  ventana.on("closed", () => {
    ventana = null;
  });
}

// Menú mínimo en español. El de fábrica viene en inglés y con entradas de
// desarrollo (Toggle DevTools, Reload) que no le sirven a nadie que instaló un
// .exe. Se dejan los atajos de edición porque sin ellos Ctrl+C/Ctrl+V no andan
// en los campos de texto: Electron los resuelve por menú, no por el sistema.
function menu() {
  return Menu.buildFromTemplate([
    {
      label: "Matcher",
      submenu: [
        { label: "Recargar", accelerator: "CmdOrCtrl+R", click: () => ventana?.reload() },
        // Sólo en la edición owner, y con motivo: es la ÚNICA forma de decirle
        // a esta copia cuál es la cuenta del dueño. Sin esto habría que abrir
        // las variables de entorno de Windows, y entonces el panel —que es
        // parte de lo que la edición owner existe para probar— no se ve nunca.
        ...(ES_OWNER
          ? [
              { type: "separator" },
              {
                label: "Cuenta de dueño (duenio.txt)…",
                click: () => {
                  const datos = app.getPath("userData");
                  servidorLocal.leerDuenio(datos); // lo crea con instrucciones si falta
                  shell.openPath(servidorLocal.archivoDuenio(datos));
                },
              },
            ]
          : []),
        { type: "separator" },
        { label: "Salir", accelerator: "CmdOrCtrl+Q", role: "quit" },
      ],
    },
    {
      label: "Editar",
      submenu: [
        { label: "Deshacer", role: "undo" },
        { label: "Rehacer", role: "redo" },
        { type: "separator" },
        { label: "Cortar", role: "cut" },
        { label: "Copiar", role: "copy" },
        { label: "Pegar", role: "paste" },
        { label: "Seleccionar todo", role: "selectAll" },
      ],
    },
    {
      label: "Ver",
      submenu: [
        { label: "Acercar", role: "zoomIn" },
        { label: "Alejar", role: "zoomOut" },
        { label: "Tamaño normal", role: "resetZoom" },
        { type: "separator" },
        { label: "Pantalla completa", role: "togglefullscreen" },
      ],
    },
  ]);
}

// Una sola instancia. Sin esto, abrir el acceso directo dos veces levanta dos
// ventanas con la misma sesión, y —peor— el enlace de vuelta del login se lo
// come el proceso nuevo mientras el usuario mira el viejo.
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", (_e, argv) => {
    if (ventana) {
      if (ventana.isMinimized()) ventana.restore();
      ventana.focus();
    }
    // En Windows el enlace profundo llega como argumento del proceso nuevo, no
    // por un evento: hay que buscarlo en el argv.
    entregarEnlace(argv.find((a) => a.startsWith(`${ESQUEMA}://`)));
  });

  app.whenReady().then(async () => {
    // El servidor local va ANTES de crear la ventana: si la ventana abriera
    // primero, la primera pantalla mostraría un error de red que se arregla
    // solo al recargar — el peor tipo de bug, porque quien lo ve no lo puede
    // reportar.
    if (ES_OWNER) {
      const datos = app.getPath("userData");
      servidor = await servidorLocal.levantar({
        datos,
        // De un archivo de texto en la carpeta de datos, no del entorno: en una
        // PC no hay panel de plataforma donde poner variables. Ver
        // `servidor-local.js`.
        cuentasDuenio: servidorLocal.leerDuenio(datos),
      });
      // Si no arrancó, `apiLocal` queda vacío y el frontend cae al backend
      // remoto de siempre. Peor que no tener servidor local es tener uno que
      // no responde y una app que le habla igual.
      if (servidor) process.env.MATCHER_API_LOCAL = servidor.url;
    }

    // Registrar el esquema deja que el sistema devuelva a la app el
    // `com.matcher.app://auth/...` con el que vuelve el login de Google. En
    // desarrollo hay que decirle cuál es el ejecutable, porque si no registra
    // `electron.exe` en vez de Matcher.
    if (process.defaultApp && process.argv.length >= 2) {
      app.setAsDefaultProtocolClient(ESQUEMA, process.execPath, [
        path.resolve(process.argv[1]),
      ]);
    } else {
      app.setAsDefaultProtocolClient(ESQUEMA);
    }
    Menu.setApplicationMenu(menu());
    crearVentana();
    entregarEnlace(process.argv.find((a) => a.startsWith(`${ESQUEMA}://`)));

    app.on("activate", () => {
      if (BrowserWindow.getAllWindows().length === 0) crearVentana();
    });
  });

  // macOS entrega el enlace por evento y no por argv.
  app.on("open-url", (evento, url) => {
    evento.preventDefault();
    entregarEnlace(url);
  });

  app.on("window-all-closed", () => {
    if (process.platform !== "darwin") app.quit();
  });
}

// Al cerrar la app se baja el servidor local. Sin esto queda un proceso de
// Python huérfano con el archivo de la base tomado, y el próximo arranque no
// puede escribir — se ve como "la app dejó de guardar", que no se parece en
// nada a la causa.
app.on("will-quit", () => {
  if (servidor) servidor.detener();
});
