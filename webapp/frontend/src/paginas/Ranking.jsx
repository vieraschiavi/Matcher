import { useEffect, useState } from "react";
import { t } from "../i18n";
import { api } from "../api";

export default function Ranking() {
  const [top, setTop] = useState([]);
  const [sugerencias, setSugerencias] = useState(null);

  useEffect(() => {
    api.ranking(25).then((r) => setTop(r.top));
    api.sugerenciasAuto().then(setSugerencias).catch(() => setSugerencias(null));
  }, []);

  return (
    <>
      <h1 className="page-title">{t("Más votados")}</h1>
      <p className="page-sub">
        El puntaje es la tasa de likes suavizada, no el total: un perfil con 3 likes en 4 vistas no
        le gana a uno con 300 en 1.200. El superfan vale por tres likes.
      </p>

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
    </>
  );
}
