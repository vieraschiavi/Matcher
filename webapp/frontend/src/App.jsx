import { useEffect, useRef, useState } from "react";
import Logo from "./Logo";
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api } from "./api";
import { useApp } from "./estado";
import { preferenciasEfectivas, soloPermitidos } from "./filtroCliente";
import { alAvisar, alFestejarMatch, avisar, festejarMatch } from "./avisos";
import FestejoMatch from "./componentes/FestejoMatch";
import { t } from "./i18n";
import {
  IcoChat,
  IcoCorazon,
  IcoDiamante,
  IcoDiana,
  IcoFiltros,
  IcoLlama,
  IcoPersona,
  IcoRadar,
  IcoSalir,
  IcoTrofeo,
} from "./Iconos";
import Chat from "./paginas/Chat";
import Completar from "./paginas/Completar";
import Cruces from "./paginas/Cruces";
import CrushTime from "./paginas/CrushTime";
import Descubrir from "./paginas/Descubrir";
import Entrar from "./paginas/Entrar";
import Filtros from "./paginas/Filtros";
import MiPerfil from "./paginas/MiPerfil";
import Planes from "./paginas/Planes";
import Radar from "./paginas/Radar";
import Ranking from "./paginas/Ranking";

// Los íconos son SVG propios (`Iconos.jsx`), no emoji: el emoji lo dibuja el
// sistema, así que cambiaba de forma entre Android, iOS y el navegador, y no
// se podía teñir con el color del ítem activo.
// `corta` es la etiqueta de la barra inferior del teléfono. En la lateral hay
// lugar para "Te gustaron"; abajo, con 51 px por pestaña, ese texto se partía
// en dos renglones y la barra quedaba con aire de maqueta.
//
// `principal` marca las cinco que van en la barra inferior. Ocho pestañas
// abajo no las tiene ninguna app de la categoría, y no es capricho: no entran
// sin romper el texto. Las otras tres viven en la barra de arriba del
// teléfono, que igual son de consulta, no de uso continuo.
const MENU = [
  { a: "/descubrir", Icono: IcoLlama, texto: "Descubrir", corta: "Descubrir", principal: true },
  { a: "/radar", Icono: IcoRadar, texto: "Radar", corta: "Radar", principal: true },
  { a: "/matches", Icono: IcoChat, texto: "Matches", corta: "Chats", globo: "matches", principal: true },
  { a: "/likes", Icono: IcoCorazon, texto: "Te gustaron", corta: "Likes", globo: "likes", principal: true },
  // El juego va en la barra de abajo y "Mi perfil" sube a la de arriba: la
  // barra inferior es para lo que se abre todos los días, y el perfil se
  // edita una vez por semana.
  { a: "/crush", Icono: IcoDiana, texto: "Crush Time", corta: "Crush", principal: true },
  { a: "/perfil", Icono: IcoPersona, texto: "Mi perfil", corta: "Perfil" },
  // Dejó de ser sólo el ranking: adentro viven "disponible hoy", los más
  // likeados del día y la tabla por barrio/ciudad/mundo. "Más votados" nombraba
  // una de las tres y escondía las otras dos.
  { a: "/ranking", Icono: IcoTrofeo, texto: "Explorar", corta: "Top" },
  { a: "/filtros", Icono: IcoFiltros, texto: "Filtros", corta: "Filtros" },
  { a: "/planes", Icono: IcoDiamante, texto: "Planes", corta: "Planes" },
];
const SECUNDARIAS = MENU.filter((m) => !m.principal);

function Barra({ globos }) {
  const { perfil, salir } = useApp();
  return (
    <nav className="sidebar">
      <div className="brand">
        <Logo tam={34} id="barra" />
        <b>
          Match<span>er</span>
        </b>
      </div>
      {MENU.map((m) => (
        <NavLink
          key={m.a}
          to={m.a}
          className={({ isActive }) =>
            `nav-item ${isActive ? "activo" : ""} ${m.principal ? "" : "solo-lateral"}`
          }
        >
          <span className="icono">
            <m.Icono tam={20} />
          </span>
          <span className="nav-texto">{t(m.texto)}</span>
          <span className="nav-texto-corto">{t(m.corta)}</span>
          {m.globo && globos[m.globo] > 0 && <span className="globo">{globos[m.globo]}</span>}
        </NavLink>
      ))}
      <div className="nav-pie">
        <div className="nav-quien">
          <span className="nav-quien-nombre">{perfil?.nombre}</span>
          <span className={`nav-plan ${perfil?.plan !== "gratis" ? "pago" : ""}`}>
            {perfil?.plan === "gratis" ? "Free" : perfil?.plan.toUpperCase()}
          </span>
        </div>
        <button className="nav-item" onClick={salir}>
          <span className="icono">
            <IcoSalir tam={20} />
          </span>
          <span>{t("Salir")}</span>
        </button>
      </div>
    </nav>
  );
}

// Barra de arriba, sólo en teléfono (el CSS la esconde en escritorio, donde
// todo esto ya está en la lateral). Lleva la marca y las tres secciones que
// no entran abajo.
function BarraSuperior() {
  const { perfil } = useApp();
  return (
    <header className="barra-sup">
      <div className="barra-sup-marca">
        <Logo tam={26} id="sup" />
        <b>
          Match<span>er</span>
        </b>
        {perfil && (
          <span className={`nav-plan ${perfil.plan !== "gratis" ? "pago" : ""}`}>
            {perfil.plan === "gratis" ? "Free" : perfil.plan.toUpperCase()}
          </span>
        )}
      </div>
      <div className="barra-sup-acciones">
        {SECUNDARIAS.map((m) => (
          <NavLink
            key={m.a}
            to={m.a}
            title={t(m.texto)}
            aria-label={t(m.texto)}
            className={({ isActive }) => `sup-boton ${isActive ? "activo" : ""}`}
          >
            <m.Icono tam={19} />
          </NavLink>
        ))}
      </div>
    </header>
  );
}

// Avisos flotantes. Uno solo por vez y se va solo: una pila de toasts
// apilados es ruido, no información.
function Avisos() {
  const [aviso, setAviso] = useState(null);
  useEffect(() => {
    let timer;
    const parar = alAvisar((a) => {
      setAviso(a);
      clearTimeout(timer);
      timer = setTimeout(() => setAviso(null), a.tipo === "festejo" ? 3800 : 2600);
    });
    return () => {
      parar();
      clearTimeout(timer);
    };
  }, []);
  if (!aviso) return null;
  return (
    <div className={`toast toast-${aviso.tipo}`} key={aviso.id} role="status">
      {aviso.texto}
    </div>
  );
}

// El festejo del match, montado una sola vez para toda la app: cualquier
// pantalla lo dispara con `festejarMatch(...)`.
function FestejoGlobal() {
  const navegar = useNavigate();
  const [match, setMatch] = useState(null);
  useEffect(() => alFestejarMatch(setMatch), []);
  if (!match) return null;
  return (
    <FestejoMatch
      con={match.con}
      compatibilidad={match.compatibilidad}
      automatico={match.automatico}
      onSeguir={() => setMatch(null)}
      onChat={() => {
        setMatch(null);
        navegar(`/matches/${match.match_id}`);
      }}
    />
  );
}

// Vista de "te gustaron". Vive acá porque es media pantalla y comparte todo
// con el deck; separarla en su archivo era un import y nada más.
function Likes() {
  const { perfil } = useApp();
  const navegar = useNavigate();
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");

  const cargar = () =>
    api
      .likesRecibidos()
      // Cinturón y tiradores del filtro duro (ver filtroCliente.js).
      .then((r) => setDatos({ ...r, perfiles: soloPermitidos(preferenciasEfectivas(perfil?.preferencias), r.perfiles) }))
      .catch(() => setDatos({ visible: false, cantidad: 0, perfiles: [] }));
  useEffect(() => {
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Responder el like ACÁ es el punto de la pantalla: te gustó → like de
  // vuelta → match instantáneo (la otra persona ya había dicho que sí) → al
  // chat. Antes la lista era sólo mirar, y "no deja chatear" era literal.
  const responder = async (id, tipo) => {
    setError("");
    try {
      const r = await api.interactuar(id, tipo);
      if (r.match) {
        festejarMatch(r);
        cargar();
      } else {
        try { navigator.vibrate?.(15); } catch { /* sin vibrador */ }
        cargar();
      }
    } catch (e) {
      setError(e.message);
    }
  };

  if (!datos) return <p className="page-sub">{t("Cargando…")}</p>;

  return (
    <>
      <h1 className="page-title">{t("Te gustaron")}</h1>
      <p className="page-sub">
        {datos.cantidad === 0
          ? "Todavía nadie pendiente. Seguí deslizando."
          : `${datos.cantidad} persona${datos.cantidad === 1 ? "" : "s"} te dio like y todavía no respondiste.`}
      </p>
      {!datos.visible && datos.cantidad > 0 && (
        <div className="aviso aviso-oro" style={{ marginBottom: 18 }}>
          Ver quién te dio like es de Plus en adelante.{" "}
          <NavLink to="/planes" style={{ textDecoration: "underline" }}>
            Ver planes desde USD 3,99
          </NavLink>
          .
        </div>
      )}
      {error && <div className="aviso aviso-error" style={{ marginBottom: 14 }}>{error}</div>}
      <div className="grid grid-3">
        {datos.perfiles?.map((p) => (
          <div key={p.id} className="panel" style={{ padding: 0, overflow: "hidden" }}>
            <img
              src={p.fotos[0]?.url}
              alt=""
              style={{ width: "100%", aspectRatio: "4/5", objectFit: "cover", display: "block" }}
            />
            <div style={{ padding: 13 }}>
              <b>
                {p.nombre}, {p.edad}
              </b>
              <div style={{ display: "flex", gap: 6, marginTop: 7, flexWrap: "wrap" }}>
                <span className="insignia insignia-comp">{p.compatibilidad}%</span>
                {p.tipo === "superfan" && <span className="insignia insignia-oro">Superfan</span>}
                {p.sintetico && <span className="insignia insignia-sint">Sintético</span>}
              </div>
              <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                <button className="btn btn-primario" style={{ flex: 1 }} onClick={() => responder(p.id, "like")}>
                  {t("Responder like")}
                </button>
                <button className="btn" onClick={() => responder(p.id, "pass")} aria-label="Pasar">
                  ✕
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

export default function App() {
  const { perfil, cargando, lang } = useApp();
  const [globos, setGlobos] = useState({ matches: 0, likes: 0 });
  const ubicacion = useLocation();
  // El último conteo de likes visto, para festejar SOLO cuando sube. Arranca
  // en null: la primera lectura no es un like nuevo, es el estado inicial —
  // sin esto la app festejaba al abrirse, que es mentirle al usuario.
  const likesVistos = useRef(null);

  // Se recuenta al cambiar de pantalla y no con un temporizador: en el APK un
  // polling de fondo vacía la batería y no aporta nada en una demo.
  useEffect(() => {
    if (!perfil) return;
    Promise.all([api.matches(), api.likesRecibidos()])
      .then(([m, l]) =>
        setGlobos(() => {
          const likes = l.cantidad || 0;
          if (likesVistos.current != null && likes > likesVistos.current) {
            avisar(t("¡Alguien te dio like! Mirá quién puede ser en Crush Time"), {
              tipo: "festejo",
              vibrar: [25, 50, 25],
            });
          }
          likesVistos.current = likes;
          return { matches: m.matches.reduce((s, x) => s + x.sin_leer, 0), likes };
        })
      )
      .catch(() => {});
  }, [perfil, ubicacion.pathname]);

  if (cargando) {
    return (
      <div className="entrar-fondo">
        <div className="entrar-marca">
          <Logo tam={62} id="cargando" />
          <p>{t("Cargando…")}</p>
        </div>
      </div>
    );
  }
  // Sin sesión hay dos pantallas: entrar y completar el alta que empezó el
  // proveedor. `/completar` tiene que existir acá porque llega desde el
  // callback de Google, cuando todavía no hay perfil.
  if (!perfil) {
    return (
      <Routes key={lang}>
        <Route path="/completar" element={<Completar />} />
        <Route path="*" element={<Entrar />} />
      </Routes>
    );
  }

  return (
    <div className="layout" key={lang}>
      <Avisos />
      <FestejoGlobal />
      <Barra globos={globos} />
      <BarraSuperior />
      <main className="main">
        <Routes>
          <Route path="/" element={<Navigate to="/descubrir" replace />} />
          <Route path="/descubrir" element={<Descubrir />} />
          <Route path="/matches" element={<Chat />} />
          <Route path="/matches/:id" element={<Chat />} />
          <Route path="/likes" element={<Likes />} />
          <Route path="/radar" element={<Radar />} />
          <Route path="/cruces" element={<Cruces />} />
          <Route path="/crush" element={<CrushTime />} />
          <Route path="/ranking" element={<Ranking />} />
          <Route path="/filtros" element={<Filtros />} />
          <Route path="/perfil" element={<MiPerfil />} />
          <Route path="/planes" element={<Planes />} />
          <Route path="/pago/:referencia" element={<Planes />} />
          <Route path="*" element={<Navigate to="/descubrir" replace />} />
        </Routes>
      </main>
    </div>
  );
}
