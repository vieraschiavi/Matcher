import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, token as guardarToken } from "../api";
import { useApp } from "../estado";
import { GENEROS, alternar } from "../vocabulario";

// Segundo paso del login con proveedor: el email ya está confirmado, faltan
// los datos que sólo puede dar la persona. Se pide el mínimo indispensable
// para que el deck funcione — cada campo de más acá es gente que abandona el
// alta a mitad de camino.
export default function Completar() {
  const { catalogos, refrescar } = useApp();
  const [params] = useSearchParams();
  const alta = params.get("alta") || "";
  const [origen, setOrigen] = useState(null);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [f, setF] = useState({
    nombre: "",
    nacimiento: "1995-01-01",
    genero: "mujer",
    altura_cm: 170,
    pais: "",
    ciudad: "",
    politica: "neutro",
    generos_busca: [],
  });

  // País pre-elegido según el idioma del teléfono, corregible. El equipo de
  // fútbol es lo único que salió del alta (a pedido): vive en "Mi perfil".
  useEffect(() => {
    if (!catalogos || f.pais) return;
    const region = (navigator.language || "").split("-")[1]?.toUpperCase() || "";
    const elegido =
      catalogos.paises.find((p) => p.codigo === region) || catalogos.paises[0];
    if (elegido) {
      setF((v) => ({ ...v, pais: elegido.codigo, ciudad: elegido.ciudades[0]?.id || "" }));
    }
  }, [catalogos, f.pais]);

  useEffect(() => {
    if (!alta) return;
    api
      .leerAlta(alta)
      .then((d) => {
        setOrigen(d);
        setF((v) => ({ ...v, nombre: d.nombre || v.nombre }));
      })
      .catch((e) => setError(e.message));
  }, [alta]);

  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const pais = catalogos?.paises.find((p) => p.codigo === f.pais);

  const enviar = async (ev) => {
    ev.preventDefault();
    setError("");
    setOcupado(true);
    try {
      const r = await api.completarAlta({
        alta,
        nombre: f.nombre,
        nacimiento: f.nacimiento,
        genero: f.genero,
        altura_cm: Number(f.altura_cm),
        pais: f.pais,
        ciudad: f.ciudad,
        politica: f.politica,
        preferencias: { generos: f.generos_busca, edad_min: 18, edad_max: 99 },
      });
      guardarToken.guardar(r.token);
      window.location.hash = "#/descubrir";
      await refrescar();
    } catch (e) {
      setError(e.message);
    } finally {
      setOcupado(false);
    }
  };

  if (!alta) {
    return (
      <div className="entrar-fondo">
        <div className="entrar-caja panel">
          <div className="aviso aviso-error">
            Falta el identificador del alta. Volvé a entrar con tu proveedor.
          </div>
          <a className="btn btn-bloque" href="#/entrar" style={{ marginTop: 12, display: "block" }}>
            Volver
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="entrar-fondo">
      <div className="entrar-caja">
        <div className="entrar-marca">
          <div className="logo-grande">M</div>
          <h1>Ya casi</h1>
          <p>
            {origen
              ? `Confirmamos ${origen.email} con ${origen.proveedor}. Falta lo que sólo sabés vos.`
              : "Cargando…"}
          </p>
        </div>

        <div className="panel">
          <form onSubmit={enviar}>
            <div className="fila">
              <label className="campo">
                <span>Nombre</span>
                <input required value={f.nombre} onChange={set("nombre")} />
              </label>
              <label className="campo">
                <span>Nacimiento</span>
                <input type="date" required value={f.nacimiento} onChange={set("nacimiento")} />
              </label>
            </div>
            <div className="fila">
              <label className="campo">
                <span>Sos</span>
                <select value={f.genero} onChange={set("genero")}>
                  <option value="mujer">Mujer</option>
                  <option value="hombre">Hombre</option>
                  <option value="trans">Trans</option>
                  <option value="otro">Otro</option>
                </select>
              </label>
              <label className="campo">
                <span>Altura (cm)</span>
                <input
                  type="number"
                  min={130}
                  max={230}
                  value={f.altura_cm}
                  onChange={set("altura_cm")}
                />
              </label>
            </div>
            <label className="campo">
              <span>Buscás (podés elegir varios; nada marcado = todos)</span>
              <div className="chips">
                {GENEROS.map((g) => (
                  <button
                    key={g.v}
                    type="button"
                    className={`chip ${f.generos_busca.includes(g.v) ? "on" : ""}`}
                    onClick={() => setF({ ...f, generos_busca: alternar(f.generos_busca, g.v) })}
                  >
                    {g.t}
                  </button>
                ))}
              </div>
            </label>
            <div className="fila">
              <label className="campo">
                <span>País</span>
                <select
                  value={f.pais}
                  onChange={(e) => {
                    const p = catalogos?.paises.find((x) => x.codigo === e.target.value);
                    setF({ ...f, pais: e.target.value, ciudad: p?.ciudades[0]?.id || "" });
                  }}
                >
                  {catalogos?.paises.map((p) => (
                    <option key={p.codigo} value={p.codigo}>
                      {p.nombre}
                    </option>
                  ))}
                </select>
              </label>
              <label className="campo">
                <span>Ciudad</span>
                <select value={f.ciudad} onChange={set("ciudad")}>
                  {pais?.ciudades.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.nombre}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label className="campo">
              <span>Postura política</span>
              <select value={f.politica} onChange={set("politica")}>
                <option value="izquierda">Izquierda</option>
                <option value="derecha">Derecha</option>
                <option value="neutro">Neutro</option>
              </select>
            </label>

            {error && (
              <div className="aviso aviso-error" style={{ marginBottom: 12 }}>
                {error}
              </div>
            )}
            <button className="btn btn-primario btn-bloque" disabled={ocupado || !origen}>
              {ocupado ? "Creando tu cuenta…" : "Empezar"}
            </button>
          </form>
          <p style={{ color: "var(--faint)", fontSize: 12, margin: "10px 0 0" }}>
            Todo esto se cambia después desde tu perfil. Ahí también podés elegir tu equipo de
            fútbol, tus hobbies y escribir tu descripción.
          </p>
        </div>
      </div>
    </div>
  );
}
