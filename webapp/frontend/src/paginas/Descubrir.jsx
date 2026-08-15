import { useCallback, useEffect, useRef, useState } from "react";
import { t } from "../i18n";
import { useNavigate } from "react-router-dom";
import { api, ErrorApi } from "../api";
import { useApp } from "../estado";
import { soloPermitidos } from "../filtroCliente";
import {
  IcoCorazon,
  IcoCruz,
  IcoDeshacer,
  IcoDiamante,
  IcoEstrella,
  IcoPelota,
  IcoPin,
  IcoRegla,
  IcoVerificado,
  IcoVoto,
} from "../Iconos";

const MOTIVOS_VACIO = {
  genero: "por el género que buscás",
  genero_inverso: "porque no coinciden con lo que buscan",
  edad: "por el rango de edad",
  edad_inversa: "porque no entrás en el rango que piden",
  altura: "por el rango de altura",
  politica: "por el filtro de postura política",
  equipo: "por el filtro de equipo de fútbol",
  pais: "porque están fuera de tu país",
  distancia: "porque están más lejos que tu radio",
  verificado: "porque no están verificados",
  visto: "porque ya los viste",
  incompleto: "porque no tienen foto",
  inactivo: "porque están desactivados",
};

// Umbral de arrastre para que cuente como decisión. 110 px es lo que se siente
// natural en un pulgar; con menos, el scroll vertical dispara likes sin querer.
const UMBRAL_X = 110;
const UMBRAL_Y = 130;

function Carta({ tarjeta, fondo, arrastre, onFoto }) {
  const [i, setI] = useState(0);
  const piezas = [...(tarjeta.fotos || []), ...(tarjeta.videos || [])];
  const actual = piezas[Math.min(i, piezas.length - 1)];

  useEffect(() => setI(0), [tarjeta.id]);

  const mover = (paso, e) => {
    e.stopPropagation();
    const siguiente = Math.min(Math.max(i + paso, 0), piezas.length - 1);
    setI(siguiente);
    onFoto?.(siguiente);
  };

  const estilo = fondo
    ? undefined
    : {
        transform: `translate(${arrastre.x}px, ${arrastre.y}px) rotate(${arrastre.x * 0.05}deg)`,
        transition: arrastre.soltando ? "transform .28s ease" : "none",
      };

  return (
    <article className={`carta ${fondo ? "fondo" : ""}`} style={estilo}>
      {piezas.length > 1 && (
        <div className="carta-pasos">
          {piezas.map((_, k) => (
            <i key={k} className={k === i ? "on" : ""} />
          ))}
        </div>
      )}
      {!fondo && piezas.length > 1 && (
        <>
          <div className="carta-toque izq" onPointerDown={(e) => mover(-1, e)} />
          <div className="carta-toque der" onPointerDown={(e) => mover(1, e)} />
        </>
      )}

      {actual?.tipo === "video" ? (
        <video className="foto" src={actual.url} muted loop autoPlay playsInline />
      ) : (
        <img className="foto" src={actual?.url} alt={`Foto de ${tarjeta.nombre}`} draggable="false" />
      )}
      <div className="carta-velo" />

      {!fondo && arrastre.x > 45 && <div className="sello like">Like</div>}
      {!fondo && arrastre.x < -45 && <div className="sello nope">Nope</div>}
      {!fondo && arrastre.y < -60 && <div className="sello fan">★ Superfan</div>}

      <div className="carta-datos">
        <div className="carta-nombre">
          {tarjeta.nombre} <span className="edad">{tarjeta.edad}</span>
          {tarjeta.verificado && (
            <span className="verif-sello" title="Perfil verificado">
              <IcoVerificado tam={19} />
            </span>
          )}
        </div>
        <div className="carta-linea">
          {tarjeta.distancia_km != null && (
            <span>
              <IcoPin tam={14} /> {tarjeta.distancia_km} km
            </span>
          )}
          <span>
            <IcoRegla tam={14} /> {tarjeta.altura_cm} cm
          </span>
          {tarjeta.equipo && (
            <span>
              <IcoPelota tam={14} /> {tarjeta.equipo}
            </span>
          )}
          <span>
            <IcoVoto tam={14} /> {tarjeta.politica}
          </span>
        </div>
        {tarjeta.bio && <div className="carta-bio">{tarjeta.bio}</div>}
        <div className="carta-insignias">
          <span className="insignia insignia-comp">
            <b>{tarjeta.compatibilidad}%</b> compatibles
          </span>
          {tarjeta.es_premium && (
            <span className="insignia insignia-oro">
              <IcoDiamante tam={12} /> Premium
            </span>
          )}
          {tarjeta.sintetico && <span className="insignia insignia-sint">Perfil sintético</span>}
        </div>
      </div>
    </article>
  );
}

export default function Descubrir() {
  const { cupos, setCupos, perfil } = useApp();
  const navegar = useNavigate();
  // En un ref y no en las deps de `cargar`: cada `refrescar()` cambia la
  // identidad del objeto perfil y metería una recarga del deck que resetea
  // la pila de tarjetas a mitad del swipeo.
  const perfilRef = useRef(perfil);
  perfilRef.current = perfil;
  const [tarjetas, setTarjetas] = useState([]);
  const [diagnostico, setDiagnostico] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [match, setMatch] = useState(null);
  const [muro, setMuro] = useState(null);
  const [arrastre, setArrastre] = useState({ x: 0, y: 0, soltando: false });
  const inicio = useRef(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const r = await api.deck(20);
      // Última línea de defensa del filtro duro: en serverless el deck puede
      // venir de una instancia que aún no vio tus preferencias nuevas.
      const limpias = soloPermitidos(perfilRef.current?.preferencias, r.tarjetas);
      setTarjetas(limpias);
      // Precargar las fotos de las próximas tarjetas: el swipe se siente
      // instantáneo en vez de mostrar un gris mientras baja la imagen.
      limpias.slice(0, 4).forEach((tar) =>
        tar.fotos?.slice(0, 1).forEach((f) => { new Image().src = f.url; })
      );
      setDiagnostico(r.diagnostico || null);
      setCupos(r.cupos);
    } finally {
      setCargando(false);
    }
  }, [setCupos]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const decidir = async (tipo) => {
    const actual = tarjetas[0];
    if (!actual) return;
    // Se saca la tarjeta de la pila ANTES de esperar la respuesta: si se
    // espera, el pulgar rápido dispara dos veces sobre el mismo perfil y el
    // backend devuelve "ya interactuaste".
    setTarjetas((t) => t.slice(1));
    setArrastre({ x: 0, y: 0, soltando: false });
    // Respuesta táctil: un tic corto en el like, uno doble en el superfan y
    // un patrón en el match. Es la mitad de por qué las apps grandes se
    // sienten "vivas"; sin permiso extra en Android.
    try { navigator.vibrate?.(tipo === "superfan" ? [20, 40, 20] : 15); } catch { /* sin vibrador */ }
    try {
      const r = await api.interactuar(actual.id, tipo);
      setCupos(r.cupos);
      if (r.match) {
        try { navigator.vibrate?.([30, 60, 30, 60, 80]); } catch { /* sin vibrador */ }
        setMatch({ ...r, con: r.con });
      }
    } catch (e) {
      if (e instanceof ErrorApi && e.sinCupo) {
        setMuro(e.cuerpo);
        setTarjetas((t) => [actual, ...t]); // se devuelve: el like no ocurrió
      }
    }
  };

  const rebobinar = async () => {
    try {
      await api.rebobinar();
      await cargar();
    } catch (e) {
      if (e instanceof ErrorApi && e.sinCupo) setMuro(e.cuerpo);
    }
  };

  const correrAutomatch = async () => {
    const r = await api.correrAuto();
    setCupos(r.cupos);
    if (r.creados.length) setMatch({ ...r.creados[0], automatico: true });
    else setMuro({ detail: "No hay nadie que supere el umbral por ahora. Probá más tarde." });
  };

  // --- arrastre ---
  const bajar = (e) => {
    if (!tarjetas.length) return;
    inicio.current = { x: e.clientX, y: e.clientY };
    e.currentTarget.setPointerCapture?.(e.pointerId);
  };
  const mover = (e) => {
    if (!inicio.current) return;
    setArrastre({
      x: e.clientX - inicio.current.x,
      y: e.clientY - inicio.current.y,
      soltando: false,
    });
  };
  const soltar = () => {
    if (!inicio.current) return;
    inicio.current = null;
    const { x, y } = arrastre;
    if (y < -UMBRAL_Y) decidir("superfan");
    else if (x > UMBRAL_X) decidir("like");
    else if (x < -UMBRAL_X) decidir("pass");
    else setArrastre({ x: 0, y: 0, soltando: true });
  };

  const actual = tarjetas[0];
  const siguiente = tarjetas[1];

  return (
    <>
      <h1 className="page-title">{t("Descubrir")}</h1>
      <p className="page-sub">
        Deslizá o usá los botones. Arrastrar hacia arriba es superfan. Se ordena por cercanía
        primero y después por compatibilidad, popularidad y actividad reciente.
      </p>

      <div className="deck-zona">
        <div>
          <div
            className="deck"
            onPointerDown={bajar}
            onPointerMove={mover}
            onPointerUp={soltar}
            onPointerCancel={soltar}
          >
            {cargando && <div className="panel">{t("Cargando perfiles…")}</div>}
            {!cargando && !actual && (
              <div className="panel" style={{ height: "100%" }}>
                <h3>No queda nadie con estos filtros</h3>
                {diagnostico && Object.keys(diagnostico).length > 0 ? (
                  <>
                    <p style={{ color: "var(--muted)", fontSize: 13.5 }}>
                      Descartamos perfiles por estos motivos:
                    </p>
                    <ul style={{ paddingLeft: 18, fontSize: 13.5, color: "var(--muted)" }}>
                      {Object.entries(diagnostico)
                        .sort((a, b) => b[1] - a[1])
                        .map(([k, n]) => (
                          <li key={k}>
                            <b style={{ color: "var(--ink)" }}>{n}</b>{" "}
                            {MOTIVOS_VACIO[k] || k}
                          </li>
                        ))}
                    </ul>
                    <button className="btn btn-primario" onClick={() => navegar("/filtros")}>
                      Aflojar filtros
                    </button>
                  </>
                ) : (
                  <p style={{ color: "var(--muted)" }}>Volvé más tarde: se suma gente todo el día.</p>
                )}
              </div>
            )}
            {siguiente && <Carta tarjeta={siguiente} fondo arrastre={arrastre} />}
            {actual && <Carta tarjeta={actual} arrastre={arrastre} />}
          </div>

          {actual && (
            <div className="acciones">
              <button
                className="accion rebobinar"
                onClick={rebobinar}
                title={cupos?.rebobinar ? "Rebobinar" : "Rebobinar es de Plus"}
                aria-label="Rebobinar"
              >
                <IcoDeshacer tam={20} />
              </button>
              <button
                className="accion grande nope"
                onClick={() => decidir("pass")}
                title="Pasar"
                aria-label="Pasar"
              >
                <IcoCruz tam={27} />
              </button>
              <button
                className="accion fan"
                onClick={() => decidir("superfan")}
                disabled={cupos?.superfans_restantes === 0}
                title="Superfan"
                aria-label="Superfan"
              >
                <IcoEstrella tam={20} relleno />
              </button>
              <button
                className="accion grande like"
                onClick={() => decidir("like")}
                title="Like"
                aria-label="Me gusta"
              >
                <IcoCorazon tam={27} relleno />
              </button>
            </div>
          )}
        </div>

        {/* Panel lateral con densidad de datos, al estilo Kobra: cupos,
            automatch y por qué apareció esta persona. */}
        <div className="grid">
          <div className="panel">
            <h3>Tus cupos de hoy</h3>
            <div className="grid grid-3">
              <div className="kpi">
                <div className="valor tnum">
                  {cupos?.likes_restantes === null ? "∞" : (cupos?.likes_restantes ?? "—")}
                </div>
                <div className="rotulo">Likes</div>
              </div>
              <div className="kpi">
                <div className="valor tnum">{cupos?.superfans_restantes ?? "—"}</div>
                <div className="rotulo">Superfans</div>
              </div>
              <div className="kpi">
                <div className="valor tnum">
                  {(cupos?.automatch_max ?? 0) - (cupos?.automatch_hoy ?? 0)}
                </div>
                <div className="rotulo">Automatch</div>
              </div>
            </div>
            {cupos?.plan === "gratis" && (
              <div className="aviso aviso-oro" style={{ marginTop: 13 }}>
                Estás en Free. Todos los filtros están incluidos; Plus suma likes ilimitados y ver
                quién te dio like, desde USD 3,99.
              </div>
            )}
          </div>

          <div className="panel">
            <h3>Match automático</h3>
            <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 0 }}>
              Empareja sólo cuando los dos se pasan todos los filtros del otro y la compatibilidad
              supera el umbral. Si nadie califica, no inventa.
            </p>
            <button className="btn btn-primario btn-bloque" onClick={correrAutomatch}>
              Buscar matches automáticos
            </button>
          </div>

          {actual?.motivos?.length > 0 && (
            <div className="panel">
              <h3>Por qué {actual.nombre}</h3>
              <div className="chips">
                {actual.motivos.map((m) => (
                  <span key={m} className="chip on">
                    {m}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {match && (
        <div className="velo-modal" onClick={() => setMatch(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>¡Es un match!</h2>
            <p style={{ color: "var(--muted)", margin: 0 }}>
              {match.automatico
                ? `El algoritmo emparejó con ${match.con.nombre} (${match.compatibilidad}% compatibles). Ninguno de los dos deslizó.`
                : `A ${match.con.nombre} también le gustaste.`}
            </p>
            <div className="modal-caras">
              <img src={match.con.fotos?.[0]?.url} alt="" />
            </div>
            <div style={{ display: "flex", gap: 9 }}>
              <button className="btn btn-bloque" onClick={() => setMatch(null)}>
                Seguir deslizando
              </button>
              <button
                className="btn btn-primario btn-bloque"
                onClick={() => navegar(`/matches/${match.match_id}`)}
              >
                Mandar mensaje
              </button>
            </div>
          </div>
        </div>
      )}

      {muro && (
        <div className="velo-modal" onClick={() => setMuro(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Se acabó el cupo</h2>
            <p style={{ color: "var(--muted)" }}>{muro.detail}</p>
            <div style={{ display: "flex", gap: 9, marginTop: 14 }}>
              <button className="btn btn-bloque" onClick={() => setMuro(null)}>
                Ahora no
              </button>
              {muro.plan_sugerido && (
                <button
                  className="btn btn-primario btn-bloque"
                  onClick={() => navegar("/planes")}
                >
                  Ver planes
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
