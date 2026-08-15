import { useCallback, useEffect, useRef, useState } from "react";
import { t } from "../i18n";
import { useNavigate } from "react-router-dom";
import { api, ErrorApi } from "../api";
import { useApp } from "../estado";
import { soloPermitidos } from "../filtroCliente";
import { avisar } from "../avisos";
import FestejoMatch from "../componentes/FestejoMatch";
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

function Carta({ tarjeta, fondo, innerRef, onFoto }) {
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

  // El transform NO viene por props ni por estado: lo escribe el gesto
  // directo en el DOM (ver `pintar`). Con `setState` en cada pointermove,
  // React re-renderizaba el deck entero —las dos cartas, el carrusel, las
  // insignias— sesenta veces por segundo, y el arrastre iba siempre atrasado
  // respecto del dedo.
  return (
    <article className={`carta ${fondo ? "fondo" : ""}`} ref={innerRef}>
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

      {/* Los tres sellos están siempre en el DOM y se revelan con una clase
          en la carta. Antes se montaban y desmontaban en cada pixel de
          arrastre: crear y destruir nodos durante un gesto es justo lo que lo
          hace sentir pegajoso. */}
      {!fondo && (
        <>
          <div className="sello like">Like</div>
          <div className="sello nope">Nope</div>
          <div className="sello fan">Superfan</div>
        </>
      )}

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
          {/* El número solo no se entendía: ahora dice qué mide. */}
          <span
            className="insignia insignia-comp"
            title="Cuánto coinciden tus filtros e intereses con los suyos"
          >
            <b>{tarjeta.compatibilidad}%</b> compatible con vos
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
  // El gesto vive en refs: nada de esto puede provocar un render mientras el
  // dedo se mueve.
  const refCarta = useRef(null);
  const gesto = useRef({ activo: false, x0: 0, y0: 0, x: 0, y: 0, pedido: 0 });

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
    // El pedido al servidor sale YA; la carta se quita cuando terminó de
    // volar. Red y animación en paralelo: el deck nunca "espera" la respuesta.
    setTimeout(() => {
      limpiarCarta();
      setTarjetas((t) => t.slice(1));
    }, 190);
    // Respuesta táctil: un tic corto en el like, uno doble en el superfan y
    // un patrón en el match. Es la mitad de por qué las apps grandes se
    // sienten "vivas"; sin permiso extra en Android.
    try { navigator.vibrate?.(tipo === "superfan" ? [20, 40, 20] : 15); } catch { /* sin vibrador */ }
    try {
      const r = await api.interactuar(actual.id, tipo);
      setCupos(r.cupos);
      if (tipo === "superfan" && !r.match) {
        const quedan = r.cupos?.superfans_restantes;
        avisar(
          quedan == null
            ? "Superfan enviado"
            : `Superfan enviado · te quedan ${quedan} esta semana`,
          { tipo: "ok" }
        );
      }
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
  //
  // Todo imperativo y sincronizado con requestAnimationFrame: se acumulan los
  // pointermove que llegan entre cuadros y se pinta UNA vez por cuadro. En un
  // teléfono llegan más eventos que cuadros, así que hacer `setState` en cada
  // uno era trabajo tirado que además atrasaba la carta.
  const pintar = () => {
    gesto.current.pedido = 0;
    const c = refCarta.current;
    if (!c) return;
    const { x, y } = gesto.current;
    c.style.transform = `translate3d(${x}px, ${y}px, 0) rotate(${x * 0.055}deg)`;
    c.classList.toggle("marca-like", x > 45);
    c.classList.toggle("marca-nope", x < -45);
    c.classList.toggle("marca-fan", y < -60);
  };

  const limpiarCarta = () => {
    const c = refCarta.current;
    if (!c) return;
    c.style.transition = "";
    c.style.transform = "";
    c.classList.remove("marca-like", "marca-nope", "marca-fan", "volando");
  };

  const bajar = (e) => {
    if (!tarjetas.length) return;
    const g = gesto.current;
    Object.assign(g, { activo: true, x0: e.clientX, y0: e.clientY, x: 0, y: 0 });
    if (refCarta.current) refCarta.current.style.transition = "none";
    e.currentTarget.setPointerCapture?.(e.pointerId);
  };

  const mover = (e) => {
    const g = gesto.current;
    if (!g.activo) return;
    g.x = e.clientX - g.x0;
    g.y = e.clientY - g.y0;
    if (!g.pedido) g.pedido = requestAnimationFrame(pintar);
  };

  const soltar = () => {
    const g = gesto.current;
    if (!g.activo) return;
    g.activo = false;
    if (g.pedido) {
      cancelAnimationFrame(g.pedido);
      g.pedido = 0;
    }
    const { x, y } = g;
    const c = refCarta.current;
    const tipo =
      y < -UMBRAL_Y ? "superfan" : x > UMBRAL_X ? "like" : x < -UMBRAL_X ? "pass" : null;

    if (!tipo) {
      // Vuelve al centro con resorte. La transición la corre el compositor,
      // no el hilo principal.
      if (c) {
        c.style.transition = "transform .34s var(--resorte)";
        c.style.transform = "";
        c.classList.remove("marca-like", "marca-nope", "marca-fan");
      }
      return;
    }

    // La carta SALE VOLANDO hacia donde la mandó el dedo. Sin esto se
    // esfumaba de golpe y el swipe se sentía barato: el vuelo es lo que le
    // da peso a la decisión.
    if (c) {
      const salidaX =
        tipo === "pass" ? -window.innerWidth : tipo === "like" ? window.innerWidth : x * 3;
      const salidaY = tipo === "superfan" ? -window.innerHeight : y * 1.4 + 60;
      c.style.transition = "transform .3s cubic-bezier(.3,0,.4,1), opacity .3s ease";
      c.style.transform = `translate3d(${salidaX}px, ${salidaY}px, 0) rotate(${x * 0.09}deg)`;
      c.classList.add("volando");
    }
    decidir(tipo);
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
            {siguiente && <Carta key={siguiente.id} tarjeta={siguiente} fondo />}
            {actual && <Carta key={actual.id} tarjeta={actual} innerRef={refCarta} />}
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
        <FestejoMatch
          con={match.con}
          compatibilidad={match.compatibilidad}
          automatico={match.automatico}
          onSeguir={() => setMatch(null)}
          onChat={() => navegar(`/matches/${match.match_id}`)}
        />
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
