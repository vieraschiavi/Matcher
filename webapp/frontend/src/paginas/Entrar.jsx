import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useApp } from "../estado";

// Etiqueta y color por proveedor. Sólo se muestran los que el backend reporta
// como configurados: un botón de "Continuar con Google" que devuelve un error
// de configuración es peor que no tenerlo.
const PROVEEDORES = {
  google: { texto: "Continuar con Google", icono: "G", color: "#ffffff", fondo: "#ffffff" },
};

const ERRORES = {
  cuenta_desactivada: "Esa cuenta está desactivada.",
  access_denied: "Cancelaste el permiso en el proveedor.",
};

const CUENTAS_DEMO = [
  { email: "vieraschiavi@gmail.com", quien: "Martín · Gold, todo activado" },
  { email: "arcortito@gmail.com", quien: "Ariel · Gold, todo activado" },
];
const CLAVE_DEMO = "matcher2026";

export default function Entrar() {
  const { entrar, entrarConToken, registrar, catalogos } = useApp();
  const [params] = useSearchParams();
  const [pestana, setPestana] = useState("entrar");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [proveedores, setProveedores] = useState([]);
  const [f, setF] = useState({
    email: "",
    clave: "",
    nombre: "",
    nacimiento: "1995-01-01",
    genero: "mujer",
    altura_cm: 170,
    pais: "UY",
    ciudad: "UY-MVD",
    politica: "neutro",
    equipo: "",
    busca: "todos",
  });

  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const pais = catalogos?.paises.find((p) => p.codigo === f.pais);

  useEffect(() => {
    api.proveedoresLogin().then((r) => setProveedores(r.proveedores)).catch(() => {});
  }, []);

  // Vuelta del proveedor: llega `?token=…` (o `?error=…`) en el hash. El token
  // se consume y se borra de la URL — dejarlo ahí lo mete en el historial del
  // navegador y en cualquier captura de pantalla.
  useEffect(() => {
    const t = params.get("token");
    const e = params.get("error");
    if (e) setError(ERRORES[e] || `No se pudo entrar (${e}).`);
    if (t) {
      window.history.replaceState(null, "", window.location.pathname + "#/entrar");
      entrarConToken(t).catch((err) => setError(err.message));
    }
  }, [params, entrarConToken]);

  const entrarCon = async (nombre) => {
    setError("");
    setOcupado(true);
    try {
      const { url } = await api.inicioLogin(nombre);
      window.location.href = url; // se va al proveedor y vuelve al callback
    } catch (e) {
      setError(e.message);
      setOcupado(false);
    }
  };

  const enviar = async (ev) => {
    ev.preventDefault();
    setError("");
    setOcupado(true);
    try {
      if (pestana === "entrar") {
        await entrar(f.email, f.clave);
      } else {
        await registrar({
          email: f.email,
          clave: f.clave,
          nombre: f.nombre,
          nacimiento: f.nacimiento,
          genero: f.genero,
          altura_cm: Number(f.altura_cm),
          pais: f.pais,
          ciudad: f.ciudad,
          politica: f.politica,
          equipo: f.equipo,
          preferencias: { busca: f.busca, edad_min: 18, edad_max: 99 },
        });
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setOcupado(false);
    }
  };

  const entrarDemo = async (email) => {
    setError("");
    setOcupado(true);
    try {
      await entrar(email, CLAVE_DEMO);
    } catch (e) {
      setError(e.message);
    } finally {
      setOcupado(false);
    }
  };

  return (
    <div className="entrar-fondo">
      <div className="entrar-caja">
        <div className="entrar-marca">
          <div className="logo-grande">M</div>
          <h1>Matcher</h1>
          <p>Filtrá por lo que de verdad te importa. Todos los filtros, gratis.</p>
        </div>

        <div className="panel">
          {proveedores.length > 0 && (
            <>
              {proveedores.map((p) => (
                <button
                  key={p}
                  className="btn btn-bloque btn-proveedor"
                  disabled={ocupado}
                  onClick={() => entrarCon(p)}
                >
                  <span className="btn-proveedor-icono">{PROVEEDORES[p]?.icono || "•"}</span>
                  {PROVEEDORES[p]?.texto || `Continuar con ${p}`}
                </button>
              ))}
              <div className="separador">o con tu email</div>
            </>
          )}

          <div className="pestanas">
            <button
              className={pestana === "entrar" ? "on" : ""}
              onClick={() => setPestana("entrar")}
            >
              Entrar
            </button>
            <button
              className={pestana === "crear" ? "on" : ""}
              onClick={() => setPestana("crear")}
            >
              Crear cuenta
            </button>
          </div>

          <form onSubmit={enviar}>
            <label className="campo">
              <span>Email</span>
              <input type="email" required value={f.email} onChange={set("email")} />
            </label>
            <label className="campo">
              <span>Contraseña</span>
              <input
                type="password"
                required
                minLength={8}
                value={f.clave}
                onChange={set("clave")}
              />
            </label>

            {pestana === "crear" && (
              <>
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
                      <option value="no_binario">No binarie</option>
                    </select>
                  </label>
                  <label className="campo">
                    <span>Buscás</span>
                    <select value={f.busca} onChange={set("busca")}>
                      <option value="mujeres">Mujeres</option>
                      <option value="hombres">Hombres</option>
                      <option value="todos">Todos</option>
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
                <div className="fila">
                  <label className="campo">
                    <span>País</span>
                    <select
                      value={f.pais}
                      onChange={(e) => {
                        const p = catalogos?.paises.find((x) => x.codigo === e.target.value);
                        setF({
                          ...f,
                          pais: e.target.value,
                          ciudad: p?.ciudades[0]?.id || "",
                          equipo: "", // el catálogo de equipos es del país nuevo
                        });
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
                <div className="fila">
                  <label className="campo">
                    <span>Postura política</span>
                    <select value={f.politica} onChange={set("politica")}>
                      <option value="izquierda">Izquierda</option>
                      <option value="derecha">Derecha</option>
                      <option value="neutro">Neutro</option>
                    </select>
                  </label>
                  <label className="campo">
                    <span>Equipo de {pais?.nombre}</span>
                    <select value={f.equipo} onChange={set("equipo")}>
                      <option value="">No me interesa el fútbol</option>
                      {pais?.equipos.map((e) => (
                        <option key={e} value={e}>
                          {e}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              </>
            )}

            {error && (
              <div className="aviso aviso-error" style={{ marginBottom: 12 }}>
                {error}
              </div>
            )}
            <button className="btn btn-primario btn-bloque" disabled={ocupado}>
              {ocupado ? "Un momento…" : pestana === "entrar" ? "Entrar" : "Crear mi cuenta"}
            </button>
          </form>
        </div>

        <div className="panel demo-caja">
          <h3>Probar la demo</h3>
          <p style={{ color: "var(--muted)", fontSize: 12.5, margin: "0 0 11px" }}>
            Dos cuentas con Gold vigente, verificadas y con las 10 fotos cargadas. El resto de los
            perfiles son sintéticos y están marcados como tales.
          </p>
          {CUENTAS_DEMO.map((c) => (
            <button
              key={c.email}
              className="btn btn-bloque"
              disabled={ocupado}
              onClick={() => entrarDemo(c.email)}
            >
              <b>{c.email}</b>
              <br />
              <span style={{ color: "var(--muted)", fontWeight: 500, fontSize: 12 }}>{c.quien}</span>
            </button>
          ))}
          <p style={{ color: "var(--faint)", fontSize: 11.5, margin: "8px 0 0" }}>
            Contraseña de ambas: <code>{CLAVE_DEMO}</code>
          </p>
        </div>
      </div>
    </div>
  );
}
