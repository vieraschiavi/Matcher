import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ErrorApi } from "../api";
import { IcoCorazon, IcoPin, IcoRayo, IcoVerificado } from "../Iconos";

// Radar en SVG, no un mapa de verdad: no hay tiles sin salir a internet desde
// el APK y sin clave de un proveedor de mapas. Lo que sí importa —cuánta
// gente hay cerca, en qué dirección, qué tan lejos— se lee igual de bien en
// un radar que en un mapa, y es la forma en que ya lo hace la categoría
// (es literalmente cómo arrancó Happn).
const LADO = 480;
const CENTRO = LADO / 2;
const RADIO_MAX = CENTRO - 34;

function posicionEnRadar(distanciaKm, rumbo, radioKm) {
  const r = Math.min((distanciaKm / radioKm) * RADIO_MAX, RADIO_MAX);
  const rad = (rumbo - 90) * (Math.PI / 180); // 0° = arriba (norte)
  return { x: CENTRO + r * Math.cos(rad), y: CENTRO + r * Math.sin(rad) };
}

export default function Radar() {
  const navegar = useNavigate();
  const [datos, setDatos] = useState(null);
  const [cruces, setCruces] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [radioKm, setRadioKm] = useState(15);
  const [seleccion, setSeleccion] = useState(null);
  const [permiso, setPermiso] = useState("pendiente"); // pendiente | ok | negado
  const [fallo, setFallo] = useState("");
  const [pulso, setPulso] = useState(0);
  const intervalo = useRef(null);

  // El `finally` apaga "Ubicándote…" pase lo que pase. Con el `setCargando`
  // sólo en el camino feliz, un pedido fallido dejaba el radar en
  // "Ubicándote…" para siempre, sin radar, sin lista y sin ningún error a la
  // vista: la pantalla parecía rota.
  const cargarRadar = async (radio) => {
    try {
      setDatos(await api.radar(radio));
      setFallo("");
    } catch (e) {
      setFallo(e.message);
    } finally {
      setCargando(false);
    }
  };

  // Los cruces se muestran EN esta pantalla, no detrás de un botón que lleva a
  // otra: es la mitad de lo que la gente viene a ver acá.
  useEffect(() => {
    api.cruces().then(setCruces).catch(() => setCruces(null));
  }, [pulso]);

  // Pide GPS una vez al entrar y cada 5 minutos mientras la pantalla está
  // abierta: alcanza para que el radar y los cruces tengan sentido, sin
  // vaciar la batería con un ping cada pocos segundos.
  useEffect(() => {
    const pedirUbicacion = () => {
      if (!navigator.geolocation) {
        setPermiso("negado");
        cargarRadar(radioKm);
        return;
      }
      navigator.geolocation.getCurrentPosition(
        async (pos) => {
          setPermiso("ok");
          try {
            const r = await api.ubicacion(pos.coords.latitude, pos.coords.longitude);
            if (r.cruces_nuevos?.length) setPulso((p) => p + 1);
          } catch {
            /* un ping fallido no es motivo para romper la pantalla */
          }
          cargarRadar(radioKm);
        },
        () => {
          setPermiso("negado");
          cargarRadar(radioKm); // igual sirve: cae al centro de tu ciudad
        },
        { enableHighAccuracy: false, timeout: 8000 }
      );
    };
    pedirUbicacion();
    intervalo.current = setInterval(pedirUbicacion, 5 * 60 * 1000);
    return () => clearInterval(intervalo.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    cargarRadar(radioKm);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [radioKm]);

  const like = async (id) => {
    try {
      const r = await api.interactuar(id, "like");
      if (r.match) navegar(`/matches/${r.match_id}`);
      else cargarRadar(radioKm);
    } catch (e) {
      if (e instanceof ErrorApi && e.sinCupo) navegar("/planes");
    }
  };

  const anillos = datos?.anillos_km || [2, 5, 15];
  const radioMostrado = anillos[anillos.length - 1] || radioKm;

  return (
    <>
      <h1 className="page-title">Radar</h1>
      <p className="page-sub">
        Quién hay cerca, ahora. Las posiciones están redondeadas a{" "}
        {datos?.precision_m || 500} m: nadie ve tu ubicación exacta, y vos no ves la de nadie.
        {pulso > 0 && " Detectamos un cruce nuevo — mirá abajo."}
      </p>

      {fallo && (
        <div className="aviso aviso-error" style={{ marginBottom: 16 }}>
          No se pudo cargar el radar: {fallo}
        </div>
      )}

      {permiso === "negado" && (
        <div className="aviso aviso-info" style={{ marginBottom: 16 }}>
          No pudimos usar tu ubicación exacta; el radar se centra en tu ciudad. Activá la
          ubicación del navegador para ver quién está cerca de verdad.
        </div>
      )}

      {/* Mismo caso que el chat: la grilla va en CSS para que colapse a una
          columna en el teléfono. Con el style en línea el radar quedaba
          encajado en una columna angosta, del tamaño de una moneda. */}
      <div className="deck-zona zona-radar">
        <div>
          <div className="panel" style={{ padding: 16 }}>
            <label className="campo" style={{ marginBottom: 12 }}>
              <span>Radio: {radioKm} km</span>
              <input
                type="range"
                min={1}
                max={100}
                value={radioKm}
                onChange={(e) => setRadioKm(Number(e.target.value))}
              />
            </label>

            {cargando && <p style={{ color: "var(--muted)" }}>Ubicándote…</p>}

            {!cargando && (
              <svg viewBox={`0 0 ${LADO} ${LADO}`} className="radar-svg" role="img" aria-label="Radar de gente cerca">
                <circle cx={CENTRO} cy={CENTRO} r={RADIO_MAX} className="radar-fondo" />
                {anillos.map((km, i) => (
                  <g key={km}>
                    <circle
                      cx={CENTRO}
                      cy={CENTRO}
                      r={(km / radioMostrado) * RADIO_MAX}
                      className="radar-anillo"
                    />
                    <text
                      x={CENTRO + 4}
                      y={CENTRO - (km / radioMostrado) * RADIO_MAX + 12}
                      className="radar-etiqueta"
                    >
                      {km} km
                    </text>
                  </g>
                ))}
                <line x1={CENTRO} y1={16} x2={CENTRO} y2={LADO - 16} className="radar-cruz" />
                <line x1={16} y1={CENTRO} x2={LADO - 16} y2={CENTRO} className="radar-cruz" />

                {datos?.personas.map((p) => {
                  const { x, y } = posicionEnRadar(p.distancia_km, p.rumbo, radioMostrado);
                  return (
                    <g
                      key={p.id}
                      transform={`translate(${x} ${y})`}
                      className="radar-punto"
                      onClick={() => setSeleccion(p)}
                    >
                      {p.cruces > 0 && <circle r={17} className="radar-punto-cruce" />}
                      <clipPath id={`clip-${p.id}`}>
                        <circle r={14} />
                      </clipPath>
                      <image
                        href={p.fotos?.[0]?.url}
                        x={-14}
                        y={-14}
                        width={28}
                        height={28}
                        clipPath={`url(#clip-${p.id})`}
                        preserveAspectRatio="xMidYMin slice"
                      />
                      <circle r={14} className="radar-punto-borde" />
                    </g>
                  );
                })}

                <circle cx={CENTRO} cy={CENTRO} r={7} className="radar-yo" />
              </svg>
            )}

            {!cargando && datos?.personas.length === 0 && (
              <p style={{ color: "var(--muted)", textAlign: "center" }}>
                Nadie en este radio ahora mismo. Probá agrandarlo.
              </p>
            )}
          </div>
        </div>

        <div className="grid">
          <div className="panel">
            <h3>Por distancia</h3>
            {datos?.por_anillo?.map((a) => (
              <div key={a.hasta_km} style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", fontSize: 13.5 }}>
                <span style={{ color: "var(--muted)" }}>
                  {a.desde_km} – {a.hasta_km} km
                </span>
                <b>{a.personas}</b>
              </div>
            ))}
          </div>

          {seleccion && (
            <div className="panel">
              <h3>{seleccion.nombre}</h3>
              <img
                src={seleccion.fotos?.[0]?.url}
                alt=""
                style={{ width: "100%", aspectRatio: "4/5", objectFit: "cover", borderRadius: 12, marginBottom: 10 }}
              />
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
                <span className="insignia insignia-comp">{seleccion.compatibilidad}%</span>
                <span className="insignia insignia-sint">{seleccion.distancia_km} km</span>
                {seleccion.cruces > 0 && (
                  <span className="insignia insignia-oro">Se cruzaron {seleccion.cruces}x</span>
                )}
              </div>
              <button className="btn btn-primario btn-bloque" onClick={() => like(seleccion.id)}>
                ♥ Like
              </button>
            </div>
          )}

          <div className="panel">
            <h3>
              Te cruzaste con{" "}
              {cruces?.resumen?.personas > 0 && (
                <span className="insignia insignia-auto">{cruces.resumen.personas}</span>
              )}
            </h3>
            <p style={{ color: "var(--muted)", fontSize: 12.5, marginTop: 0 }}>
              Gente con la que te cruzaste de verdad, no sólo que está cerca ahora.
              {cruces?.resumen?.cruces_totales > 0 &&
                ` ${cruces.resumen.cruces_totales} cruces en total.`}
            </p>
            {cruces?.personas?.length === 0 && (
              <p style={{ color: "var(--faint)", fontSize: 13 }}>
                Todavía ninguno. Se van sumando solos mientras usás la app.
              </p>
            )}
            <div className="lista-gente">
              {cruces?.personas?.map((p) => (
                <FichaGente key={p.id} p={p} onLike={() => like(p.id)} cruces={p.veces} />
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Lista de quién hay cerca, con la cara. El radar solo, con puntitos,
          no alcanza: la gente quiere ver a quién tiene al lado. */}
      <h2 className="page-title" style={{ marginTop: 26, fontSize: 18 }}>
        Cerca tuyo ahora {datos?.personas?.length > 0 && `(${datos.personas.length})`}
      </h2>
      <div className="lista-gente">
        {datos?.personas?.map((p) => (
          <FichaGente key={p.id} p={p} onLike={() => like(p.id)} cruces={p.cruces} />
        ))}
      </div>
      {!cargando && datos?.personas?.length === 0 && (
        <p style={{ color: "var(--muted)" }}>
          Nadie en {radioKm} km. Agrandá el radio con el control de arriba.
        </p>
      )}
    </>
  );
}

// Ficha de una persona: foto grande, distancia y cruces. Es la unidad que se
// repite en "cerca tuyo" y en "te cruzaste con".
function FichaGente({ p, onLike, cruces = 0 }) {
  return (
    <article className="ficha-gente">
      <img src={p.fotos?.[0]?.url} alt={`Foto de ${p.nombre}`} />
      <div className="ficha-velo" />
      <div className="ficha-datos">
        <b>
          {p.nombre} <span>{p.edad}</span>
        </b>
        <div className="ficha-linea">
          {p.distancia_km != null && (
            <span>
              <IcoPin tam={13} /> {p.distancia_km} km
            </span>
          )}
          {cruces > 0 && (
            <span className="ficha-cruce">
              <IcoRayo tam={13} /> {cruces}x
            </span>
          )}
        </div>
        <div className="ficha-insignias">
          <span className="insignia insignia-comp">{p.compatibilidad}%</span>
          {p.verificado && (
            <span className="verif-sello" title="Verificado">
              <IcoVerificado tam={16} />
            </span>
          )}
        </div>
      </div>
      <button className="ficha-like" onClick={onLike} aria-label={`Me gusta ${p.nombre}`}>
        <IcoCorazon tam={19} relleno />
      </button>
    </article>
  );
}
