import { useCallback, useEffect, useRef, useState } from "react";
import { t } from "../i18n";
import { useNavigate } from "react-router-dom";
import { api, ErrorApi } from "../api";
import { useApp } from "../estado";
import { preferenciasEfectivas, soloPermitidos } from "../filtroCliente";
import { avisar, festejarMatch } from "../avisos";
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

// Pero la distancia sola no alcanza, y era la queja: "el deslizamiento es
// tosco". Un pulgar rápido recorre 60 px y suelta — la intención es clarísima
// y el gesto no disparaba, así que la carta volvía al centro y había que
// arrastrar de nuevo, largo y lento. Es exactamente lo que hace que un deck se
// sienta pesado.
//
// Con velocidad, un envión corto cuenta. 0,45 px/ms ≈ 450 px/s: arriba de eso
// nadie está "acomodando" la carta, la está tirando. El mínimo de 26 px es para
// que el temblor de un toque no se lea como envión.
const VELOCIDAD_FLICK = 0.45;
const MINIMO_FLICK = 26;

// Cuánto dura el vuelo de salida. La carta se sacaba de la pila a los 190 ms
// mientras la animación duraba 300: la tarjeta desaparecía a media salida, con
// un salto visible. Ahora los dos números salen de la misma constante, que es
// la única forma de que no se vuelvan a desincronizar.
const MS_VUELO = 260;

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
  const [muro, setMuro] = useState(null);
  // El gesto vive en refs: nada de esto puede provocar un render mientras el
  // dedo se mueve.
  const refCarta = useRef(null);
  // La carta de atrás también se anima: crece y se aclara a medida que la de
  // adelante se va. Sin eso el deck es una foto sobre otra foto; con eso hay
  // profundidad, que es la mitad de por qué el gesto se siente bien.
  const refFondo = useRef(null);
  const gesto = useRef({
    activo: false, x0: 0, y0: 0, x: 0, y: 0, pedido: 0,
    // Muestreo de velocidad, para el flick.
    t: 0, vx: 0, vy: 0, puntero: null,
  });

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const r = await api.deck(20);
      // Última línea de defensa del filtro duro: en serverless el deck puede
      // venir de una instancia que aún no vio tus preferencias nuevas.
      const limpias = soloPermitidos(preferenciasEfectivas(perfilRef.current?.preferencias), r.tarjetas);
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
    }, MS_VUELO);
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
      if (r.match) festejarMatch(r);
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
    if (r.creados.length) festejarMatch({ ...r.creados[0], automatico: true });
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

    // La de atrás acompaña: cuanto más lejos va la de adelante, más "sube" la
    // siguiente. Se escribe directo en el DOM igual que la de adelante — meter
    // esto por estado devolvería el re-render por cuadro que se sacó a mano.
    // Se animan LAS MISMAS propiedades que le da el CSS en reposo
    // (`.carta.fondo`: scale .945, translateY 16px, brightness .6): así,
    // cuando se borra el estilo en línea, la carta vuelve exactamente a donde
    // estaba. Escribir `scale()` a secas le comía el translateY y la carta de
    // atrás saltaba 16 px al soltar.
    const f = refFondo.current;
    if (f) {
      const avance = Math.min(1, Math.max(Math.abs(x) / UMBRAL_X, Math.abs(y) / UMBRAL_Y));
      f.style.transform =
        `scale(${(0.945 + 0.055 * avance).toFixed(4)}) translateY(${(16 * (1 - avance)).toFixed(2)}px)`;
      f.style.filter =
        `brightness(${(0.6 + 0.4 * avance).toFixed(3)}) saturate(${(0.8 + 0.2 * avance).toFixed(3)})`;
    }
  };

  const limpiarCarta = () => {
    const c = refCarta.current;
    if (c) {
      c.style.transition = "";
      c.style.transform = "";
      c.classList.remove("marca-like", "marca-nope", "marca-fan", "volando");
    }
    // La de atrás pasa a ser la de adelante en el próximo render: si le queda
    // el scale de la animación, la carta nueva aparece encogida un cuadro y
    // pega un salto. Se limpia junto con la otra.
    const f = refFondo.current;
    if (f) {
      f.style.transition = "";
      f.style.transform = "";
      f.style.filter = "";
    }
  };

  const bajar = (e) => {
    if (!tarjetas.length) return;
    const g = gesto.current;
    // Un solo dedo manda. Con dos, el segundo pointerdown reseteaba el origen
    // del gesto y la carta pegaba un salto al punto del dedo nuevo.
    if (g.activo) return;
    Object.assign(g, {
      activo: true, x0: e.clientX, y0: e.clientY, x: 0, y: 0,
      t: e.timeStamp || performance.now(), vx: 0, vy: 0, puntero: e.pointerId,
    });
    if (refCarta.current) refCarta.current.style.transition = "none";
    if (refFondo.current) refFondo.current.style.transition = "none";
    e.currentTarget.setPointerCapture?.(e.pointerId);
  };

  const mover = (e) => {
    const g = gesto.current;
    if (!g.activo || (g.puntero != null && e.pointerId !== g.puntero)) return;
    const x = e.clientX - g.x0;
    const y = e.clientY - g.y0;
    const t = e.timeStamp || performance.now();
    const dt = t - g.t;
    if (dt > 0) {
      // Suavizado exponencial: la velocidad instantánea entre dos eventos
      // pegados es puro ruido, y un solo cuadro lento la manda a cero justo
      // cuando el dedo se levanta — que es el momento en que la necesitamos.
      g.vx = 0.65 * ((x - g.x) / dt) + 0.35 * g.vx;
      g.vy = 0.65 * ((y - g.y) / dt) + 0.35 * g.vy;
      g.t = t;
    }
    g.x = x;
    g.y = y;
    if (!g.pedido) g.pedido = requestAnimationFrame(pintar);
  };

  const soltar = () => {
    const g = gesto.current;
    if (!g.activo) return;
    g.activo = false;
    g.puntero = null;
    if (g.pedido) {
      cancelAnimationFrame(g.pedido);
      g.pedido = 0;
    }
    const { x, y, vx, vy } = g;
    const c = refCarta.current;
    const f = refFondo.current;

    // Distancia O envión. El envión tiene que ir primero en el eje vertical:
    // un flick hacia arriba corto es un superfan, y si se evaluara la
    // distancia horizontal antes, terminaba siendo un like de costado.
    const flickArriba = vy < -VELOCIDAD_FLICK && y < -MINIMO_FLICK;
    const flickDerecha = vx > VELOCIDAD_FLICK && x > MINIMO_FLICK;
    const flickIzquierda = vx < -VELOCIDAD_FLICK && x < -MINIMO_FLICK;
    const tipo =
      y < -UMBRAL_Y || flickArriba
        ? "superfan"
        : x > UMBRAL_X || flickDerecha
          ? "like"
          : x < -UMBRAL_X || flickIzquierda
            ? "pass"
            : null;

    if (!tipo) {
      // Vuelve al centro con resorte. La transición la corre el compositor,
      // no el hilo principal.
      if (c) {
        c.style.transition = "transform .34s var(--resorte)";
        c.style.transform = "";
        c.classList.remove("marca-like", "marca-nope", "marca-fan");
      }
      if (f) {
        f.style.transition = "transform .34s var(--resorte), filter .34s ease";
        f.style.transform = "";
        f.style.filter = "";
      }
      return;
    }

    // La carta SALE VOLANDO hacia donde la mandó el dedo. Sin esto se
    // esfumaba de golpe y el swipe se sentía barato: el vuelo es lo que le
    // da peso a la decisión.
    //
    // Y sale en la dirección REAL del gesto, no siempre recto al costado: si
    // la tiraste en diagonal, se va en diagonal. Con la salida fija, el vuelo
    // contradecía al dedo y ahí es donde se sentía de cartón.
    if (c) {
      const ancho = window.innerWidth;
      const alto = window.innerHeight;
      const dirX = tipo === "pass" ? -1 : tipo === "like" ? 1 : Math.sign(x) || 0;
      const salidaX = tipo === "superfan" ? x + dirX * ancho * 0.3 : dirX * (ancho + 220);
      const salidaY =
        tipo === "superfan" ? -(alto + 220) : y + Math.sign(vy || y || 1) * 120;
      c.style.transition =
        `transform ${MS_VUELO}ms cubic-bezier(.22,.61,.36,1), opacity ${MS_VUELO}ms ease`;
      c.style.transform = `translate3d(${salidaX}px, ${salidaY}px, 0) rotate(${x * 0.09}deg)`;
      c.classList.add("volando");
    }
    // La de atrás termina de subir mientras la otra vuela: cuando la carta
    // nueva queda sola, ya está en tamaño completo y no se la ve "acomodarse".
    if (f) {
      f.style.transition = `transform ${MS_VUELO}ms ease-out, filter ${MS_VUELO}ms ease-out`;
      f.style.transform = "scale(1) translateY(0)";
      f.style.filter = "brightness(1) saturate(1)";
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
            {siguiente && <Carta key={siguiente.id} tarjeta={siguiente} fondo innerRef={refFondo} />}
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
