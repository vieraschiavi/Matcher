import { Capacitor } from "@capacitor/core";

// Cliente HTTP. Una sola puerta a la API: si cada componente hace su fetch,
// el manejo del 401 y del 402 (sin cupo) termina copiado en quince lugares y
// alguno se olvida de alguno.

// A dónde le pega la app.
//
// En web es same-origin: el propio backend sirve el dist/, así que alcanza con
// rutas relativas. En el APK y en iOS NO: ahí el frontend vive en un origen
// local (`https://localhost`, ver abajo) y "/api" resolvería contra el propio
// WebView, que no tiene backend. La app arrancaba en blanco y sin un solo
// error visible.
//
// Por eso la URL del servidor se compila adentro del bundle con
// VITE_API_URL. Sin eso, un APK instalado no puede hablar con nadie.

// ---------------------------------------------------------------------------
// ¿Esto corre DENTRO de la app instalada?
//
// Se hacía mirando el protocolo (`capacitor:`, `ionic:`, `file:`) y estaba MAL,
// porque `capacitor.config.json` usa `androidScheme: "https"` — que es lo
// recomendado, porque habilita las APIs que exigen contexto seguro (cámara y
// geolocalización). Con eso el WebView carga desde `https://localhost`, así que
// la detección por protocolo daba SIEMPRE false adentro del APK.
//
// No se notaba porque el único uso era elegir la URL de la API, y en el APK
// `VITE_API_URL` viene compilada y gana igual. Pero apenas se colgaron
// decisiones de esta bandera, el error se volvió grave: en el APK se mostraría
// el botón de comprar (rechazo seguro de las tiendas, ver `cobroEnApp.js`) y el
// login iría por el WebView, que Google rechaza (ver `loginNativo.js`).
//
// `Capacitor.isNativePlatform()` es la API oficial y no depende del esquema. El
// chequeo de protocolo queda de respaldo por si el global no está inyectado.
//
// ESCRITORIO (Electron/Windows) NO ES UNA TIENDA. El .exe se descarga de
// nuestra web: Microsoft no cobra comisión ni exige pasarela propia, así que
// ahí SÍ se vende, igual que en la web. Se detecta aparte porque carga con
// `file:` y el respaldo de protocolo lo marcaría como app de tienda — y con
// eso el programa de Windows quedaría sin botón de comprar, que es lo mismo
// que no tener producto. Lo inyecta `electron/preload.js`.
const ESCRITORIO = Boolean(
  typeof window !== "undefined" && window.matcherEscritorio?.escritorio
);
const NATIVO = Boolean(
  Capacitor.isNativePlatform() ||
    // Respaldo por si el global no llegó a inyectarse: no cuesta nada y el
    // costo de equivocarse en esta bandera es un rechazo de tienda.
    (!ESCRITORIO &&
      typeof window !== "undefined" &&
      /^(capacitor|ionic|file):/.test(window.location.protocol))
);
const CONFIGURADA = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

// Backend por defecto para los builds empaquetados (APK, iOS, escritorio).
//
// ACÁ HUBO UN BUG CARO. El valor por defecto era `https://api.matcher.app`, un
// dominio de ejemplo que nunca existió ni se registró. Cualquier APK compilado
// sin `VITE_API_URL` —o sea, el que sale de correr `npm run apk:debug` a
// secas— quedaba apuntando ahí, y en el teléfono la app abría bien pero
// **cualquier acción moría con "Failed to fetch"**: no se podía ni entrar con
// las cuentas de demo. Nada en el build avisaba; el error recién aparecía con
// el teléfono en la mano.
//
// El valor por defecto ahora es el despliegue de producción real. Se sigue
// pudiendo pisar al compilar, que es lo que hay que hacer cuando el backend se
// mude:
//
//     VITE_API_URL=https://mi-backend npm run apk:debug
//
// `tests/test_url_api.py` no deja volver a un dominio de ejemplo.
const POR_DEFECTO = "https://matcher-sable.vercel.app";

// El escritorio necesita URL absoluta por el mismo motivo que el APK: la app
// se sirve desde el disco, no desde el backend, así que una ruta relativa
// apuntaría al sistema de archivos.
export const BASE = CONFIGURADA || (NATIVO || ESCRITORIO ? POR_DEFECTO : "");
export const esNativo = NATIVO;
export const esEscritorio = ESCRITORIO;

const LLAVE = "matcher.token";

export const token = {
  leer: () => localStorage.getItem(LLAVE) || "",
  guardar: (t) => localStorage.setItem(LLAVE, t),
  borrar: () => localStorage.removeItem(LLAVE),
};

// Error con la carga útil del backend adentro. `sinCupo` es la que dispara el
// muro de pago en la UI, así que necesita viajar entera (recurso + plan).
export class ErrorApi extends Error {
  constructor(estado, cuerpo) {
    super(cuerpo?.detail || `error ${estado}`);
    this.estado = estado;
    this.cuerpo = cuerpo || {};
  }
  get sinCupo() {
    return this.estado === 402;
  }
  get noAutorizado() {
    return this.estado === 401;
  }
  /** Hubo respuesta del servidor, así que red hubo. Existe para que quien
   *  atrapa un error pueda preguntar `e.sinRed` sin fijarse de qué clase es. */
  get sinRed() {
    return false;
  }
}

/** No se pudo ni hablar con el servidor: no hay respuesta HTTP que mirar. */
export class ErrorSinRed extends Error {
  constructor(base, causa) {
    const donde = base || "este mismo sitio";
    super(
      `No se puede conectar con el servidor (${donde}). ` +
        "Revisá que tengas internet; si el problema sigue, esta versión de la " +
        "app está compilada contra esa dirección y ahí no hay nadie contestando."
    );
    this.estado = 0;
    this.cuerpo = {};
    this.base = base;
    this.causa = causa;
  }
  get sinRed() {
    return true;
  }
  get sinCupo() {
    return false;
  }
  get noAutorizado() {
    return false;
  }
}

async function crudo(ruta, metodo, cuerpo, t) {
  let res;
  try {
    res = await fetch(`${BASE}/api${ruta}`, {
      method: metodo,
      headers: {
        ...(cuerpo ? { "Content-Type": "application/json" } : {}),
        ...(t ? { Authorization: `Bearer ${t}` } : {}),
      },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined,
    });
  } catch (e) {
    // `fetch` tira TypeError("Failed to fetch") cuando no hay red, cuando el
    // dominio no existe o cuando lo frena CORS. Ese texto no le dice NADA a
    // nadie: en un APK compilado contra una URL equivocada, la persona ve
    // "Failed to fetch" y la app parece rota sin motivo.
    //
    // Pasó de verdad: el valor por defecto de `BASE` es un dominio de ejemplo,
    // así que cualquier build sin `VITE_API_URL` sale apuntando a un servidor
    // que no existe. Con este error, la pantalla dice contra qué URL está
    // compilada la app y que esa URL no contesta — que es la única pista que
    // sirve para arreglarlo.
    throw new ErrorSinRed(BASE, e);
  }
  const texto = await res.text();
  return { res, datos: texto ? JSON.parse(texto) : null };
}

async function pedir(ruta, { metodo = "GET", cuerpo } = {}) {
  const t = token.leer();
  let { res, datos } = await crudo(ruta, metodo, cuerpo, t);

  // Un 401 suelto NO cierra la sesión de una. En el despliegue serverless una
  // instancia recién levantada puede no tener el perfil todavía y devolver
  // 401 con un token perfectamente válido; cerrar la sesión por eso es lo que
  // hacía que "se cierre sola". Se sondea /api/yo: si la sonda pasa, el 401
  // era un espasmo de una instancia — se reintenta una vez y listo. Sólo si
  // la sonda también da 401 la sesión está muerta de verdad.
  if (res.status === 401 && t && ruta !== "/yo") {
    try {
      const sonda = await crudo("/yo", "GET", undefined, t);
      if (sonda.res.ok) {
        ({ res, datos } = await crudo(ruta, metodo, cuerpo, t));
      }
    } catch {
      /* sin red: que caiga por el camino normal */
    }
  }

  if (!res.ok) {
    if (res.status === 401) {
      token.borrar();
      // Además de borrar el token hay que avisarle a la app. Antes sólo se
      // borraba: el estado seguía creyendo que había perfil, así que en vez
      // de volver al login cada pantalla se quedaba colgada en "Cargando…".
      window.dispatchEvent(new CustomEvent(SESION_CAIDA));
    }
    throw new ErrorApi(res.status, datos);
  }
  return datos;
}

export const SESION_CAIDA = "matcher:sesion-caida";

export const api = {
  salud: () => pedir("/salud"),
  catalogos: () => pedir("/catalogos"),
  planes: () => pedir("/planes"),

  registro: (datos) => pedir("/registro", { metodo: "POST", cuerpo: datos }),
  proveedoresLogin: () => pedir("/auth/proveedores"),
  // `destino` decide por dónde vuelve el proveedor: "web" a esta misma web,
  // "app" a un enlace profundo que el sistema enruta a la app instalada
  // (ver `loginNativo.js` y `matcher/oauth.py`).
  inicioLogin: (nombre, destino = "web") =>
    pedir(`/auth/${nombre}/inicio?destino=${encodeURIComponent(destino)}`),
  leerAlta: (token) => pedir(`/auth/alta/${token}`),
  completarAlta: (datos) => pedir("/auth/completar", { metodo: "POST", cuerpo: datos }),
  login: (email, clave) => pedir("/login", { metodo: "POST", cuerpo: { email, clave } }),
  logout: () => pedir("/logout", { metodo: "POST" }),
  yo: () => pedir("/yo"),
  editar: (cambio) => pedir("/yo", { metodo: "PATCH", cuerpo: cambio }),
  marcarDisponible: () => pedir("/yo/disponible", { metodo: "POST" }),
  apagarDisponible: () => pedir("/yo/disponible", { metodo: "DELETE" }),
  borrarCuenta: () => pedir("/yo", { metodo: "DELETE" }),

  subirFoto: (url, bytes) => pedir("/yo/fotos", { metodo: "POST", cuerpo: { url, bytes } }),
  subirVideo: (url, segundos, bytes) =>
    pedir("/yo/videos", { metodo: "POST", cuerpo: { url, segundos, bytes } }),
  borrarMedia: (id) => pedir(`/yo/medios/${id}`, { metodo: "DELETE" }),
  ordenarMedios: (ids) => pedir("/yo/medios/orden", { metodo: "POST", cuerpo: { ids } }),

  deck: (limite = 20) => pedir(`/deck?limite=${limite}`),
  radar: (radio_km) => pedir(`/radar?radio_km=${radio_km}`),
  ubicacion: (lat, lon) => pedir("/ubicacion", { metodo: "POST", cuerpo: { lat, lon } }),
  cruces: () => pedir("/cruces"),
  interactuar: (a_id, tipo) => pedir("/interacciones", { metodo: "POST", cuerpo: { a_id, tipo } }),
  rebobinar: () => pedir("/rebobinar", { metodo: "POST" }),
  likesRecibidos: () => pedir("/likes-recibidos"),
  ranking: (limite = 20) => pedir(`/ranking?limite=${limite}`),

  sugerenciasAuto: () => pedir("/automatch/sugerencias"),
  correrAuto: () => pedir("/automatch", { metodo: "POST" }),

  citaACiegas: () => pedir("/aciegas", { metodo: "POST" }),
  topDia: () => pedir("/top-dia"),
  disponibles: (limite = 60) => pedir(`/disponibles?limite=${limite}`),
  segundaVuelta: () => pedir("/segunda-vuelta"),
  repescar: (a_id) => pedir(`/segunda-vuelta/${a_id}`, { metodo: "POST" }),
  masLikeados: (alcance = "ciudad", limite = 200) =>
    pedir(`/mas-likeados?alcance=${alcance}&limite=${limite}`),
  boost: () => pedir("/boost"),
  activarBoost: () => pedir("/boost", { metodo: "POST" }),
  crushtime: () => pedir("/crushtime"),
  crushtimeRonda: () => pedir("/crushtime/ronda", { metodo: "POST" }),
  crushtimeAdivinar: (ronda, elegido) =>
    pedir("/crushtime/adivinar", { metodo: "POST", cuerpo: { ronda, elegido } }),
  matches: () => pedir("/matches"),
  mensajes: (id) => pedir(`/matches/${id}/mensajes`),
  enviar: (id, texto) => pedir(`/matches/${id}/mensajes`, { metodo: "POST", cuerpo: { texto } }),
  borrarMatch: (id) => pedir(`/matches/${id}`, { metodo: "DELETE" }),

  // Videollamada del match. El `enlace` viene en null hasta que la otra
  // persona acepta: no es que el cliente lo esconda, es que no lo recibe.
  videollamada: (matchId) => pedir(`/matches/${matchId}/videollamada`),
  proponerVideollamada: (matchId, proveedor, enlace = "", cuando = "") =>
    pedir(`/matches/${matchId}/videollamada`, {
      metodo: "POST",
      cuerpo: { proveedor, enlace, cuando },
    }),
  responderVideollamada: (id, acepta) =>
    pedir(`/videollamadas/${id}/responder`, { metodo: "POST", cuerpo: { acepta } }),
  cancelarVideollamada: (id) => pedir(`/videollamadas/${id}`, { metodo: "DELETE" }),
  reportar: (a_id, motivo, detalle = "") =>
    pedir("/reportes", { metodo: "POST", cuerpo: { a_id, motivo, detalle } }),

  checkout: (plan, periodo) => pedir("/pagos/checkout", { metodo: "POST", cuerpo: { plan, periodo } }),
  confirmarPago: (referencia) =>
    pedir("/pagos/confirmar", { metodo: "POST", cuerpo: { referencia } }),
  cancelarPlan: () => pedir("/pagos/cancelar", { metodo: "POST" }),
  historialPagos: () => pedir("/pagos"),
};

// Lee un archivo del selector como data-URI. La demo guarda las fotos así
// (no hay bucket de objetos todavía); cuando haya storage real, esto pasa a
// ser un PUT firmado y no cambia nada más de la app.
export function leerArchivo(archivo) {
  return new Promise((resolve, reject) => {
    const lector = new FileReader();
    lector.onload = () => resolve({ url: lector.result, bytes: archivo.size });
    lector.onerror = reject;
    lector.readAsDataURL(archivo);
  });
}

// Duración real del video, para poder rechazarlo antes de subirlo y no
// después de que el usuario esperó la carga entera.
export function duracionVideo(archivo) {
  return new Promise((resolve) => {
    const v = document.createElement("video");
    v.preload = "metadata";
    v.onloadedmetadata = () => {
      URL.revokeObjectURL(v.src);
      resolve(v.duration);
    };
    v.onerror = () => resolve(null);
    v.src = URL.createObjectURL(archivo);
  });
}
