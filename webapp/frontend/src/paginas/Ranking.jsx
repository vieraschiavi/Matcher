import { useEffect, useState } from "react";
import { t } from "../i18n";
import { ErrorApi, api } from "../api";
import { avisar } from "../avisos";
import { useNavigate } from "react-router-dom";
import { useApp } from "../estado";
import { soloPermitidos } from "../filtroCliente";

export default function Ranking() {
  const { perfil } = useApp();
  const navegar = useNavigate();
  const [top, setTop] = useState([]);
  const [hoy, setHoy] = useState(null);
  const [pestana, setPestana] = useState("hoy");
  const [sugerencias, setSugerencias] = useState(null);

  const cargarHoy = () =>
    api
      .topDia()
      .then((r) => setHoy(soloPermitidos(perfil?.preferencias, r.top)))
      .catch(() => setHoy([]));

  const likeDesdeHoy = async (id) => {
    try {
      const r = await api.interactuar(id, "like");
      if (r.match) {
        avisar(t("¡Es un match!") + " 🎉", { tipo: "festejo", vibrar: [30, 60, 30, 60, 80] });
        navegar(`/matches/${r.match_id}`);
      } else {
        avisar("💛 Like enviado", { tipo: "ok", vibrar: 15 });
        cargarHoy();
      }
    } catch (e) {
      if (e instanceof ErrorApi && e.sinCupo) navegar("/planes");
    }
  };

  useEffect(() => {
    // Cinturón y tiradores del filtro duro (ver filtroCliente.js).
    api.ranking(25).then((r) => setTop(soloPermitidos(perfil?.preferencias, r.top)));
    cargarHoy();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    api.sugerenciasAuto().then(setSugerencias).catch(() => setSugerencias(null));
  }, []);

  return (
    <>
      <h1 className="page-title">{t("Más votados")}</h1>
      <p className="page-sub">
        El puntaje es la tasa de likes suavizada, no el total: un perfil con 3 likes en 4 vistas no
        le gana a uno con 300 en 1.200. El superfan vale por tres likes.
      </p>

      <div className="pestanas" style={{ maxWidth: 340, marginBottom: 16 }}>
        <button className={pestana === "hoy" ? "on" : ""} onClick={() => setPestana("hoy")}>
          🔥 {t("Los de hoy")}
        </button>
        <button className={pestana === "siempre" ? "on" : ""} onClick={() => setPestana("siempre")}>
          {t("Histórico")}
        </button>
      </div>

      {pestana === "hoy" && (
        <>
          <p className="page-sub" style={{ marginTop: -6 }}>
            {t("Los más likeados de hoy que pasan tus filtros. Todavía no les respondiste: dales like desde acá.")}
          </p>
          {hoy === null && <div className="esqueleto" style={{ height: 180 }} />}
          {hoy?.length === 0 && (
            <p style={{ color: "var(--muted)" }}>{t("Hoy todavía no hay votados que pasen tus filtros.")}</p>
          )}
          <div className="grid grid-3">
            {hoy?.map((p) => (
              <div key={p.id} className="panel" style={{ padding: 0, overflow: "hidden" }}>
                <img
                  src={p.fotos?.[0]?.url}
                  alt=""
                  style={{ width: "100%", aspectRatio: "4/5", objectFit: "cover", display: "block" }}
                />
                <div style={{ padding: 13 }}>
                  <b>
                    {p.nombre}, {p.edad}
                  </b>
                  <div style={{ display: "flex", gap: 6, marginTop: 7, flexWrap: "wrap" }}>
                    <span className="insignia insignia-oro">🔥 {p.likes_hoy} hoy</span>
                    <span className="insignia insignia-comp">{p.compatibilidad}%</span>
                    {p.sintetico && <span className="insignia insignia-sint">Sintético</span>}
                  </div>
                  <button
                    className="btn btn-primario btn-bloque"
                    style={{ marginTop: 10 }}
                    onClick={() => likeDesdeHoy(p.id)}
                  >
                    ♥ Like
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {pestana === "siempre" && (
      <div className="grid grid-2" style={{ alignItems: "start" }}>
        <div className="panel">
          <h3>Ranking global</h3>
          <div style={{ overflowX: "auto" }}>
            <table className="tabla">
              <thead>
                <tr>
                  <th>#</th>
                  <th></th>
                  <th>Perfil</th>
                  <th style={{ width: 130 }}>Popularidad</th>
                  <th className="tnum">Likes</th>
                  <th className="tnum">★</th>
                </tr>
              </thead>
              <tbody>
                {top.map((p, i) => (
                  <tr key={p.id}>
                    <td className="tnum" style={{ color: "var(--muted)" }}>
                      {i + 1}
                    </td>
                    <td>
                      <img className="mini-foto" src={p.portada} alt="" />
                    </td>
                    <td>
                      <b>{p.nombre}</b>
                      <div style={{ display: "flex", gap: 5, marginTop: 3 }}>
                        {p.verificado && <span className="insignia insignia-verif">✓</span>}
                        {p.sintetico && <span className="insignia insignia-sint">Sintético</span>}
                      </div>
                    </td>
                    <td>
                      <div className="barra">
                        <i style={{ width: `${p.popularidad}%` }} />
                      </div>
                      <span className="tnum" style={{ fontSize: 11.5, color: "var(--muted)" }}>
                        {p.popularidad}
                      </span>
                    </td>
                    <td className="tnum">{p.likes_recibidos}</td>
                    <td className="tnum">{p.superfans_recibidos}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel">
          <h3>Tus candidatos a match automático</h3>
          <p style={{ color: "var(--muted)", fontSize: 12.5, marginTop: 0 }}>
            Umbral de compatibilidad: {sugerencias?.umbral ?? "—"}%. Sólo entran los que además te
            pasan a vos todos sus filtros.
          </p>
          {sugerencias?.sugerencias?.length === 0 && (
            <p style={{ color: "var(--muted)", fontSize: 13 }}>
              Nadie supera el umbral ahora mismo. Es a propósito: bajarlo para llenar la lista sería
              mentir sobre el porcentaje.
            </p>
          )}
          <div className="chat-lista">
            {sugerencias?.sugerencias?.map((s) => (
              <div key={s.id} className="chat-fila">
                <img src={s.fotos?.[0]?.url} alt="" />
                <div className="chat-cuerpo">
                  <b>
                    {s.nombre}, {s.edad}
                  </b>
                  <span>{s.motivos.join(" · ") || "Compatibilidad alta"}</span>
                </div>
                <span className="insignia insignia-comp">{s.compatibilidad}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>
      )}
    </>
  );
}
