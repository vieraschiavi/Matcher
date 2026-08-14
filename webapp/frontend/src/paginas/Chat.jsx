import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";

export default function Chat() {
  const { id } = useParams();
  const navegar = useNavigate();
  const [matches, setMatches] = useState([]);
  const [mensajes, setMensajes] = useState([]);
  const [texto, setTexto] = useState("");
  const [cargando, setCargando] = useState(true);
  const fin = useRef(null);

  // El `finally` no es decorativo: si el pedido falla (sesión vencida, red
  // caída) y sólo se apaga `cargando` en el `then`, la pantalla se queda en
  // "Cargando…" para siempre y no hay forma de saber qué pasó.
  useEffect(() => {
    api
      .matches()
      .then((r) => setMatches(r.matches))
      .catch(() => setMatches([]))
      .finally(() => setCargando(false));
  }, []);

  useEffect(() => {
    if (!id) {
      setMensajes([]);
      return;
    }
    api.mensajes(id).then((r) => setMensajes(r.mensajes)).catch(() => setMensajes([]));
  }, [id]);

  useEffect(() => {
    fin.current?.scrollIntoView({ behavior: "smooth" });
  }, [mensajes]);

  const activo = matches.find((m) => m.id === id);

  const enviar = async (e) => {
    e.preventDefault();
    const t = texto.trim();
    if (!t || !id) return;
    setTexto("");
    const r = await api.enviar(id, t);
    setMensajes((m) => [...m, { ...r.mensaje, mio: true }]);
  };

  const deshacer = async () => {
    if (!activo) return;
    await api.borrarMatch(activo.id);
    setMatches((m) => m.filter((x) => x.id !== activo.id));
    navegar("/matches");
  };

  if (cargando) return <p className="page-sub">Cargando…</p>;

  return (
    <>
      <h1 className="page-title">Matches</h1>
      <p className="page-sub">
        {matches.length === 0
          ? "Todavía no tenés matches. Deslizá en Descubrir o probá el match automático."
          : `${matches.length} conversación${matches.length === 1 ? "" : "es"} abiertas.`}
      </p>

      {/* La proporción de columnas va en CSS, NO en un style en línea: el
          estilo en línea le gana al @media de móvil y la grilla de dos
          columnas no colapsaba. En un teléfono el panel derecho quedaba
          fuera de pantalla y la página parecía rota. */}
      <div className="deck-zona zona-chat">
        <div className="panel">
          <h3>Conversaciones</h3>
          <div className="chat-lista">
            {matches.map((m) => (
              <div
                key={m.id}
                className={`chat-fila ${m.id === id ? "activo" : ""}`}
                onClick={() => navegar(`/matches/${m.id}`)}
              >
                <img src={m.con.fotos?.[0]?.url} alt="" />
                <div className="chat-cuerpo">
                  <b>
                    {m.con.nombre}, {m.con.edad}
                  </b>
                  <span>
                    {m.ultimo_mensaje
                      ? `${m.ultimo_mensaje.mio ? "Vos: " : ""}${m.ultimo_mensaje.texto}`
                      : m.automatico
                        ? "Match automático · escribí primero"
                        : "Se gustaron · escribí primero"}
                  </span>
                </div>
                {m.sin_leer > 0 && <span className="globo">{m.sin_leer}</span>}
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          {!activo && <p style={{ color: "var(--muted)" }}>Elegí una conversación.</p>}
          {activo && (
            <>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  borderBottom: "1px solid var(--line)",
                  paddingBottom: 12,
                  marginBottom: 12,
                }}
              >
                <img
                  src={activo.con.fotos?.[0]?.url}
                  alt=""
                  style={{ width: 48, height: 48, borderRadius: "50%", objectFit: "cover" }}
                />
                <div style={{ flex: 1 }}>
                  <b>
                    {activo.con.nombre}, {activo.con.edad}
                  </b>
                  <div style={{ display: "flex", gap: 6, marginTop: 4, flexWrap: "wrap" }}>
                    <span className="insignia insignia-comp">{activo.compatibilidad}%</span>
                    {activo.automatico && (
                      <span className="insignia insignia-auto">⚡ Match automático</span>
                    )}
                    {activo.con.sintetico && (
                      <span className="insignia insignia-sint">Sintético</span>
                    )}
                  </div>
                </div>
                <button className="btn btn-fantasma" onClick={deshacer}>
                  Deshacer match
                </button>
              </div>

              <div className="burbujas">
                {mensajes.length === 0 && (
                  <p style={{ color: "var(--muted)", fontSize: 13 }}>
                    {activo.automatico
                      ? "Los emparejó el algoritmo. Nadie deslizó — decilo si querés, funciona bien como apertura."
                      : "Todavía no se dijeron nada."}
                  </p>
                )}
                {mensajes.map((m) => (
                  <div key={m.id} className={`burbuja ${m.mio ? "mia" : "suya"}`}>
                    {m.texto}
                  </div>
                ))}
                <div ref={fin} />
              </div>

              <form onSubmit={enviar} style={{ display: "flex", gap: 9, marginTop: 12 }}>
                <input
                  value={texto}
                  onChange={(e) => setTexto(e.target.value)}
                  placeholder={`Escribile a ${activo.con.nombre}…`}
                  maxLength={2000}
                />
                <button className="btn btn-primario" disabled={!texto.trim()}>
                  Enviar
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </>
  );
}
