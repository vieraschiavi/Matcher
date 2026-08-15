import { useEffect, useRef, useState } from "react";
import { t } from "../i18n";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { IcoAntifaz } from "../Iconos";

// Avatar de la lista y la cabecera. En una cita a ciegas sin revelar el
// servidor manda `fotos: []` (regla 8: no viaja lo que no se puede ver), así
// que acá no hay nada que "desblurear": se dibuja una silueta.
function Avatar({ con, tam = 48 }) {
  const url = con.fotos?.[0]?.url;
  if (url) return <img src={url} alt="" style={{ width: tam, height: tam, borderRadius: "50%", objectFit: "cover" }} />;
  return (
    <span className="silueta" style={{ width: tam, height: tam }} aria-label="Perfil sin revelar">
      <IcoAntifaz tam={Math.round(tam * 0.55)} />
    </span>
  );
}

export default function Chat() {
  const { id } = useParams();
  const navegar = useNavigate();
  const [matches, setMatches] = useState([]);
  const [mensajes, setMensajes] = useState([]);
  const [texto, setTexto] = useState("");
  const [cargando, setCargando] = useState(true);
  const [avisoCiegas, setAvisoCiegas] = useState("");
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
    if (activo?.ciego && !activo.ciego.revelado) {
      // El progreso de la revelación vive en el payload de matches; sin esto
      // había que salir del chat y volver para ver la barra moverse (o la
      // revelación misma, que es EL momento del feature).
      api.matches().then((mm) => setMatches(mm.matches)).catch(() => {});
    }
  };

  // El diferencial: la app elige a la mejor persona que pasa los filtros de
  // los dos y abre el chat SIN fotos. Se revelan solas cuando cada uno
  // escribió su parte. El botón vive acá porque el resultado es un chat.
  const pedirCiegas = async () => {
    setAvisoCiegas("");
    try {
      const r = await api.citaACiegas();
      try { navigator.vibrate?.([20, 40, 20]); } catch { /* sin vibrador */ }
      const m = await api.matches();
      setMatches(m.matches);
      navegar(`/matches/${r.match_id}`);
    } catch (e) {
      setAvisoCiegas(e.message);
    }
  };

  const deshacer = async () => {
    if (!activo) return;
    await api.borrarMatch(activo.id);
    setMatches((m) => m.filter((x) => x.id !== activo.id));
    navegar("/matches");
  };

  if (cargando) return <p className="page-sub">{t("Cargando…")}</p>;

  return (
    <>
      <h1 className="page-title">{t("Matches")}</h1>
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
          {/* Tarjeta grande y no un botón más de la lista: pasaba
              desapercibida entre las conversaciones y es EL diferencial. */}
          <button className="tarjeta-ciegas" onClick={pedirCiegas}>
            <span className="tarjeta-ciegas-icono"><IcoAntifaz tam={26} /></span>
            <span className="tarjeta-ciegas-texto">
              <b>{t("Cita a ciegas")}</b>
              <span>{t("Primero la charla, después las caras")}</span>
            </span>
            <span className="tarjeta-ciegas-cta">{t("Jugar")}</span>
          </button>
          {avisoCiegas && (
            <div className="aviso aviso-info" style={{ margin: "10px 0" }}>{avisoCiegas}</div>
          )}
          <h3>Conversaciones</h3>
          <div className="chat-lista">
            {matches.map((m) => (
              <div
                key={m.id}
                className={`chat-fila ${m.id === id ? "activo" : ""}`}
                onClick={() => navegar(`/matches/${m.id}`)}
              >
                <Avatar con={m.con} tam={44} />
                <div className="chat-cuerpo">
                  <b>
                    {m.con.nombre}, {m.con.edad}
                  </b>
                  <span>
                    {m.ultimo_mensaje
                      ? `${m.ultimo_mensaje.mio ? "Vos: " : ""}${m.ultimo_mensaje.texto}`
                      : m.ciego && !m.ciego.revelado
                        ? "Cita a ciegas · las fotos se revelan charlando"
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
                <Avatar con={activo.con} />
                <div style={{ flex: 1 }}>
                  <b>
                    {activo.con.nombre}, {activo.con.edad}
                  </b>
                  <div style={{ display: "flex", gap: 6, marginTop: 4, flexWrap: "wrap" }}>
                    <span className="insignia insignia-comp">{activo.compatibilidad}%</span>
                    {activo.ciego && !activo.ciego.revelado && (
                      <span className="insignia insignia-oro">
                        <IcoAntifaz tam={12} /> {t("Cita a ciegas")}
                      </span>
                    )}
                    {activo.ciego?.revelado && (
                      <span className="insignia insignia-auto">{t("Revelado")}</span>
                    )}
                    {activo.automatico && (
                      <span className="insignia insignia-auto">Match automático</span>
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

              {activo.ciego && !activo.ciego.revelado && (
                <div className="ciegas-progreso">
                  <p>
                    {t("Las fotos se revelan cuando los dos escriben")}{" "}
                    <b>{activo.ciego.umbral}</b> {t("mensajes cada uno.")}{" "}
                    {t("Vos")}: {activo.ciego.mios}/{activo.ciego.umbral} · {activo.con.nombre}:{" "}
                    {activo.ciego.suyos}/{activo.ciego.umbral}
                  </p>
                  <div className="ciegas-barra">
                    <span style={{ width: `${((activo.ciego.mios + activo.ciego.suyos) / (activo.ciego.umbral * 2)) * 100}%` }} />
                  </div>
                </div>
              )}

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
