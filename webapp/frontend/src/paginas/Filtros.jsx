import { useEffect, useState } from "react";
import { api } from "../api";
import { useApp } from "../estado";

const POLITICAS = [
  { v: "izquierda", t: "Izquierda" },
  { v: "derecha", t: "Derecha" },
  { v: "neutro", t: "Neutro" },
];

// Alterna un valor dentro de una lista. Lista vacía = "cualquiera", que es
// distinto de "ninguno": si el usuario destilda todo, el filtro se apaga.
const alternar = (lista, v) =>
  lista.includes(v) ? lista.filter((x) => x !== v) : [...lista, v];

export default function Filtros() {
  const { perfil, catalogos, refrescar } = useApp();
  const [p, setP] = useState(perfil?.preferencias);
  const [guardado, setGuardado] = useState("");
  const [error, setError] = useState("");
  const [conteo, setConteo] = useState(null);

  useEffect(() => setP(perfil?.preferencias), [perfil]);

  if (!p || !catalogos) return <p className="page-sub">Cargando…</p>;

  // Los equipos que se ofrecen son los del país del usuario. Es el punto del
  // filtro: un uruguayo elige entre equipos uruguayos, un mexicano entre
  // mexicanos. Cablear un país acá rompe el producto para todos los demás.
  const miPais = catalogos.paises.find((x) => x.codigo === perfil.pais);

  const set = (k, v) => {
    setP({ ...p, [k]: v });
    setGuardado("");
  };

  const guardar = async () => {
    setError("");
    try {
      await api.editar({ preferencias: p });
      await refrescar();
      const d = await api.deck(20);
      setConteo(d.tarjetas.length);
      setGuardado("Filtros guardados.");
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <>
      <h1 className="page-title">Filtros</h1>
      <p className="page-sub">
        Todos los filtros están incluidos en el plan gratis. Se aplican como filtro duro: si pedís
        sólo hinchas de un equipo, no aparece nadie más — no se “compensa” con otra afinidad.
      </p>

      <div className="grid grid-2">
        <div className="panel">
          <h3>Quién</h3>
          <label className="campo">
            <span>Buscás</span>
            <select value={p.busca} onChange={(e) => set("busca", e.target.value)}>
              <option value="mujeres">Mujeres</option>
              <option value="hombres">Hombres</option>
              <option value="todos">Todos</option>
            </select>
          </label>
          <div className="fila">
            <label className="campo">
              <span>Edad mínima</span>
              <input
                type="number"
                min={18}
                max={99}
                value={p.edad_min}
                onChange={(e) => set("edad_min", Number(e.target.value))}
              />
            </label>
            <label className="campo">
              <span>Edad máxima</span>
              <input
                type="number"
                min={18}
                max={99}
                value={p.edad_max}
                onChange={(e) => set("edad_max", Number(e.target.value))}
              />
            </label>
          </div>
          <div className="fila">
            <label className="campo">
              <span>Altura mín. (cm)</span>
              <input
                type="number"
                min={130}
                max={230}
                placeholder="sin mínimo"
                value={p.altura_min_cm ?? ""}
                onChange={(e) =>
                  set("altura_min_cm", e.target.value === "" ? null : Number(e.target.value))
                }
              />
            </label>
            <label className="campo">
              <span>Altura máx. (cm)</span>
              <input
                type="number"
                min={130}
                max={230}
                placeholder="sin máximo"
                value={p.altura_max_cm ?? ""}
                onChange={(e) =>
                  set("altura_max_cm", e.target.value === "" ? null : Number(e.target.value))
                }
              />
            </label>
          </div>
        </div>

        <div className="panel">
          <h3>Dónde</h3>
          <label className="campo">
            <span>Radio máximo (km)</span>
            <input
              type="number"
              min={1}
              placeholder="sin límite"
              value={p.distancia_max_km ?? ""}
              onChange={(e) =>
                set("distancia_max_km", e.target.value === "" ? null : Number(e.target.value))
              }
            />
          </label>
          <label style={{ display: "flex", gap: 9, alignItems: "center", marginBottom: 11 }}>
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
          <p style={{ color: "var(--faint)", fontSize: 12, marginBottom: 0 }}>
            El deck ordena por cercanía antes que por puntaje: nadie de otro país se cuela delante
            de alguien de tu ciudad.
          </p>
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
        Guardar filtros
      </button>
    </>
  );
}
