// Preload: el único puente entre la app web y Electron.
//
// Corre con `contextIsolation: true`, así que lo que se expone acá es TODO lo
// que la página puede tocar del sistema. No se expone `require`, ni `ipcRenderer`
// entero, ni el módulo `shell`: una app de citas carga fotos y links de
// desconocidos, y con `nodeIntegration` prendida un XSS deja de ser un problema
// de la web para pasar a ser ejecución de código en la máquina de la persona.
//
// `escritorio: true` es la bandera que lee `webapp/frontend/src/api.js` para
// saber que esto NO es una app de tienda: en Windows se puede cobrar, no hay
// comisión de Apple ni de Google de por medio.

const { contextBridge, ipcRenderer, shell } = require("electron");

contextBridge.exposeInMainWorld("matcherEscritorio", {
  escritorio: true,
  version: process.env.MATCHER_VERSION || "",
  plataforma: process.platform,

  /** Abre un link en el navegador del sistema, nunca adentro de la ventana. */
  abrirAfuera: (url) => {
    // La validación se repite acá aunque el proceso principal también valide:
    // este canal es el que ve la página, y una lista blanca del lado de adentro
    // no sirve de nada si la puerta de afuera acepta cualquier cosa.
    if (typeof url === "string" && /^https:\/\//i.test(url)) {
      shell.openExternal(url);
    }
  },

  /** Enlaces `com.matcher.app://` que el sistema le entrega a la app (login). */
  alEnlace: (fn) => {
    const oyente = (_evento, url) => fn(url);
    ipcRenderer.on("matcher:enlace", oyente);
    return () => ipcRenderer.removeListener("matcher:enlace", oyente);
  },
});
