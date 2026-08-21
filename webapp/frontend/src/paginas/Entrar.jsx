import { useEffect, useState } from "react";
import { t } from "../i18n";
import Logo from "../Logo";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useApp } from "../estado";
import { entrarConProveedor, hayLoginNativo } from "../loginNativo";
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
// La clave de las cuentas de demo NO va en el bundle: el bundle es público y
// el repositorio también. Se pasa al compilar sólo cuando se arma una build
// para mostrar (VITE_CLAVE_DEMO); sin eso, los botones de demo ni aparecen.
const CLAVE_DEMO = import.meta.env.VITE_CLAVE_DEMO || "";

export default function Entrar() {
  const { entrar, entrarConToken, registrar, catalogos, sesionCaida } = useApp();
  const [params] = useSearchParams();
  const navegar = useNavigate();
  const [pestana, setPestana] = useState("entrar");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [proveedores, setProveedores] = useState([]);
  const [efimero, setEfimero] = useState(false);
  // Vacío = el servidor contesta. Con texto = no hay con quién hablar, y ese
  // texto dice contra qué dirección está compilada esta versión de la app.
  const [sinServidor, setSinServidor] = useState("");
  // Sólo se muestran las cuentas de demo si el servidor lo habilita.
  const [demoPublica, setDemoPublica] = useState(false);
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
    // Si el backend corre sobre almacenamiento efímero hay que decirlo ANTES
    // de que alguien cree una cuenta y suba diez fotos, no después de que las
    // pierda. El servidor lo reporta; la interfaz no lo adivina.
    // El sondeo de salud es además la forma de saber si HAY servidor. Antes
    // este `catch` se tragaba el error y la pantalla de entrada quedaba
    // normal: recién al apretar "Entrar" aparecía un "Failed to fetch" que no
    // le dice nada a nadie. Con un APK compilado contra una URL equivocada eso
    // es toda la experiencia: una app que parece rota y no explica por qué.
    api
      .salud()
      .then((r) => {
        setEfimero(!!r.almacenamiento_efimero);
        setDemoPublica(!!r.demo_publica);
        setSinServidor("");
      })
      .catch((e) => setSinServidor(e?.sinRed ? e.message : ""));
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
      if (hayLoginNativo()) {
        // App instalada: navegador del sistema + vuelta por enlace profundo.
        // El WebView no sirve — Google lo rechaza y el token caería en el
        // origen equivocado. Está explicado en `loginNativo.js`.
        const r = await entrarConProveedor(nombre);
        if (r.token) await entrarConToken(r.token);
        else if (r.alta) navegar(`/completar?alta=${encodeURIComponent(r.alta)}`);
        setOcupado(false);
        return;
      }
      const { url } = await api.inicioLogin(nombre, "web");
      window.location.href = url; // se va al proveedor y vuelve al callback
    } catch (e) {
      // Cerrar el navegador a mano no es un error que haya que mostrar en
      // rojo: el usuario ya sabe que canceló.
      if (e.message !== "cancelado") setError(ERRORES[e.message] || e.message);
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
          <p>{t("Filtrá por lo que de verdad te importa. Todos los filtros, gratis.")}</p>
        </div>

        {sesionCaida && (
          <div className="aviso aviso-info" style={{ marginBottom: 14 }}>
            {t("Se cerró tu sesión y hay que entrar de nuevo. Tus datos están intactos.")}
          </div>
        )}

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
              <div className="separador">{t("o con tu email")}</div>
            </>
          )}

          {/* Va ARRIBA de todo y en los dos modos: sin servidor no se puede ni
              entrar ni crear cuenta, así que es lo primero que hay que saber. */}
          {sinServidor && (
            <div className="aviso aviso-error" style={{ marginBottom: 12 }}>
              {sinServidor}
            </div>
          )}

          {efimero && pestana === "crear" && (
            <div className="aviso aviso-oro" style={{ marginBottom: 12 }}>
              {t("Este servidor de demostración borra los datos cada vez que se reinicia: la cuenta y las fotos que subas se van a perder. Para probar sin sorpresas, usá una de las cuentas de demo de abajo.")}
            </div>
          )}

          <div className="pestanas">
            <button
              className={pestana === "entrar" ? "on" : ""}
              onClick={() => setPestana("entrar")}
            >
              {t("Entrar")}
            </button>
            <button
              className={pestana === "crear" ? "on" : ""}
              onClick={() => setPestana("crear")}
            >
              {t("Crear cuenta")}
            </button>
          </div>

          <form onSubmit={enviar}>
            <label className="campo">
              <span>{t("Email")}</span>
              <input type="email" required value={f.email} onChange={set("email")} />
            </label>
            <label className="campo">
              <span>{t("Contraseña")}</span>
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
                    <span>{t("Nombre")}</span>
                    <input required value={f.nombre} onChange={set("nombre")} />
                  </label>
                  <label className="campo">
                    <span>{t("Nacimiento")}</span>
                    <input type="date" required value={f.nacimiento} onChange={set("nacimiento")} />
                  </label>
                </div>
                <div className="fila">
                  <label className="campo">
                    <span>{t("Sos")}</span>
                    <select value={f.genero} onChange={set("genero")}>
                      <option value="mujer">{t("Mujer")}</option>
                      <option value="hombre">{t("Hombre")}</option>
                      <option value="trans">{t("Trans")}</option>
                      <option value="otro">{t("Otro")}</option>
                    </select>
                  </label>
                  <label className="campo">
                    <span>{t("Altura (cm)")}</span>
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
                  <span>{t("Buscás (podés elegir varios; nada marcado = todos)")}</span>
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
                    <span>{t("País")}</span>
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
                    <span>{t("Ciudad")}</span>
                    <select value={f.ciudad} onChange={set("ciudad")}>
                      {pais?.ciudades.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.nombre}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="campo">
                    <span>{t("Postura política")}</span>
                    <select value={f.politica} onChange={set("politica")}>
                      <option value="izquierda">{t("Izquierda")}</option>
                      <option value="derecha">{t("Derecha")}</option>
                      <option value="neutro">{t("Neutro")}</option>
                    </select>
                  </label>
                </div>
                {/* El equipo de fútbol es lo único que salió del alta, a
                    pedido. Se elige en "Mi perfil" y el filtro sigue igual. */}
                <label className="campo">
                  <span>{t("Tus hobbies (marcá los que quieras)")}</span>
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
                  <span>{t("Contá algo de vos")}</span>
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
              {ocupado ? t("Un momento…") : pestana === "entrar" ? t("Entrar") : t("Crear mi cuenta")}
            </button>
          </form>
        </div>

        {/* La demo dejó de ser pública para no regalarle el producto a la
            competencia: quien entra a una demo abierta se lleva las pantallas y
            los flujos sin dejar rastro y sin que nadie le venda nada. El video
            de la landing muestra el resultado; para ver la app andando hay que
            pedirla.

            Lo decide el SERVIDOR (`demo_publica` en /api/salud), no una
            constante del bundle: una bandera del cliente se enciende editando
            el JavaScript, y esto es justamente lo que no queremos que se pueda
            abrir desde afuera. */}
        {demoPublica && (
          <div className="panel demo-caja">
            <h3>{t("Probar la demo")}</h3>
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
          </div>
        )}
      </div>
    </div>
  );
}
