import { useEffect, useMemo, useRef, useState } from "react";
import { t } from "../i18n";

// Mapa de verdad: dónde está la gente que el radar encontró.
//
// Sin librería a propósito. Leaflet son ~145 KB y MapLibre ~800 KB, y de esto
// se usa exactamente una cosa: proyectar lat/lon a píxeles y pegar tiles en
// una grilla. La proyección Web Mercator son seis líneas y están abajo.
//
// Los tiles salen de un servidor configurable (VITE_TILES_URL). El default es
// OpenStreetMap, que no pide clave y alcanza para la demo; para producción de
// verdad hay que poner un proveedor propio (MapTiler, Mapbox, un caché de
// tiles) porque la política de uso de OSM no cubre el tráfico de una app.
//
// Si los tiles no cargan —sin red, un WebView que los bloquea, el servidor
// caído— NO se rompe la pantalla: se apaga la capa de tiles y quedan la
// grilla, los anillos de distancia y los puntos, que es el radar de siempre.
// Un mapa gris con los puntos encima sigue siendo útil; un cuadro en blanco no.

const TAM_TILE = 256;
const URL_TILES =
  import.meta.env.VITE_TILES_URL || "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const ATRIBUCION = import.meta.env.VITE_TILES_ATRIBUCION || "© OpenStreetMap";

// --- Web Mercator -----------------------------------------------------------
const xDeLon = (lon, z) => ((lon + 180) / 360) * 2 ** z;
const yDeLat = (lat, z) => {
  const r = (Math.max(-85.05, Math.min(85.05, lat)) * Math.PI) / 180;
  return ((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * 2 ** z;
};
// Metros por píxel: de acá sale el zoom que hace entrar el radio pedido.
const metrosPorPixel = (lat, z) =>
  (156543.03392 * Math.cos((lat * Math.PI) / 180)) / 2 ** z;

function zoomPara(radioKm, lat, anchoPx) {
  if (!anchoPx) return 13;
  const objetivo = (radioKm * 1000 * 2) / (anchoPx * 0.92); // metros por píxel deseados
  const z = Math.log2((156543.03392 * Math.cos((lat * Math.PI) / 180)) / objetivo);
  return Math.max(3, Math.min(17, Math.floor(z)));
}

export default function Mapa({
  centro,
  personas = [],
  cruces = [],
  radioKm = 15,
  precisionM = 500,
  anillosKm = [],
  seleccion,
  onElegir,
  alto = 420,
}) {
  const caja = useRef(null);
  const [ancho, setAncho] = useState(0);
  const [sinTiles, setSinTiles] = useState(false);
  const algunoCargo = useRef(false);

  // Un tile puede no fallar nunca: queda colgado. Pasa con una red lenta, con
  // un portal cautivo y con cualquier proxy que se trague el pedido sin
  // contestar. `onError` no dispara, así que sin este plazo el mapa se queda
  // vacío mostrando "© OpenStreetMap" al pie — un cartel que miente sobre un
  // cuadro en blanco. Si a los 6 segundos no cargó ni uno, se pasa al modo sin
  // conexión, que dibuja los anillos y las caras igual.
  useEffect(() => {
    const t = setTimeout(() => {
      if (!algunoCargo.current) setSinTiles(true);
    }, 6000);
    return () => clearTimeout(t);
  }, []);

  // El ancho se mide del DOM: el zoom depende de cuántos píxeles hay para
  // mostrar el radio, y en el teléfono no es el mismo que en escritorio.
  useEffect(() => {
    if (!caja.current) return;
    const medir = () => setAncho(caja.current?.clientWidth || 0);
    medir();
    const ro = new ResizeObserver(medir);
    ro.observe(caja.current);
    return () => ro.disconnect();
  }, []);

  const vista = useMemo(() => {
    if (!centro || !ancho) return null;
    const z = zoomPara(radioKm, centro.lat, ancho);
    const cx = xDeLon(centro.lon, z) * TAM_TILE;
    const cy = yDeLat(centro.lat, z) * TAM_TILE;
    // Esquina superior izquierda del viewport, en píxeles de mundo.
    const ox = cx - ancho / 2;
    const oy = cy - alto / 2;
    const aPixel = (lat, lon) => ({
      x: xDeLon(lon, z) * TAM_TILE - ox,
      y: yDeLat(lat, z) * TAM_TILE - oy,
    });
    const pxPorMetro = 1 / metrosPorPixel(centro.lat, z);
    return { z, ox, oy, aPixel, pxPorMetro };
  }, [centro, ancho, alto, radioKm]);

  const tiles = useMemo(() => {
    if (!vista || sinTiles) return [];
    const { z, ox, oy } = vista;
    const max = 2 ** z;
    const desdeX = Math.floor(ox / TAM_TILE);
    const hastaX = Math.floor((ox + ancho) / TAM_TILE);
    const desdeY = Math.floor(oy / TAM_TILE);
    const hastaY = Math.floor((oy + alto) / TAM_TILE);
    const salida = [];
    for (let x = desdeX; x <= hastaX; x++) {
      for (let y = desdeY; y <= hastaY; y++) {
        if (y < 0 || y >= max) continue;
        const xn = ((x % max) + max) % max; // el mundo da la vuelta en longitud
        salida.push({
          clave: `${z}/${x}/${y}`,
          url: URL_TILES.replace("{z}", z).replace("{x}", xn).replace("{y}", y),
          izq: x * TAM_TILE - ox,
          arr: y * TAM_TILE - oy,
        });
      }
    }
    return salida;
  }, [vista, ancho, alto, sinTiles]);

  if (!centro) {
    return (
      <div className="mapa-vacio" style={{ height: alto }}>
        {t("Todavía no sabemos dónde estás.")}
      </div>
    );
  }

  const yo = vista?.aPixel(centro.lat, centro.lon);

  return (
    <div className="mapa" ref={caja} style={{ height: alto }}>
      <div className="mapa-tiles" aria-hidden="true">
        {tiles.map((t) => (
          <img
            key={t.clave}
            src={t.url}
            alt=""
            draggable="false"
            style={{ left: t.izq, top: t.arr }}
            onLoad={() => {
              algunoCargo.current = true;
            }}
            // Un tile que falla apaga la capa entera: mejor el mapa gris
            // parejo que un damero con agujeros blancos.
            onError={() => setSinTiles(true)}
          />
        ))}
      </div>

      {/* Anillos de distancia. Se mantienen sobre el mapa: son la referencia
          que dice "esto está a 2 km", que en un mapa sin escala se pierde. */}
      {vista && (
        <svg className="mapa-capa" viewBox={`0 0 ${ancho} ${alto}`}>
          {anillosKm
            .filter((km) => km <= radioKm)
            .map((km) => (
              <g key={km}>
                <circle cx={yo.x} cy={yo.y} r={km * 1000 * vista.pxPorMetro} className="mapa-anillo" />
                <text x={yo.x + 4} y={yo.y - km * 1000 * vista.pxPorMetro + 12} className="mapa-etiqueta">
                  {km} km
                </text>
              </g>
            ))}

          {/* Dónde te cruzaste con alguien. Es el dato que el usuario pidió
              ver en el mapa: no sólo quién anda cerca ahora, sino el lugar
              donde efectivamente se cruzaron. */}
          {cruces
            .filter((c) => c.punto)
            .map((c) => {
              const p = vista.aPixel(c.punto.lat, c.punto.lon);
              return <circle key={`x-${c.id}`} cx={p.x} cy={p.y} r={9} className="mapa-cruce" />;
            })}

          {/* El círculo de privacidad alrededor tuyo: hace visible que la
              posición está redondeada, en vez de prometer un punto exacto. */}
          <circle cx={yo.x} cy={yo.y} r={precisionM * vista.pxPorMetro} className="mapa-privacidad" />
          <circle cx={yo.x} cy={yo.y} r={7} className="mapa-yo" />
        </svg>
      )}

      {/* Las caras van en HTML y no en el SVG: así son botones de verdad,
          con foco, título y área táctil, sin inventar accesibilidad a mano. */}
      {vista &&
        personas
          .filter((p) => p.lat_aprox != null)
          .map((p) => {
            const pos = vista.aPixel(p.lat_aprox, p.lon_aprox);
            if (pos.x < -30 || pos.x > ancho + 30 || pos.y < -30 || pos.y > alto + 30) return null;
            return (
              <button
                key={p.id}
                className={`mapa-pin ${seleccion?.id === p.id ? "on" : ""} ${p.cruces > 0 ? "cruzado" : ""}`}
                style={{ left: pos.x, top: pos.y }}
                onClick={() => onElegir?.(p)}
                title={`${p.nombre} · ${p.distancia_km} km`}
                aria-label={`${p.nombre}, a ${p.distancia_km} kilómetros`}
              >
                <img src={p.fotos?.[0]?.url} alt="" draggable="false" />
              </button>
            );
          })}

      <div className="mapa-pie">
        {sinTiles ? t("Mapa sin conexión · posiciones reales") : ATRIBUCION}
      </div>
    </div>
  );
}
