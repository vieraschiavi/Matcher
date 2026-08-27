// Servidor LOCAL de la edición OWNER.
//
// QUÉ ES ESTO Y POR QUÉ EXISTE
// En la edición normal el `.exe` es una ventana: no trae backend, y habla con
// el servidor compartido. Es lo correcto para el producto — una app de citas
// necesita la base de todo el mundo, no una copia local (ver `main.js`).
//
// La edición OWNER es otra cosa: es para que el dueño pruebe el producto
// completo en su máquina, sin depender de que haya un servidor arriba, sin
// credenciales de pasarela y sin internet. Por eso trae el backend adentro y
// lo levanta al abrir.
//
// LO QUE ESTO **NO** ES: no es "el .exe que desbloquea la versión paga". El
// plan de un cliente vive en el servidor compartido y se decide al entrar
// (regla 15). Acá no hay nada que desbloquear porque no hay nada que cobrar:
// es una instancia propia, con su propia base vacía, en la máquina del dueño.
// Copiar este ejecutable no le da a nadie acceso a las cuentas de nadie.
//
// TRES DECISIONES QUE IMPORTAN
//
// 1. **Escucha SÓLO en 127.0.0.1.** Nunca en 0.0.0.0. Un backend de escritorio
//    escuchando en todas las interfaces expone la base al resto de la red wifi
//    —el bar, la oficina, el aeropuerto— sin que nadie se entere.
// 2. **El puerto se elige libre, no se cablea.** Un puerto fijo choca con
//    cualquier otra cosa que lo esté usando y el arranque falla con un error
//    que no dice nada.
// 3. **Si el servidor no arranca, la app NO se queda muda.** `apiLocal` queda
//    vacío y el frontend cae al backend remoto de siempre. Peor que no tener
//    servidor local es tener uno que no responde y una app que le habla igual.

const { spawn } = require("child_process");
const net = require("net");
const path = require("path");
const fs = require("fs");

/**
 * ¿Este ejecutable es la edición OWNER?
 *
 * Se decide MIRANDO EL CONTENIDO, no una bandera. La primera versión leía
 * `process.env.MATCHER_EDICION`, y estaba mal por los dos lados: en el `.exe`
 * empaquetado esa variable no la pone nadie —electron-builder no inyecta
 * entorno en tiempo de ejecución—, así que la edición owner nunca se hubiera
 * reconocido a sí misma y habría abierto contra el servidor remoto, que es
 * justo lo que existe para no hacer; y en la edición normal cualquiera la
 * podía prender a mano.
 *
 * Que la carpeta `servidor/` exista SÓLO puede pasar si el paquete se armó con
 * `electron-builder-owner.yml`. El `--owner` de la línea de comandos queda
 * como atajo para probar desde el repo (`npm run pc:owner`), donde no hay nada
 * empaquetado; en el `.exe` instalado no cambia nada, porque ahí la carpeta
 * `servidor/` decide sola.
 */
function esOwner() {
  return process.argv.includes("--owner") || ubicaciones().empaquetado;
}

/**
 * Las cuentas del dueño, leídas de un archivo de texto en la carpeta de datos.
 *
 * POR QUÉ UN ARCHIVO Y NO UNA VARIABLE DE ENTORNO
 * En el servidor, `MATCHER_CUENTAS_DUENIO` se pone en el panel de la
 * plataforma (ver `matcher/duenio.py`). En una PC no hay panel: quien instala
 * el `.exe` no va a abrir las variables de entorno de Windows. Sin esto, la
 * edición owner arranca con la lista vacía y el dueño **no puede ver su propio
 * panel** en la copia que existe para probarlo.
 *
 * POR QUÉ NO SE INVENTA UN VALOR POR DEFECTO
 * Sería la cuenta privilegiada de fábrica que `duenio.py` se cuida de no
 * tener. El archivo se crea vacío, con instrucciones adentro, y hasta que
 * alguien escriba un mail la lista sigue vacía.
 */
function archivoDuenio(datos) {
  return path.join(datos, "duenio.txt");
}

function leerDuenio(datos) {
  const archivo = archivoDuenio(datos);
  try {
    if (!fs.existsSync(archivo)) {
      fs.mkdirSync(datos, { recursive: true });
      fs.writeFileSync(archivo, PLANTILLA_DUENIO, "utf8");
      return "";
    }
    return fs
      .readFileSync(archivo, "utf8")
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter((l) => l && !l.startsWith("#"))
      .join(",");
  } catch {
    return ""; // sin lista, la app abre igual: sólo no hay panel
  }
}

const PLANTILLA_DUENIO = [
  "# Cuentas de dueño de esta copia de Matcher.",
  "#",
  "# Escribí abajo el mail con el que te registrás en la app, uno por linea,",
  "# guardá el archivo y volvé a abrir Matcher. Esa cuenta queda en Gold y ve",
  "# el panel (facturación, clientes, pedidos de demo).",
  "#",
  "# Las lineas que empiezan con # se ignoran. Vacio = ninguna cuenta de",
  "# dueño, que es el valor por defecto a proposito: nunca hay una cuenta",
  "# privilegiada de fabrica.",
  "",
].join("\n");

/** Un puerto libre pedido al sistema. Ver decisión 2 del encabezado. */
function puertoLibre() {
  return new Promise((resolve, reject) => {
    const s = net.createServer();
    s.unref();
    s.on("error", reject);
    // Puerto 0 = "dame uno libre". Se cierra enseguida y se usa ese número:
    // hay una ventana mínima de carrera, pero es infinitamente mejor que
    // cablear 8820 y chocar con lo que sea que ya lo tenga.
    s.listen(0, "127.0.0.1", () => {
      const { port } = s.address();
      s.close(() => resolve(port));
    });
  });
}

/**
 * Dónde está el intérprete de Python y la raíz del backend empaquetado.
 *
 * En el `.exe` instalado, electron-builder deja los `extraResources` en
 * `process.resourcesPath`. Corriendo desde el repo (`npm run pc:owner`) se usa
 * el Python del sistema y el código de la carpeta de al lado — así el mismo
 * archivo sirve para probar sin empaquetar nada.
 */
function ubicaciones() {
  const empaquetado = path.join(process.resourcesPath || "", "servidor");
  if (fs.existsSync(empaquetado)) {
    const exe = process.platform === "win32" ? "python.exe" : "bin/python3";
    return {
      python: path.join(empaquetado, "python", exe),
      raiz: empaquetado,
      empaquetado: true,
    };
  }
  return {
    python: process.platform === "win32" ? "python" : "python3",
    raiz: path.join(__dirname, ".."),
    empaquetado: false,
  };
}

/**
 * Levanta el backend y devuelve `{ url, detener }`, o `null` si no se pudo.
 *
 * NUNCA levanta una excepción: si algo falla, la app tiene que abrir igual
 * contra el servidor remoto. Un error acá no puede dejar al dueño sin poder
 * abrir su propio programa.
 */
async function levantar({ datos, cuentasDuenio }) {
  try {
    const { python, raiz, empaquetado } = ubicaciones();
    const puerto = await puertoLibre();
    fs.mkdirSync(datos, { recursive: true });

    const hijo = spawn(
      python,
      ["-m", "uvicorn", "webapp.backend.api:app",
       "--host", "127.0.0.1", "--port", String(puerto), "--log-level", "warning"],
      {
        cwd: raiz,
        env: {
          ...process.env,
          PYTHONPATH: raiz,
          // La base va a la carpeta de datos del usuario, NO adentro de la
          // instalación: el desinstalador de electron-builder hace `RMDir /r`
          // sobre $INSTDIR en cada actualización, y con la base ahí adentro se
          // perdería la cuenta y los matches en cada update, en silencio.
          MATCHER_BD: path.join(datos, "matcher.db"),
          MATCHER_EFIMERO: "0",
          // Siembra los perfiles sintéticos para que la app no abra vacía. Van
          // marcados `sintetico: true` y la interfaz lo dice (regla 5).
          MATCHER_DEMO: "1",
          // El Gold del dueño sale de acá, igual que en el servidor real: es
          // la MISMA ruta de código, no un atajo de la edición owner.
          MATCHER_CUENTAS_DUENIO: cuentasDuenio,
          // Sin pasarela configurada: en local no se cobra ni se simula un
          // cobro. La pasarela `demo` dice en pantalla que no mueve plata.
          MATCHER_PASARELA: "demo",
        },
        stdio: ["ignore", "pipe", "pipe"],
        windowsHide: true,
      }
    );

    hijo.on("error", () => {});          // sin Python no hay servidor: se sigue
    hijo.stderr.on("data", () => {});    // no se loguea: puede traer rutas del disco

    const url = `http://127.0.0.1:${puerto}`;
    const listo = await esperarSalud(url, empaquetado ? 40 : 25);
    if (!listo) {
      try { hijo.kill(); } catch { /* ya estaba muerto */ }
      return null;
    }
    return { url, detener: () => { try { hijo.kill(); } catch { /* ya murió */ } } };
  } catch {
    return null;
  }
}

/**
 * Espera a que `/api/salud` conteste. Sin esto la ventana abre antes que el
 * servidor y la primera pantalla muestra un error de red que se arregla solo
 * al recargar — el peor tipo de bug, porque el que lo ve no lo puede reportar.
 */
async function esperarSalud(url, intentos) {
  for (let i = 0; i < intentos; i++) {
    try {
      const r = await fetch(`${url}/api/salud`);
      if (r.ok) return true;
    } catch { /* todavía no levantó */ }
    await new Promise((r) => setTimeout(r, 250));
  }
  return false;
}

module.exports = { levantar, esOwner, leerDuenio, archivoDuenio };
