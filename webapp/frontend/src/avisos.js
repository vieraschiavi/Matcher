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
