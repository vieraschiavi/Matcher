// Festejos y avisos flotantes (toasts), sin dependencia de contexto.
//
// Va por eventos de window y no por un contexto de React a propósito: se
// dispara desde handlers sueltos (dar like, adivinar en Crush Time, el sondeo
// de likes nuevos) y enhebrar un hook hasta cada uno de esos lugares es más
// código que el feature. El componente <Avisos/> de App.jsx escucha y pinta.

const EVENTO = "matcher:aviso";

/**
 * tipo: "festejo" (grande, con corazones) | "info" | "ok"
 * `vibrar` es el patrón háptico; en escritorio no existe y no pasa nada.
 */
export function avisar(texto, { tipo = "info", vibrar = null } = {}) {
  if (vibrar) {
    try {
      navigator.vibrate?.(vibrar);
    } catch {
      /* sin vibrador */
    }
  }
  window.dispatchEvent(new CustomEvent(EVENTO, { detail: { texto, tipo, id: Date.now() } }));
}

export function alAvisar(fn) {
  const oir = (e) => fn(e.detail);
  window.addEventListener(EVENTO, oir);
  return () => window.removeEventListener(EVENTO, oir);
}


// --- festejo de match, global -----------------------------------------------
//
// El festejo vivía dentro de Descubrir, así que sólo salía al hacer match
// deslizando. Los matches que nacen en "Te gustaron", el radar, los cruces,
// el ranking o Crush Time llevaban derecho al chat y no se veía ni el fuego
// ni el cartel — que es justo el momento que hay que celebrar. Ahora el
// festejo lo monta App una sola vez y cualquier pantalla lo dispara.
const MATCH = "matcher:match";

export function festejarMatch(datos) {
  try {
    navigator.vibrate?.([30, 60, 30, 60, 80]);
  } catch {
    /* sin vibrador */
  }
  window.dispatchEvent(new CustomEvent(MATCH, { detail: datos }));
}

export function alFestejarMatch(fn) {
  const oir = (e) => fn(e.detail);
  window.addEventListener(MATCH, oir);
  return () => window.removeEventListener(MATCH, oir);
}
