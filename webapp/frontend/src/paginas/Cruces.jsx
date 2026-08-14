import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ErrorApi } from "../api";

export default function Cruces() {
  const navegar = useNavigate();
  const [datos, setDatos] = useState(null);

  useEffect(() => {
    // Sin el catch, un pedido fallido dejaba `datos` en null y la pantalla
    // colgada en "Cargando…" para siempre.
    api.cruces().then(setDatos).catch(() => setDatos({ resumen: {}, personas: [] }));
  }, []);

  const like = async (id) => {
    try {
      const r = await api.interactuar(id, "like");
      if (r.match) navegar(`/matches/${r.match_id}`);
      else {
        const d = await api.cruces();
        setDatos(d);
      }
    } catch (e) {
      if (e instanceof ErrorApi && e.sinCupo) navegar("/planes");
    }
  };

  if (!datos) return <p className="page-sub">Cargando…</p>;

  return (
    <>
      <h1 className="page-title">Cruces</h1>
      <p className="page-sub">
        Se cuenta un cruce cuando estuvieron en el mismo lugar de verdad, no sólo cerca en el
        mapa. {datos.resumen.cruces_totales} cruces con {datos.resumen.personas} personas.
      </p>

      {datos.personas.length === 0 && (
        <div className="panel">
          <p style={{ color: "var(--muted)", margin: 0 }}>
            Todavía no detectamos cruces. Activá la ubicación en Radar para empezar a contarlos.
          </p>
        </div>
      )}

      <div className="grid grid-3">
        {datos.personas.map((p) => (
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
              <div style={{ display: "flex", gap: 6, margin: "7px 0", flexWrap: "wrap" }}>
                <span className="insignia insignia-oro">
                  Se cruzaron {p.veces}x
                </span>
                <span className="insignia insignia-comp">{p.compatibilidad}%</span>
              </div>
              <button className="btn btn-primario btn-bloque" onClick={() => like(p.id)}>
                ♥ Like
              </button>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
