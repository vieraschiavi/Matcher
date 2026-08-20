import { useEffect, useMemo, useRef, useState } from "react";
import { IcoCorazon, IcoCruz } from "../Iconos";
import { t } from "../i18n";

// Mapa de verdad: dónde está la gente que el radar encontró.
//
// Sin librería a propósito. Leaflet son ~145 KB y MapLibre ~800 KB, y de esto
// se usa exactamente una cosa: proyectar lat/lon a píxeles y pegar tiles en
// una grilla. La proyección Web Mercator son seis líneas y están abajo.
//
// Los tiles salen de un servidor configurable (VITE_TILES_URL). El default es
// el Voyager de Carto (cartografía de OpenStreetMap, servidor de Carto): no
// pide clave, tolera el tráfico de una app chica y dibuja las calles con
// nombre bien legibles. NO se usa tile.openstreetmap.org: su política de uso
// no cubre apps y bloquea el tráfico que no la sigue — se comprobó acá mismo,
// devolviendo un tile de "Access blocked" en vez del mapa. Para crecer en
// serio: MapTiler/Mapbox con clave propia.
//
// Si los tiles no cargan —sin red, un WebView que los bloquea, el servidor
// caído— NO se rompe la pantalla: se apaga la capa de tiles y quedan la
// grilla, los anillos de distancia y los puntos, que es el radar de siempre.
// Un mapa gris con los puntos encima sigue siendo útil; un cuadro en blanco no.

const TAM_TILE = 256;
const URL_TILES =
  import.meta.env.VITE_TILES_URL ||
  "https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png";
const ATRIBUCION = import.meta.env.VITE_TILES_ATRIBUCION || "© OpenStreetMap · © CARTO";

// A partir de acá los tiles de OSM dibujan la trama de calles con nombre.
// Es el zoom al que salta el mapa cuando tocás un cruce: "nos cruzamos en
// tal esquina" sólo se entiende viendo la esquina.
const ZOOM_CALLES = 16;
const ZOOM_MAX = 18;
const ZOOM_MIN = 3;

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
  return Math.max(ZOOM_MIN, Math.min(17, Math.floor(z)));
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
  onLike,
  alto = 420,
}) {
  const caja = useRef(null);
  const [ancho, setAncho] = useState(0);
  const [sinTiles, setSinTiles] = useState(false);
  // Zoom absoluto elegido a mano (null = automático según el radio) y centro
  // enfocado (null = el usuario). Juntos permiten las dos cosas nuevas:
  // acercarse hasta ver las calles, y saltar a la esquina de un cruce.
  const [zoomManual, setZoomManual] = useState(null);
  const [foco, setFoco] = useState(null);
  // La cara agrandada: tocar el pin de alguien ya seleccionado (o su foto en
  // el globo) abre la foto en grande, con el like a mano.
  const [ampliada, setAmpliada] = useState(null);
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

  // Cambiar de vista (zoom o foco) le da otra oportunidad a los tiles: el
  // "sin conexión" de recién pudo ser un hipo de red, y los tiles del nivel
  // nuevo son otros archivos.
  useEffect(() => {
    setSinTiles(false);
  }, [zoomManual, foco]);

  const zoomAuto = centro && ancho ? zoomPara(radioKm, centro.lat, ancho) : 13;
  const z = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, zoomManual ?? zoomAuto));
  const centroVista = foco || centro;

  const vista = useMemo(() => {
    if (!centroVista || !ancho) return null;
    const cx = xDeLon(centroVista.lon, z) * TAM_TILE;
    const cy = yDeLat(centroVista.lat, z) * TAM_TILE;
    // Esquina superior izquierda del viewport, en píxeles de mundo.
    const ox = cx - ancho / 2;
    const oy = cy - alto / 2;
    const aPixel = (lat, lon) => ({
      x: xDeLon(lon, z) * TAM_TILE - ox,
      y: yDeLat(lat, z) * TAM_TILE - oy,
    });
    const pxPorMetro = 1 / metrosPorPixel(centroVista.lat, z);
    return { z, ox, oy, aPixel, pxPorMetro };
  }, [centroVista, ancho, alto, z]);

  const tiles = useMemo(() => {
    if (!vista || sinTiles) return [];
    const { z: zv, ox, oy } = vista;
    const max = 2 ** zv;
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
          clave: `${zv}/${x}/${y}`,
          url: URL_TILES.replace("{z}", zv).replace("{x}", xn).replace("{y}", y),
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
  const hayVistaManual = zoomManual != null || foco != null;

  // Tocar la cara de alguien: la primera vez lo selecciona (globo con el
  // like); tocarla de nuevo la agranda de verdad. Es el gesto que pidió el
  // dueño: "al clickear la cara se agrande".
  const tocarPin = (p) => {
    if (seleccion?.id === p.id) setAmpliada(p);
    else onElegir?.(p);
  };

  // Tocar un cruce salta a esa esquina con zoom de calles: "nos cruzamos acá"
  // recién significa algo cuando se ve el nombre de la calle.
  const irAlCruce = (punto) => {
    setFoco({ lat: punto.lat, lon: punto.lon });
    setZoomManual(ZOOM_CALLES);
  };

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
            // Antes un solo tile fallido apagaba la capa entera, y con una
            // red que resetea conexiones de a ratos eso mataba el mapa por un
            // hipo. Ahora sólo se apaga si NINGUNO cargó: un agujero oscuro
            // en un mapa vivo molesta menos que perder el mapa entero.
            onError={() => {
              if (!algunoCargo.current) setSinTiles(true);
            }}
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

          {/* Dónde te cruzaste con alguien. Tocarlo acerca el mapa hasta la
              esquina: el punto pasa de "por ahí" a una calle con nombre. */}
          {cruces
            .filter((c) => c.punto)
            .map((c) => {
              const p = vista.aPixel(c.punto.lat, c.punto.lon);
              return (
                <g
                  key={`x-${c.id}`}
                  className="mapa-cruce-zona"
                  onClick={() => irAlCruce(c.punto)}
                >
                  <circle cx={p.x} cy={p.y} r={16} className="mapa-cruce-toque" />
                  <circle cx={p.x} cy={p.y} r={9} className="mapa-cruce" />
                </g>
              );
            })}

          {/* El círculo de privacidad alrededor tuyo: hace visible que la
              posición está redondeada, en vez de prometer un punto exacto. */}
          <circle cx={yo.x} cy={yo.y} r={precisionM * vista.pxPorMetro} className="mapa-privacidad" />
          <circle cx={yo.x} cy={yo.y} r={7} className="mapa-yo" />
        </svg>
      )}

      {/* Las caras van en HTML y no en el SVG: así son botones de verdad,
          con foco, título y área táctil, sin inventar accesibilidad a mano.

          Las posiciones vienen redondeadas a la celda de privacidad (~500 m),
          así que DOS personas de la misma cuadra caen en el MISMO punto y una
          tapa a la otra — la de abajo quedaba imposible de tocar (lo atrapó
          el test de click). Las apiladas se despliegan en un anillo alrededor
          del punto: se ven todas y se tocan todas. */}
      {vista &&
        (() => {
          const visibles = personas
            .filter((p) => p.lat_aprox != null)
            .map((p) => ({ p, pos: vista.aPixel(p.lat_aprox, p.lon_aprox) }))
            .filter(
              ({ pos }) =>
                pos.x > -30 && pos.x < ancho + 30 && pos.y > -30 && pos.y < alto + 30
            );
          const grupos = new Map();
          for (const v of visibles) {
            const clave = `${Math.round(v.pos.x / 26)}:${Math.round(v.pos.y / 26)}`;
            if (!grupos.has(clave)) grupos.set(clave, []);
            grupos.get(clave).push(v);
          }
          const salida = [];
          for (const grupo of grupos.values()) {
            grupo.forEach(({ p, pos }, i) => {
              // El primero queda en el punto; el resto, en anillo de a 20 px.
              const r = grupo.length > 1 ? 20 : 0;
              const ang = (i / grupo.length) * Math.PI * 2 - Math.PI / 2;
              salida.push(
                <button
                  key={p.id}
                  className={`mapa-pin ${seleccion?.id === p.id ? "on" : ""} ${p.cruces > 0 ? "cruzado" : ""}`}
                  style={{
                    left: pos.x + (grupo.length > 1 ? Math.cos(ang) * r : 0),
                    top: pos.y + (grupo.length > 1 ? Math.sin(ang) * r : 0),
                  }}
                  onClick={() => tocarPin(p)}
                  title={`${p.nombre} · ${p.distancia_km} km`}
                  aria-label={`${p.nombre}, a ${p.distancia_km} kilómetros`}
                >
                  <img src={p.fotos?.[0]?.url} alt="" draggable="false" />
                </button>
              );
            });
          }
          return salida;
        })()}

      {/* Tocar un pin abre esta tarjeta con el botón de like; tocar la foto
          la agranda a pantalla completa. */}
      {vista && seleccion && (() => {
        const pos = vista.aPixel(seleccion.lat_aprox, seleccion.lon_aprox);
        const izq = Math.min(Math.max(pos.x - 86, 6), Math.max(ancho - 178, 6));
        const arriba = pos.y > alto / 2 ? pos.y - 132 : pos.y + 26;
        return (
          <div className="mapa-globo" style={{ left: izq, top: Math.max(6, arriba) }}>
            <button
              className="mapa-globo-foto"
              onClick={() => setAmpliada(seleccion)}
              aria-label={`Ver la foto de ${seleccion.nombre} en grande`}
            >
              <img src={seleccion.fotos?.[0]?.url} alt="" />
            </button>
            <div className="mapa-globo-datos">
              <b>{seleccion.nombre}, {seleccion.edad}</b>
              <span>{seleccion.distancia_km} km · {seleccion.compatibilidad}%</span>
            </div>
            <button
              className="mapa-globo-like"
              onClick={() => onLike?.(seleccion.id)}
              aria-label={`Me gusta ${seleccion.nombre}`}
            >
              <IcoCorazon tam={18} relleno />
            </button>
          </div>
        );
      })()}

      {/* Zoom manual. El automático encuadra el radio; estos botones dejan
          bajar hasta el nivel de calle (o subir a ver la ciudad entera). */}
      <div className="mapa-controles">
        <button
          onClick={() => setZoomManual(Math.min(ZOOM_MAX, z + 1))}
          aria-label={t("Acercar el mapa")}
          disabled={z >= ZOOM_MAX}
        >
          +
        </button>
        <button
          onClick={() => setZoomManual(Math.max(ZOOM_MIN, z - 1))}
          aria-label={t("Alejar el mapa")}
          disabled={z <= ZOOM_MIN}
        >
          −
        </button>
        {hayVistaManual && (
          <button
            className="volver"
            onClick={() => {
              setZoomManual(null);
              setFoco(null);
            }}
            aria-label={t("Volver a la vista del radar")}
            title={t("Volver a la vista del radar")}
          >
            ⌖
          </button>
        )}
      </div>

      {/* La cara en grande. Va sobre el mapa entero, con el like a mano:
          agrandar para mirar y tener que volver atrás para likear sería
          hacerle repetir el camino. */}
      {ampliada && (
        <div className="mapa-lightbox" onClick={() => setAmpliada(null)}>
          <div className="mapa-lightbox-caja" onClick={(e) => e.stopPropagation()}>
            <img src={ampliada.fotos?.[0]?.url} alt={`Foto de ${ampliada.nombre}`} />
            <div className="mapa-lightbox-pie">
              <div>
                <b>{ampliada.nombre}, {ampliada.edad}</b>
                <span>
                  {ampliada.distancia_km} km
                  {ampliada.cruces > 0 && ` · ${t("se cruzaron")} ${ampliada.cruces}×`}
                  {ampliada.compatibilidad != null && ` · ${ampliada.compatibilidad}%`}
                </span>
              </div>
              <button
                className="mapa-globo-like grande"
                onClick={() => {
                  onLike?.(ampliada.id);
                  setAmpliada(null);
                }}
                aria-label={`Me gusta ${ampliada.nombre}`}
              >
                <IcoCorazon tam={22} relleno />
              </button>
            </div>
            <button
              className="mapa-lightbox-cerrar"
              onClick={() => setAmpliada(null)}
              aria-label={t("Cerrar")}
            >
              <IcoCruz tam={18} />
            </button>
          </div>
        </div>
      )}

      <div className="mapa-pie">
        {sinTiles ? t("Mapa sin conexión · posiciones reales") : ATRIBUCION}
      </div>
    </div>
  );
}
