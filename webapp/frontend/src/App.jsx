import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api";
import { useApp } from "./estado";
import Chat from "./paginas/Chat";
import Completar from "./paginas/Completar";
import Cruces from "./paginas/Cruces";
import Descubrir from "./paginas/Descubrir";
import Entrar from "./paginas/Entrar";
import Filtros from "./paginas/Filtros";
import MiPerfil from "./paginas/MiPerfil";
import Planes from "./paginas/Planes";
import Radar from "./paginas/Radar";
import Ranking from "./paginas/Ranking";

const MENU = [
  { a: "/descubrir", icono: "🔥", texto: "Descubrir" },
  { a: "/radar", icono: "📍", texto: "Radar" },
  { a: "/matches", icono: "💬", texto: "Matches", globo: "matches" },
  { a: "/likes", icono: "💛", texto: "Te gustaron", globo: "likes" },
  { a: "/ranking", icono: "🏆", texto: "Más votados" },
  // Nada de 🎛️ ni 🙂: en Android se dibujan como un dado y una cara plana y
  // no se entiende qué son. Los que quedaron se leen igual en las tres.
  { a: "/filtros", icono: "⚙️", texto: "Filtros" },
  { a: "/perfil", icono: "👤", texto: "Mi perfil" },
  { a: "/planes", icono: "💎", texto: "Planes" },
];

function Barra({ globos }) {
  const { perfil, salir } = useApp();
  return (
    <nav className="sidebar">
      <div className="brand">
        <div className="brand-logo">M</div>
        <b>
          Match<span>er</span>
        </b>
      </div>
      {MENU.map((m) => (
        <NavLink
          key={m.a}
          to={m.a}
          className={({ isActive }) => `nav-item ${isActive ? "activo" : ""}`}
        >
          <span className="icono">{m.icono}</span>
          <span>{m.texto}</span>
          {m.globo && globos[m.globo] > 0 && <span className="globo">{globos[m.globo]}</span>}
        </NavLink>
      ))}
      <div className="nav-pie">
        <div style={{ padding: "0 12px 10px", fontSize: 12, color: "var(--muted)" }}>
          {perfil?.nombre} · {perfil?.plan === "gratis" ? "Free" : perfil?.plan.toUpperCase()}
        </div>
        <button className="nav-item" onClick={salir}>
          <span className="icono">⏻</span>
          <span>Salir</span>
        </button>
      </div>
    </nav>
  );
}

// Vista de "te gustaron". Vive acá porque es media pantalla y comparte todo
// con el deck; separarla en su archivo era un import y nada más.
function Likes() {
  const [datos, setDatos] = useState(null);
  useEffect(() => {
    api.likesRecibidos().then(setDatos).catch(() => setDatos({ visible: false, cantidad: 0 }));
  }, []);
  if (!datos) return <p className="page-sub">Cargando…</p>;

  return (
    <>
      <h1 className="page-title">Te gustaron</h1>
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
                {p.tipo === "superfan" && <span className="insignia insignia-oro">⭐ Superfan</span>}
                {p.sintetico && <span className="insignia insignia-sint">Sintético</span>}
              </div>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

export default function App() {
  const { perfil, cargando } = useApp();
  const [globos, setGlobos] = useState({ matches: 0, likes: 0 });
  const ubicacion = useLocation();

  // Se recuenta al cambiar de pantalla y no con un temporizador: en el APK un
  // polling de fondo vacía la batería y no aporta nada en una demo.
  useEffect(() => {
    if (!perfil) return;
    Promise.all([api.matches(), api.likesRecibidos()])
      .then(([m, l]) =>
        setGlobos({
          matches: m.matches.reduce((s, x) => s + x.sin_leer, 0),
          likes: l.cantidad || 0,
        })
      )
      .catch(() => {});
  }, [perfil, ubicacion.pathname]);

  if (cargando) {
    return (
      <div className="entrar-fondo">
        <div className="entrar-marca">
          <div className="logo-grande">M</div>
          <p>Cargando…</p>
        </div>
      </div>
    );
  }
  // Sin sesión hay dos pantallas: entrar y completar el alta que empezó el
  // proveedor. `/completar` tiene que existir acá porque llega desde el
  // callback de Google, cuando todavía no hay perfil.
  if (!perfil) {
    return (
      <Routes>
        <Route path="/completar" element={<Completar />} />
        <Route path="*" element={<Entrar />} />
      </Routes>
    );
  }

  return (
    <div className="layout">
      <Barra globos={globos} />
      <main className="main">
        <Routes>
          <Route path="/" element={<Navigate to="/descubrir" replace />} />
          <Route path="/descubrir" element={<Descubrir />} />
          <Route path="/matches" element={<Chat />} />
          <Route path="/matches/:id" element={<Chat />} />
          <Route path="/likes" element={<Likes />} />
          <Route path="/radar" element={<Radar />} />
          <Route path="/cruces" element={<Cruces />} />
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
