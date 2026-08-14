import { useEffect, useState } from "react";
import Logo from "../Logo";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useApp } from "../estado";
import { GENEROS, alternar } from "../vocabulario";

// Etiqueta y color por proveedor. Sólo se muestran los que el backend reporta
// como configurados: un botón de "Continuar con Google" que devuelve un error
// de configuración es peor que no tenerlo.
const PROVEEDORES = {
  google: { texto: "Continuar con Google", icono: "G", clase: "btn-google" },
  facebook: { texto: "Continuar con Facebook", icono: "f", clase: "btn-facebook" },
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
    bio: "",
    intereses: [],
    pais: "",
    ciudad: "",
    politica: "neutro",
    generos_busca: [], // vacío = Todos, igual que en Filtros
  });

  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const pais = catalogos?.paises.find((p) => p.codigo === f.pais);

  // El país arranca pre-elegido según el idioma del teléfono ("es-UY" → UY),
  // pero el selector queda visible para corregirlo. El equipo de fútbol es lo
  // único que se fue del alta (a pedido): se elige después en "Mi perfil".
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
          bio: f.bio,
          intereses: f.intereses,
          pais: f.pais,
          ciudad: f.ciudad,
          politica: f.politica,
          preferencias: { generos: f.generos_busca, edad_min: 18, edad_max: 99 },
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
          <Logo tam={62} id="entrar" />
          <h1>Matcher</h1>
          <p>Filtrá por lo que de verdad te importa. Todos los filtros, gratis.</p>
        </div>

        <div className="panel">
          {proveedores.length > 0 && (
            <>
              {proveedores.map((p) => (
                <button
                  key={p}
                  className={`btn btn-bloque btn-proveedor ${PROVEEDORES[p]?.clase || ""}`}
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
                        onClick={() =>
                          setF({ ...f, generos_busca: alternar(f.generos_busca, g.v) })
                        }
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
                  <label className="campo">
                    <span>Postura política</span>
                    <select value={f.politica} onChange={set("politica")}>
                      <option value="izquierda">Izquierda</option>
                      <option value="derecha">Derecha</option>
                      <option value="neutro">Neutro</option>
                    </select>
                  </label>
                </div>
                {/* El equipo de fútbol es lo único que salió del alta, a
                    pedido. Se elige en "Mi perfil" y el filtro sigue igual. */}
                <label className="campo">
                  <span>Tus hobbies (marcá los que quieras)</span>
                  <div className="chips">
                    {(catalogos?.intereses || []).map((i) => (
                      <button
                        key={i}
                        type="button"
                        className={`chip ${f.intereses.includes(i) ? "on" : ""}`}
                        onClick={() => setF({ ...f, intereses: alternar(f.intereses, i) })}
                      >
                        {i}
                      </button>
                    ))}
                  </div>
                </label>
                <label className="campo">
                  <span>Contá algo de vos</span>
                  <textarea
                    value={f.bio}
                    maxLength={500}
                    rows={3}
                    placeholder="Una línea que dé pie a una respuesta: qué te gusta, qué buscás, qué te hace reír…"
                    onChange={set("bio")}
                  />
                </label>
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
