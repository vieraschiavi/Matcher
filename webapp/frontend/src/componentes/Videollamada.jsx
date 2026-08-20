import { useEffect, useState } from "react";
import { Browser } from "@capacitor/browser";

import { api, esNativo } from "../api";
import { IcoVideo } from "../Iconos";
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
 *   y micrófono, y un WebView embebido o los rechaza o los concede con un
 *   permiso que el usuario le dio a Matcher, no a Zoom. Se abre el navegador
 *   del sistema (o la app de Zoom/Meet si está instalada, que es lo que hace
 *   el sistema operativo con esos links).
 */
function abrir(url) {
  if (esNativo) {
    // `Browser.open` en la app = Chrome Custom Tab / SFSafariViewController.
    // Si el teléfono tiene la app de Zoom o Meet instalada, el sistema la
    // levanta él solo con ese link.
    Browser.open({ url }).catch(() => window.open(url, "_blank", "noopener"));
    return;
  }
  window.open(url, "_blank", "noopener,noreferrer");
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
          <span className="insignia insignia-auto">{llamada.proveedor_nombre}</span>
        </div>
        {llamada.cuando && <p className="videollamada-cuando">{llamada.cuando}</p>}
        <div className="videollamada-acciones">
          <button className="btn btn-primario" onClick={() => abrir(llamada.enlace)}>
            {t("Entrar a la llamada")}
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
          <span className="insignia insignia-auto">{llamada.proveedor_nombre}</span>
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
                className={`chip ${p.codigo === proveedor ? "on" : ""}`}
                onClick={() => {
                  setProveedor(p.codigo);
                  setEnlace("");
                  setError("");
                }}
              >
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
