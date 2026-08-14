import { useEffect, useState } from "react";
import { t } from "../i18n";
import { useParams } from "react-router-dom";
import { api } from "../api";
import { useApp } from "../estado";

export default function Planes() {
  const { perfil, refrescar } = useApp();
  const { referencia } = useParams();
  const [catalogo, setCatalogo] = useState(null);
  const [periodo, setPeriodo] = useState("mensual");
  const [pendiente, setPendiente] = useState(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [historial, setHistorial] = useState([]);

  useEffect(() => {
    // El catálogo de planes es público; el historial no. Si falla el
    // historial la pantalla igual tiene que mostrarse: antes cualquiera de
    // los dos la dejaba en "Cargando planes…" y no se podía ni ver el precio.
    api.planes().then(setCatalogo).catch((e) => setError(e.message));
    api.historialPagos().then((r) => setHistorial(r.pagos)).catch(() => setHistorial([]));
  }, [perfil?.plan]);

  // La pasarela demo redirige a /#/pago/<referencia>. Con una pasarela real,
  // acá llega el `return_url` y la confirmación de verdad la hace el webhook;
  // esta pantalla sólo muestra el resultado.
  useEffect(() => {
    if (referencia) setPendiente({ id: referencia });
  }, [referencia]);

  const comprar = async (codigo) => {
    setError("");
    setOk("");
    try {
      const r = await api.checkout(codigo, periodo);
      setPendiente(r.checkout);
    } catch (e) {
      setError(e.message);
    }
  };

  const confirmar = async () => {
    setError("");
    try {
      const r = await api.confirmarPago(pendiente.id);
      await refrescar();
      const p = await api.historialPagos();
      setHistorial(p.pagos);
      setPendiente(null);
      setOk(
        r.resultado.ya_confirmado
          ? "Ese pago ya estaba confirmado."
          : `Listo: ${r.resultado.plan.toUpperCase()} activo hasta ${new Date(
              r.resultado.vence
            ).toLocaleDateString()}.`
      );
    } catch (e) {
      setError(e.message);
    }
  };

  const cancelar = async () => {
    setError("");
    try {
      const r = await api.cancelarPlan();
      await refrescar();
      setOk(r.mensaje);
    } catch (e) {
      setError(e.message);
    }
  };

  if (!catalogo) {
    // Un error acá tiene que verse. Devolver siempre "Cargando planes…" es
    // lo que hacía parecer que el botón del plan pago "no hacía nada".
    return error ? (
      <div className="aviso aviso-error">No se pudieron cargar los planes: {error}</div>
    ) : (
      <p className="page-sub">{t("Cargando planes…")}</p>
    );
  }

  const referenciaMasCara = Math.max(
    ...catalogo.referencia_competencia.map((c) => c.precio_mes_aprox)
  );

  return (
    <>
      <h1 className="page-title">{t("Planes")}</h1>
      <p className="page-sub">
        Todos los filtros están en el plan gratis. Lo que se paga es volumen y visibilidad, no el
        derecho a filtrar por lo que te importa.
      </p>

      <div className="pestanas" style={{ maxWidth: 300 }}>
        <button className={periodo === "mensual" ? "on" : ""} onClick={() => setPeriodo("mensual")}>
          Mensual
        </button>
        {/* "Anual (más barato)" se partía en dos renglones dentro de la
            pestaña y descolocaba la fila entera. El ahorro va en una etiqueta
            aparte, que además se lee mejor que entre paréntesis. */}
        <button className={periodo === "anual" ? "on" : ""} onClick={() => setPeriodo("anual")}>
          Anual <span className="ahorro">−20%</span>
        </button>
      </div>

      <div className="grid grid-3" style={{ marginTop: 16 }}>
        {catalogo.planes.map((pl) => {
          const precio =
            pl.codigo === "gratis"
              ? 0
              : periodo === "anual"
                ? pl.precio_mes_en_anual
                : pl.precio_mes;
          const actual = (perfil.es_premium ? perfil.plan : "gratis") === pl.codigo;
          return (
            <div
              key={pl.codigo}
              className={`plan-tarjeta ${pl.codigo === "plus" ? "destacado" : ""}`}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <b style={{ fontSize: 16 }}>{pl.nombre}</b>
                {pl.codigo === "plus" && <span className="insignia insignia-comp">Elegido</span>}
                {actual && <span className="insignia insignia-oro">Tu plan</span>}
              </div>
              <div className="plan-precio">
                {precio === 0 ? (
                  "Gratis"
                ) : (
                  <>
                    {catalogo.moneda} {precio.toFixed(2)}
                    <small> /mes</small>
                  </>
                )}
              </div>
              {pl.codigo !== "gratis" && periodo === "anual" && (
                <div style={{ color: "var(--muted)", fontSize: 12.5 }}>
                  {catalogo.moneda} {pl.precio_anual.toFixed(2)} por año
                </div>
              )}
              <ul className="plan-lista">
                {pl.destacados.map((d) => (
                  <li key={d}>{d}</li>
                ))}
              </ul>
              <div style={{ marginTop: "auto" }}>
                {pl.codigo === "gratis" ? (
                  <button className="btn btn-bloque" disabled>
                    Incluido
                  </button>
                ) : actual ? (
                  <button className="btn btn-bloque" onClick={cancelar}>
                    No renovar
                  </button>
                ) : (
                  <button
                    className="btn btn-primario btn-bloque"
                    onClick={() => comprar(pl.codigo)}
                  >
                    Pasar a {pl.nombre}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-2" style={{ marginTop: 18, alignItems: "start" }}>
        <div className="panel">
          <h3>Comparación de precios</h3>
          <table className="tabla">
            <thead>
              <tr>
                <th>App</th>
                <th className="tnum">USD / mes</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <b>Matcher Plus</b>
                </td>
                <td className="tnum">
                  <b>{catalogo.planes[1].precio_mes.toFixed(2)}</b>
                </td>
              </tr>
              <tr>
                <td>
                  <b>Matcher Gold</b>
                </td>
                <td className="tnum">
                  <b>{catalogo.planes[2].precio_mes.toFixed(2)}</b>
                </td>
              </tr>
              {catalogo.referencia_competencia.map((c) => (
                <tr key={c.app}>
                  <td style={{ color: "var(--muted)" }}>{c.app}</td>
                  <td className="tnum" style={{ color: "var(--muted)" }}>
                    ≈ {c.precio_mes_aprox.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="aviso aviso-info" style={{ marginTop: 12 }}>
            {catalogo.aviso_referencia}
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12.5, marginBottom: 0 }}>
            Gold cuesta cerca de {Math.round((1 - catalogo.planes[2].precio_mes / referenciaMasCara) * 100)}
            % menos que el plan más caro de esa lista, tomando esos valores de referencia.
          </p>
        </div>

        <div className="panel">
          <h3>Tus pagos</h3>
          {historial.length === 0 && (
            <p style={{ color: "var(--muted)", fontSize: 13 }}>Todavía no hay movimientos.</p>
          )}
          {historial.length > 0 && (
            <table className="tabla">
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Plan</th>
                  <th className="tnum">Monto</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {historial.map((h) => (
                  <tr key={h.id}>
                    <td>{new Date(h.momento).toLocaleDateString()}</td>
                    <td>
                      {h.plan} · {h.periodo}
                    </td>
                    <td className="tnum">
                      {h.moneda} {h.monto.toFixed(2)}
                    </td>
                    <td>
                      <span
                        className={`insignia ${h.estado === "pagado" ? "insignia-comp" : "insignia-sint"}`}
                      >
                        {h.estado}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {error && (
        <div className="aviso aviso-error" style={{ marginTop: 16 }}>
          {error}
        </div>
      )}
      {ok && (
        <div className="aviso aviso-ok" style={{ marginTop: 16 }}>
          {ok}
        </div>
      )}

      {pendiente && (
        <div className="velo-modal" onClick={() => setPendiente(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Confirmar pago</h2>
            <div className="aviso aviso-info" style={{ textAlign: "left", marginBottom: 14 }}>
              Pasarela <b>demo</b>: no mueve plata y no pide datos de tarjeta. Con Stripe o Mercado
              Pago configurado, este paso es el checkout del proveedor y la confirmación llega por
              webhook.
            </div>
            <p style={{ color: "var(--muted)", fontSize: 13 }}>
              Referencia <code>{pendiente.id}</code>
            </p>
            <div style={{ display: "flex", gap: 9 }}>
              <button className="btn btn-bloque" onClick={() => setPendiente(null)}>
                Cancelar
              </button>
              <button className="btn btn-primario btn-bloque" onClick={confirmar}>
                Confirmar
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
