import { useEffect, useState } from "react";
import { t } from "../i18n";
import { api } from "../api";
import RangoDoble from "../componentes/RangoDoble";
import { useApp } from "../estado";
import { GENEROS, INTENCIONES, POLITICAS, alternar } from "../vocabulario";

export default function Filtros() {
  const { perfil, catalogos, refrescar, guardarPreferencias } = useApp();
  const [p, setP] = useState(perfil?.preferencias);
  const [guardado, setGuardado] = useState("");
  const [error, setError] = useState("");
  const [conteo, setConteo] = useState(null);

  useEffect(() => setP(perfil?.preferencias), [perfil]);

  if (!p || !catalogos) return <p className="page-sub">{t("Cargando…")}</p>;

  // Los equipos se ofrecen del país del usuario, y la unidad de distancia
  // (km o millas) también sale de ahí: un uruguayo elige entre equipos
  // uruguayos y ve km; alguien en EE.UU./Reino Unido ve millas.
  const miPais = catalogos.paises.find((x) => x.codigo === perfil.pais);
  const unidad = miPais?.unidad === "mi" ? "mi" : "km";
  const AMILLA = 0.621371;
  const aVisible = (km) => (unidad === "mi" ? Math.round(km * AMILLA) : Math.round(km));
  const aKm = (v) => (unidad === "mi" ? Math.round(v / AMILLA) : v);

  const set = (k, v) => {
    setP({ ...p, [k]: v });
    setGuardado("");
  };

  const guardar = async () => {
    setError("");
    try {
      await guardarPreferencias(p);
      await refrescar();
      const d = await api.deck(20);
      setConteo(d.tarjetas.length);
      setGuardado("Filtros guardados.");
    } catch (e) {
      setError(e.message);
    }
  };

  const distanciaMax = p.distancia_max_km ?? 200;

  return (
    <>
      <h1 className="page-title">{t("Filtros")}</h1>
      <p className="page-sub">
        Todos los filtros están incluidos en el plan gratis. Se aplican como filtro duro: si pedís
        sólo hinchas de un equipo, no aparece nadie más — no se “compensa” con otra afinidad.
      </p>

      <div className="grid grid-2">
        <div className="panel">
          <h3>Sexo</h3>
          <p style={{ color: "var(--muted)", fontSize: 12.5, marginTop: 0 }}>
            Podés elegir varios. Sin nada marcado, aparecen todos.
          </p>
          <div className="chips">
            {GENEROS.map((g) => (
              <button
                key={g.v}
                className={`chip ${p.generos.includes(g.v) ? "on" : ""}`}
                onClick={() => set("generos", alternar(p.generos, g.v))}
              >
                {g.t}
              </button>
            ))}
          </div>
        </div>

        <div className="panel">
          <h3>¿Qué buscás?</h3>
          <p style={{ color: "var(--muted)", fontSize: 12.5, marginTop: 0 }}>
            Multi-selección. Alcanza con que coincida una para aparecer en el deck del otro.
          </p>
          <div className="chips">
            {INTENCIONES.filter((i) => i.v !== "disponible_hoy").map((i) => (
              <button
                key={i.v}
                className={`chip ${p.intenciones.includes(i.v) ? "on" : ""}`}
                onClick={() => set("intenciones", alternar(p.intenciones, i.v))}
              >
                {i.icono} {i.t}
              </button>
            ))}
          </div>
        </div>

        <div className="panel">
          <h3>Edad</h3>
          <RangoDoble
            min={18}
            max={99}
            valorMin={p.edad_min}
            valorMax={p.edad_max}
            unidad=""
            onCambiar={(min, max) => setP({ ...p, edad_min: min, edad_max: max })}
          />
        </div>

        <div className="panel">
          <h3>Altura</h3>
          <RangoDoble
            min={130}
            max={230}
            valorMin={p.altura_min_cm ?? 130}
            valorMax={p.altura_max_cm ?? 230}
            unidad=" cm"
            onCambiar={(min, max) =>
              setP({
                ...p,
                altura_min_cm: min === 130 ? null : min,
                altura_max_cm: max === 230 ? null : max,
              })
            }
          />
          <p style={{ color: "var(--faint)", fontSize: 12, margin: 0 }}>
            En los extremos, sin límite.
          </p>
        </div>

        <div className="panel">
          <h3>Distancia</h3>
          <div className="rango-doble">
            <div className="rango-doble-valores">
              <span>0 {unidad}</span>
              <span>
                {p.distancia_max_km == null ? "sin límite" : `${aVisible(distanciaMax)} ${unidad}`}
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={aVisible(200)}
              value={p.distancia_max_km == null ? aVisible(200) : aVisible(distanciaMax)}
              onChange={(e) => {
                const v = Number(e.target.value);
                set("distancia_max_km", v >= aVisible(200) ? null : aKm(v));
              }}
              style={{ width: "100%" }}
            />
          </div>
          <label style={{ display: "flex", gap: 9, alignItems: "center", marginTop: 9, marginBottom: 11 }}>
            <input
              type="checkbox"
              style={{ width: "auto" }}
              checked={p.solo_mi_pais}
              onChange={(e) => set("solo_mi_pais", e.target.checked)}
            />
            <span>Sólo mi país ({miPais?.nombre})</span>
          </label>
          <label style={{ display: "flex", gap: 9, alignItems: "center" }}>
            <input
              type="checkbox"
              style={{ width: "auto" }}
              checked={p.solo_verificados}
              onChange={(e) => set("solo_verificados", e.target.checked)}
            />
            <span>Sólo perfiles verificados</span>
          </label>
        </div>

        <div className="panel">
          <h3>Postura política</h3>
          <p style={{ color: "var(--muted)", fontSize: 12.5, marginTop: 0 }}>
            Sin nada marcado, aparecen todas.
          </p>
          <div className="chips">
            {POLITICAS.map((x) => (
              <button
                key={x.v}
                className={`chip ${p.politicas.includes(x.v) ? "on" : ""}`}
                onClick={() => set("politicas", alternar(p.politicas, x.v))}
              >
                {x.t}
              </button>
            ))}
          </div>
        </div>

        <div className="panel">
          <h3>Equipo de fútbol · {miPais?.nombre}</h3>
          <p style={{ color: "var(--muted)", fontSize: 12.5, marginTop: 0 }}>
            Los equipos salen de tu país de localización. Sin nada marcado, aparecen todos.
          </p>
          <div className="chips">
            {miPais?.equipos.map((e) => (
              <button
                key={e}
                className={`chip ${p.equipos.includes(e) ? "on" : ""}`}
                onClick={() => set("equipos", alternar(p.equipos, e))}
              >
                {e}
              </button>
            ))}
          </div>
        </div>

        <div className="panel" style={{ gridColumn: "1 / -1" }}>
          <h3>Intereses que te importan</h3>
          <div className="chips">
            {catalogos.intereses.slice(0, 28).map((i) => (
              <button
                key={i}
                className={`chip ${p.intereses.includes(i) ? "on" : ""}`}
                onClick={() => set("intereses", alternar(p.intereses, i))}
              >
                {i}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && (
        <div className="aviso aviso-error" style={{ marginTop: 16 }}>
          {error}
        </div>
      )}
      {guardado && (
        <div className="aviso aviso-ok" style={{ marginTop: 16 }}>
          {guardado} Con estos filtros hay <b>{conteo}</b> perfil{conteo === 1 ? "" : "es"} en tu
          deck ahora mismo.
        </div>
      )}
      <button className="btn btn-primario" style={{ marginTop: 16 }} onClick={guardar}>
        {t("Guardar filtros")}
      </button>
    </>
  );
}
