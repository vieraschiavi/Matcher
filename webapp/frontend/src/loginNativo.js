// Login con Google/Facebook desde la app instalada.
//
// POR QUÉ ESTE ARCHIVO EXISTE
//
// En la web alcanza con `window.location.href = url`: el navegador se va al
// proveedor, vuelve al callback y el backend redirige a la misma web. En la
// app instalada eso NO funciona, y falla de dos formas distintas a la vez:
//
// 1. **Google rechaza el WebView.** Cuando detecta un navegador embebido
//    responde `disallowed_useragent` y no deja ni ver la pantalla de login. Es
//    política de Google desde hace años, para apps nativas de cualquiera. No
//    se esquiva falseando el user-agent — eso es exactamente lo que la
//    política busca impedir, y además rompe el login apenas lo detectan.
//
// 2. **El token quedaba del otro lado.** Aun si el proveedor lo permitiera, el
//    callback devolvía el navegador a la web del backend. La app vive en otro
//    origen (`https://localhost`), así que el `localStorage` donde caía el
//    token no era el de la app: el usuario "entraba" y la app seguía sin
//    sesión, mostrando la web adentro del cascarón.
//
// LA FORMA CORRECTA, que es la que usan todas las apps nativas:
//
//   app → abre el navegador DEL SISTEMA (Chrome Custom Tab / Safari)
//       → el usuario se loguea con el proveedor
//       → el proveedor vuelve al callback HTTPS del backend
//       → el backend redirige a `com.matcher.app://auth/...`
//       → el sistema operativo enruta ese esquema a la app
//       → la app agarra el token y cierra el navegador
//
// El `client_secret` nunca sale del backend: el proveedor sigue redirigiendo a
// una URL HTTPS nuestra, y el enlace profundo es un salto posterior entre
// nuestro propio backend y nuestra propia app.

import { App } from "@capacitor/app";
import { Browser } from "@capacitor/browser";

import { api, esNativo } from "./api";

export const ESQUEMA = "com.matcher.app";

/** ¿Se puede hacer el login por enlace profundo en este dispositivo? */
export function hayLoginNativo() {
  return esNativo;
}

/**
 * Lee el enlace profundo de vuelta y devuelve qué hay que hacer.
 * `com.matcher.app://auth/entrar?token=…` → { ruta: "entrar", token }
 */
export function leerEnlace(url) {
  if (!url || !url.startsWith(`${ESQUEMA}://auth`)) return null;
  // No se usa `new URL()`: en algunos WebView viejos falla con esquemas
  // propios y devuelve pathname vacío.
  const sinEsquema = url.slice(`${ESQUEMA}://auth`.length);
  const [ruta, consulta = ""] = sinEsquema.split("?");
  const p = new URLSearchParams(consulta);
  return {
    ruta: (ruta || "/entrar").replace(/^\//, ""),
    token: p.get("token") || "",
    alta: p.get("alta") || "",
    error: p.get("error") || "",
  };
}

/**
 * Corre el login entero y resuelve con el resultado.
 *
 * Se resuelve por UNA de tres vías, y hay que contemplar las tres o la app
 * queda colgada con el botón girando:
 *   - llega el enlace profundo (el caso feliz);
 *   - el usuario cierra el navegador sin loguearse (`browserFinished`);
 *   - pasan `tiempoLimiteMs` sin ninguna de las dos.
 */
export async function entrarConProveedor(nombre, { tiempoLimiteMs = 180000 } = {}) {
  const { url } = await api.inicioLogin(nombre, "app");

  let quitarUrl = null;
  let quitarCierre = null;
  let reloj = null;

  const limpiar = async () => {
    if (reloj) clearTimeout(reloj);
    // `remove()` devuelve promesa en Capacitor 6; si no se espera, el listener
    // puede sobrevivir al siguiente intento y disparar dos veces.
    try { await quitarUrl?.remove(); } catch { /* ya removido */ }
    try { await quitarCierre?.remove(); } catch { /* ya removido */ }
  };

  return new Promise((resolver, rechazar) => {
    const terminar = async (fn, valor) => {
      await limpiar();
      try { await Browser.close(); } catch { /* ya estaba cerrado */ }
      fn(valor);
    };

    App.addListener("appUrlOpen", (ev) => {
      const datos = leerEnlace(ev?.url || "");
      if (!datos) return; // otro enlace profundo cualquiera: no es lo nuestro
      if (datos.error) {
        terminar(rechazar, new Error(datos.error));
        return;
      }
      terminar(resolver, datos);
    }).then((h) => { quitarUrl = h; });

    // El usuario cerró la pestaña del navegador a mano. Sin esto el botón
    // quedaba girando para siempre y había que matar la app.
    Browser.addListener("browserFinished", () => {
      terminar(rechazar, new Error("cancelado"));
    }).then((h) => { quitarCierre = h; });

    reloj = setTimeout(() => {
      terminar(rechazar, new Error("El login tardó demasiado. Probá de nuevo."));
    }, tiempoLimiteMs);

    Browser.open({ url, presentationStyle: "popover" }).catch((e) =>
      terminar(rechazar, e)
    );
  });
}
