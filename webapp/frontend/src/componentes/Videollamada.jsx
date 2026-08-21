import { useEffect, useState } from "react";
import { AppLauncher } from "@capacitor/app-launcher";
import { Browser } from "@capacitor/browser";

import { api, esNativo } from "../api";
import { IcoVideo, LogoProveedor } from "../Iconos";
import { t } from "../i18n";

/**
 * Videollamada dentro del match.
 *
 * Toda la lógica de verdad vive en `matcher/videollamada.py`; acá sólo se
 * dibuja el estado que manda el servidor. Dos cosas que esta pantalla NO hace,
 * a propósito:
 *
 * - **No guarda el link en el cliente.** Mientras la propuesta está pendiente
 *   el servidor manda `enlace: null`, y esta pantalla no tiene de dónde
 *   sacarlo aunque quisiera. Es la regla 9 del producto: lo que decide el
 *   servidor no lo esconde el cliente.
 * - **No abre la llamada adentro de la app.** Meet, Zoom y Webex piden cámara
 *   y micrófono, y no se pueden empotrar: sus clientes web bloquean el iframe
 *   y sus SDK nativos exigen cuenta de organización. La llamada la atiende la
 *   app de ellos, que es la que la persona ya tiene instalada y con los
 *   permisos dados a ELLOS, no a Matcher.
 */

/**
 * Abre la reunión FUERA de Matcher.
 *
 * El orden importa y antes estaba mal. La primera versión usaba
 * `Browser.open`, que en Android es una Chrome Custom Tab: un navegador
 * empotrado adentro de la app. Ahí el link de Zoom cae en la web de Zoom en
 * vez de despertar la app de Zoom, y el comentario que decía "el sistema la
 * levanta él solo" era optimismo, no algo verificado.
 *
 * `AppLauncher.openUrl` manda un Intent común y silvestre: es el sistema
 * operativo el que resuelve quién abre ese link, así que si la app de Zoom,
 * Meet o Webex está instalada, la abre ella. Si no hay ninguna app que lo
 * reclame, se cae al navegador, que es exactamente lo que uno quiere.
 */
async function abrir(url) {
  if (!esNativo) {
    window.open(url, "_blank", "noopener,noreferrer");
    return;
  }
  try {
    const r = await AppLauncher.openUrl({ url });
    if (r?.completed) return;
  } catch {
    /* sin app que lo reclame: sigue el navegador */
  }
  try {
    await Browser.open({ url });
  } catch {
    window.open(url, "_blank", "noopener");
  }
}

export default function Videollamada({ matchId, nombre }) {
  const [datos, setDatos] = useState(null);
  const [abierto, setAbierto] = useState(false);
  const [proveedor, setProveedor] = useState("jitsi");
  const [enlace, setEnlace] = useState("");
  const [cuando, setCuando] = useState("");
  const [error, setError] = useState("");

  const cargar = () =>
    api
      .videollamada(matchId)
      .then(setDatos)
      .catch(() => setDatos(null));

  useEffect(() => {
    setAbierto(false);
    setError("");
    setEnlace("");
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matchId]);

  if (!datos) return null;

  const cat = datos.proveedores.find((p) => p.codigo === proveedor);
  const llamada = datos.llamada;

  const hacer = async (fn) => {
    setError("");
    try {
      await fn();
      await cargar();
      setAbierto(false);
      setEnlace("");
    } catch (e) {
      setError(e.message);
    }
  };

  // En una cita a ciegas sin revelar el servidor dice que no y por qué. Se
  // muestra el motivo en vez de esconder el botón: si desaparece sin más, la
  // función parece rota.
  if (!datos.disponible) {
    return (
      <div className="videollamada videollamada-trabada">
        <IcoVideo tam={17} />
        <span>{datos.motivo}</span>
      </div>
    );
  }

  if (llamada?.estado === "aceptada") {
    return (
      <div className="videollamada videollamada-lista">
        <div className="videollamada-cabeza">
          <IcoVideo tam={17} />
          <b>{t("Videollamada acordada")}</b>
          <span className="insignia insignia-auto insignia-proveedor">
            <LogoProveedor codigo={llamada.proveedor} tam={14} />
            {llamada.proveedor_nombre}
          </span>
        </div>
        {llamada.cuando && <p className="videollamada-cuando">{llamada.cuando}</p>}
        <p className="videollamada-nota">
          {t("Se abre en la app de")} {llamada.proveedor_nombre}{" "}
          {t("si la tenés instalada; si no, en el navegador.")}
        </p>
        <div className="videollamada-acciones">
          <button className="btn btn-primario" onClick={() => abrir(llamada.enlace)}>
            {t("Abrir la llamada")} ↗
          </button>
          <button
            className="btn btn-fantasma"
            onClick={() => hacer(() => api.cancelarVideollamada(llamada.id))}
          >
            {t("Cancelar")}
          </button>
        </div>
        {error && <div className="aviso aviso-error">{error}</div>}
      </div>
    );
  }

  if (llamada?.estado === "pendiente") {
    return (
      <div className="videollamada">
        <div className="videollamada-cabeza">
          <IcoVideo tam={17} />
          <b>
            {llamada.mia
              ? t("Propusiste una videollamada")
              : `${nombre} ${t("te propone una videollamada")}`}
          </b>
          <span className="insignia insignia-auto insignia-proveedor">
            <LogoProveedor codigo={llamada.proveedor} tam={14} />
            {llamada.proveedor_nombre}
          </span>
        </div>
        {llamada.cuando && <p className="videollamada-cuando">{llamada.cuando}</p>}
        <p className="videollamada-nota">
          {llamada.mia
            ? t("El link aparece cuando la otra persona acepta.")
            : t("Si aceptás, el link se abre para los dos.")}
        </p>
        <div className="videollamada-acciones">
          {!llamada.mia && (
            <>
              <button
                className="btn btn-primario"
                onClick={() => hacer(() => api.responderVideollamada(llamada.id, true))}
              >
                {t("Aceptar")}
              </button>
              <button
                className="btn"
                onClick={() => hacer(() => api.responderVideollamada(llamada.id, false))}
              >
                {t("Ahora no")}
              </button>
            </>
          )}
          {llamada.mia && (
            <button
              className="btn btn-fantasma"
              onClick={() => hacer(() => api.cancelarVideollamada(llamada.id))}
            >
              {t("Cancelar propuesta")}
            </button>
          )}
        </div>
        {error && <div className="aviso aviso-error">{error}</div>}
      </div>
    );
  }

  return (
    <div className="videollamada">
      {!abierto && (
        <button className="videollamada-abrir" onClick={() => setAbierto(true)}>
          <IcoVideo tam={17} />
          <span>{t("Proponer videollamada")}</span>
        </button>
      )}
      {abierto && (
        <>
          <div className="videollamada-cabeza">
            <IcoVideo tam={17} />
            <b>{t("Videollamada antes de verse")}</b>
          </div>
          <div className="videollamada-proveedores">
            {datos.proveedores.map((p) => (
              <button
                key={p.codigo}
                className={`chip chip-proveedor ${p.codigo === proveedor ? "on" : ""}`}
                onClick={() => {
                  setProveedor(p.codigo);
                  setEnlace("");
                  setError("");
                }}
              >
                <LogoProveedor codigo={p.codigo} />
                {p.nombre}
              </button>
            ))}
          </div>
          {/* La nota del proveedor sale del servidor y dice la verdad: Jitsi lo
              crea Matcher; Meet, Zoom y Webex hay que crearlos en la cuenta de
              uno. Prometer una sala de Meet que la app no puede crear sería
              exactamente lo que la regla 10 prohíbe. */}
          <p className="videollamada-nota">{cat?.nota}</p>
          {cat && !cat.crea_sala && (
            <input
              value={enlace}
              onChange={(e) => setEnlace(e.target.value)}
              placeholder={`https://${cat.dominios[0]}/…`}
              inputMode="url"
              autoCapitalize="off"
              autoCorrect="off"
            />
          )}
          <input
            value={cuando}
            onChange={(e) => setCuando(e.target.value)}
            placeholder={t("¿Cuándo? (opcional) — ej: hoy 21:00")}
            maxLength={60}
          />
          <div className="videollamada-acciones">
            <button
              className="btn btn-primario"
              onClick={() =>
                hacer(() =>
                  api.proponerVideollamada(matchId, proveedor, enlace.trim(), cuando.trim())
                )
              }
            >
              {t("Proponer")}
            </button>
            <button className="btn btn-fantasma" onClick={() => setAbierto(false)}>
              {t("Cerrar")}
            </button>
          </div>
        </>
      )}
      {error && <div className="aviso aviso-error">{error}</div>}
    </div>
  );
}
