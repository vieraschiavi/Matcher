import { useCallback, useEffect, useState } from "react";
import { t } from "../i18n";
import { ErrorApi, api } from "../api";
import { avisar, festejarMatch } from "../avisos";
import { useNavigate } from "react-router-dom";
import { useApp } from "../estado";
import { preferenciasEfectivas, soloPermitidos } from "../filtroCliente";
import { IcoPin, IcoTrofeo } from "../Iconos";

// Cuatro formas de encontrar gente sin swipear. Van juntas y no en pantallas
// separadas por una razón de navegación, no de código: la barra de arriba del
// teléfono ya tiene cuatro botones y en 360 dp no entra un quinto sin que el
// logo se parta. Son las tres "vitrinas" de la app, así que comparten sección.
//
// La primera pestaña es "Disponibles" a propósito: es la de más intención
// —la otra persona ya dijo que quiere salir— y por eso es la que conviene que
// aparezca al abrir.
//
// Los nombres cortos de las pestañas no son sólo por espacio. La primera
// versión decía "Disponible hoy" y "Los de hoy", que además de partirse en dos
// renglones a 390 px se confundían entre sí: una es "quién sale hoy" y la otra
// "a quién likearon hoy", que no tienen nada que ver. El texto largo que las
// explica quedó abajo de cada pestaña, donde hay lugar.
const ALCANCES = [
  { id: "barrio", texto: "Mi barrio" },
  { id: "ciudad", texto: "Mi ciudad" },
  { id: "mundo", texto: "El mundo" },
];

export default function Ranking() {
  const { perfil } = useApp();
  const navegar = useNavigate();
  const [pestana, setPestana] = useState("disponibles");
  const [top, setTop] = useState([]);
  const [hoy, setHoy] = useState(null);
  const [disponibles, setDisponibles] = useState(null);
  const [alcance, setAlcance] = useState("ciudad");
  const [likeados, setLikeados] = useState(null);
  const [revancha, setRevancha] = useState(null);
  const [sugerencias, setSugerencias] = useState(null);

  const permitidas = preferenciasEfectivas(perfil?.preferencias);

  const cargarHoy = useCallback(
    () =>
      api
        .topDia()
        .then((r) => setHoy(soloPermitidos(permitidas, r.top)))
        .catch(() => setHoy([])),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  const cargarDisponibles = useCallback(
    () =>
      api
        .disponibles()
        .then((r) => setDisponibles({ ...r, personas: soloPermitidos(permitidas, r.personas) }))
        .catch(() => setDisponibles({ total: 0, personas: [] })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  // Cinturón y tiradores del filtro duro en las tres listas (ver
  // filtroCliente.js): el servidor ya filtra, esto cubre el caso serverless.
  const cargarLikeados = useCallback(
    (cual) =>
      api
        .masLikeados(cual, 200)
        .then((r) => setLikeados({ ...r, top: soloPermitidos(permitidas, r.top) }))
        .catch(() => setLikeados({ alcance: cual, total: 0, top: [] })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  useEffect(() => {
    cargarDisponibles();
    cargarHoy();
    api
      .ranking(25)
      .then((r) => setTop(soloPermitidos(permitidas, r.top)))
      .catch(() => setTop([]));
    api.sugerenciasAuto().then(setSugerencias).catch(() => setSugerencias(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const cargarRevancha = useCallback(
    () =>
      api
        .segundaVuelta()
        .then((r) => setRevancha({ ...r, personas: soloPermitidos(permitidas, r.personas) }))
        .catch(() => setRevancha({ dias_espera: 7, personas: [] })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  useEffect(() => {
    if (pestana === "likeados") {
      setLikeados(null);
      cargarLikeados(alcance);
    }
    if (pestana === "revancha" && revancha === null) cargarRevancha();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pestana, alcance]);

  // Repescar no es un like común: primero borra el descarte viejo. Si sale un
  // match, la persona que descartaste hace semanas te había dicho que sí — el
  // mejor final posible de esta pantalla, y se festeja igual que cualquiera.
  const darRevancha = async (id) => {
    try {
      const r = await api.repescar(id);
      if (r.match) festejarMatch(r);
      else avisar(t("Segunda oportunidad enviada"), { tipo: "ok", vibrar: 15 });
      cargarRevancha();
    } catch (e) {
      if (e instanceof ErrorApi && e.sinCupo) navegar("/planes");
      else avisar(e.message, { tipo: "error" });
    }
  };

  const darLike = async (id, recargar) => {
    try {
      const r = await api.interactuar(id, "like");
      if (r.match) festejarMatch(r);
      else avisar("Like enviado", { tipo: "ok", vibrar: 15 });
      recargar();
    } catch (e) {
      if (e instanceof ErrorApi && e.sinCupo) navegar("/planes");
    }
  };

  return (
    <>
      <h1 className="page-title">{t("Explorar")}</h1>
      <p className="page-sub">
        {t("Cuatro formas de encontrar gente sin deslizar. Todas respetan tus filtros.")}
      </p>

      <div className="pestanas pestanas-tres">
        <button
          className={pestana === "disponibles" ? "on" : ""}
          onClick={() => setPestana("disponibles")}
        >
          {t("Disponibles")}
        </button>
        <button className={pestana === "hoy" ? "on" : ""} onClick={() => setPestana("hoy")}>
          {t("Top del día")}
        </button>
        <button
          className={pestana === "likeados" ? "on" : ""}
          onClick={() => setPestana("likeados")}
        >
          {t("Top por zona")}
        </button>
        <button
          className={pestana === "revancha" ? "on" : ""}
          onClick={() => setPestana("revancha")}
        >
          {t("2ª vuelta")}
        </button>
      </div>

      {/* ---------------- Segunda vuelta ---------------- */}
      {pestana === "revancha" && (
        <>
          <p className="page-sub" style={{ marginTop: 12 }}>
            {t("La gente que descartaste hace más de una semana y que hoy pasa tus filtros. El descarte con el pulgar en piloto automático no es una opinión: acá tenés la segunda mirada. Nadie se entera de que lo descartaste.")}
          </p>
          {revancha === null && <div className="esqueleto" style={{ height: 180 }} />}
          {revancha?.personas.length === 0 && (
            <div className="panel">
              <p style={{ color: "var(--muted)", margin: 0 }}>
                {t("No hay descartes viejos que pasen tus filtros. Los descartes entran acá a los 7 días.")}
              </p>
            </div>
          )}
          <div className="grid grid-3">
            {revancha?.personas.map((p) => (
              <div key={p.id} className="panel" style={{ padding: 0, overflow: "hidden" }}>
                <img
                  src={p.fotos?.[0]?.url}
                  alt=""
                  className="foto-persona"
                />
                <div style={{ padding: 13 }}>
                  <b>
                    {p.nombre}, {p.edad}
                  </b>
                  <div style={{ display: "flex", gap: 6, marginTop: 7, flexWrap: "wrap" }}>
                    <span className="insignia insignia-auto">
                      {t("hace")} {p.hace_dias} {t("días")}
                    </span>
                    <span className="insignia insignia-comp">{p.compatibilidad}%</span>
                    {p.sintetico && <span className="insignia insignia-sint">Sintético</span>}
                  </div>
                  <button
                    className="btn btn-primario btn-bloque"
                    style={{ marginTop: 10 }}
                    onClick={() => darRevancha(p.id)}
                  >
                    {t("Dar otra oportunidad")}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* ---------------- Disponible hoy ---------------- */}
      {pestana === "disponibles" && (
        <>
          <p className="page-sub" style={{ marginTop: 12 }}>
            {t("Gente que marcó que sale hoy. Vence a las 24 horas: si figura acá, es de hoy.")}{" "}
            {!perfil?.disponible_hoy && (
              <button className="enlace-boton" onClick={() => navegar("/perfil")}>
                {t("Marcarme disponible")}
              </button>
            )}
          </p>
          {disponibles === null && <div className="esqueleto" style={{ height: 180 }} />}
          {disponibles?.personas.length === 0 && (
            <div className="panel">
              <p style={{ color: "var(--muted)", margin: 0 }}>
                {t("Todavía nadie que pase tus filtros marcó disponible hoy. Se llena sobre la tarde.")}
              </p>
            </div>
          )}
          <div className="grid grid-3">
            {disponibles?.personas.map((p) => (
              <div key={p.id} className="panel" style={{ padding: 0, overflow: "hidden" }}>
                <img
                  src={p.fotos?.[0]?.url}
                  alt=""
                  className="foto-persona"
                />
                <div style={{ padding: 13 }}>
                  <b>
                    {p.nombre}, {p.edad}
                  </b>
                  <div style={{ display: "flex", gap: 6, marginTop: 7, flexWrap: "wrap" }}>
                    <span className="insignia insignia-hoy">{t("Disponible hoy")}</span>
                    {p.distancia_km != null && (
                      <span className="insignia">
                        <IcoPin tam={12} /> {p.distancia_km} km
                      </span>
                    )}
                    <span className="insignia insignia-comp">{p.compatibilidad}%</span>
                    {p.sintetico && <span className="insignia insignia-sint">Sintético</span>}
                  </div>
                  <button
                    className="btn btn-primario btn-bloque"
                    style={{ marginTop: 10 }}
                    onClick={() => darLike(p.id, cargarDisponibles)}
                  >
                    {t("Dar like")}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* ---------------- Los más likeados de hoy ---------------- */}
      {pestana === "hoy" && (
        <>
          <p className="page-sub" style={{ marginTop: 12 }}>
            {t("Los más likeados de hoy que pasan tus filtros. Todavía no les respondiste: dales like desde acá.")}
          </p>
          {hoy === null && <div className="esqueleto" style={{ height: 180 }} />}
          {hoy?.length === 0 && (
            <p style={{ color: "var(--muted)" }}>{t("Hoy todavía no hay votados que pasen tus filtros.")}</p>
          )}
          <div className="grid grid-3">
            {hoy?.map((p) => (
              <div key={p.id} className="panel" style={{ padding: 0, overflow: "hidden" }}>
                <img
                  src={p.fotos?.[0]?.url}
                  alt=""
                  className="foto-persona"
                />
                <div style={{ padding: 13 }}>
                  <b>
                    {p.nombre}, {p.edad}
                  </b>
                  <div style={{ display: "flex", gap: 6, marginTop: 7, flexWrap: "wrap" }}>
                    <span className="insignia insignia-oro">{p.likes_hoy} likes hoy</span>
                    <span className="insignia insignia-comp">{p.compatibilidad}%</span>
                    {p.sintetico && <span className="insignia insignia-sint">Sintético</span>}
                  </div>
                  <button
                    className="btn btn-primario btn-bloque"
                    style={{ marginTop: 10 }}
                    onClick={() => darLike(p.id, cargarHoy)}
                  >
                    {t("Dar like")}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* ---------------- Más likeados por zona ---------------- */}
      {pestana === "likeados" && (
        <>
          <div className="pestanas pestanas-tres" style={{ marginTop: 12 }}>
            {ALCANCES.map((a) => (
              <button
                key={a.id}
                className={alcance === a.id ? "on" : ""}
                onClick={() => setAlcance(a.id)}
              >
                {t(a.texto)}
              </button>
            ))}
          </div>

          <p className="page-sub" style={{ marginTop: 10 }}>
            {alcance === "barrio" &&
              t("Los 200 más likeados a menos de 2 km tuyo. No usamos el nombre del barrio: usamos tu última ubicación, que es dato que la app ya tiene.")}
            {alcance === "ciudad" &&
              (likeados?.ciudad
                ? `${t("Los 200 más likeados de")} ${likeados.ciudad}.`
                : t("Los 200 más likeados de tu ciudad."))}
            {alcance === "mundo" && t("Los 200 más likeados de todo Matcher.")}{" "}
            {t("El puntaje es la tasa de likes suavizada, no el total: un perfil con 3 likes en 4 vistas no le gana a uno con 300 en 1.200.")}
          </p>

          {likeados === null && <div className="esqueleto" style={{ height: 220 }} />}

          {likeados?.top.length === 0 && (
            <div className="panel">
              <p style={{ color: "var(--muted)", margin: 0 }}>
                {alcance === "barrio"
                  ? t("No hay nadie en tu barrio todavía, o el teléfono no compartió ubicación. Probá con tu ciudad.")
                  : t("Nadie que pase tus filtros en este alcance.")}
              </p>
            </div>
          )}

          {likeados?.top.length > 0 && (
            <div className="panel">
              <div style={{ overflowX: "auto" }}>
                <table className="tabla">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th></th>
                      <th>{t("Perfil")}</th>
                      {/* En un teléfono no entran seis columnas: la tabla
                          quedaba con el encabezado cortado a la mitad
                          ("POPULARIDA") y las dos últimas fuera de pantalla.
                          Se esconden las secundarias y el dato que importa
                          —los likes— pasa a viajar abajo del nombre. */}
                      <th className="col-ancha">{t("Popularidad")}</th>
                      <th className="tnum col-ancha">Likes</th>
                      <th className="tnum col-ancha">★</th>
                    </tr>
                  </thead>
                  <tbody>
                    {likeados.top.map((p) => (
                      <tr key={p.id}>
                        {/* El puesto viene del servidor. Si lo numerara el
                            cliente con el índice, al sacar a alguien por el
                            filtro toda la tabla se correría un lugar y el #7
                            pasaría a #6 sin haber subido. */}
                        <td className="tnum" style={{ color: "var(--muted)" }}>
                          {p.puesto}
                        </td>
                        <td>
                          <img className="mini-foto" src={p.portada} alt="" />
                        </td>
                        <td>
                          <b>{p.nombre}</b>
                          <div style={{ display: "flex", gap: 5, marginTop: 3, flexWrap: "wrap" }}>
                            <span className="insignia solo-angosto">
                              {p.likes_recibidos} likes
                            </span>
                            {p.verificado && <span className="insignia insignia-verif">✓</span>}
                            {p.sintetico && <span className="insignia insignia-sint">Sintético</span>}
                          </div>
                        </td>
                        <td className="col-ancha">
                          <div className="barra">
                            <i style={{ width: `${p.popularidad}%` }} />
                          </div>
                          <span className="tnum" style={{ fontSize: 11.5, color: "var(--muted)" }}>
                            {p.popularidad}
                          </span>
                        </td>
                        <td className="tnum col-ancha">{p.likes_recibidos}</td>
                        <td className="tnum col-ancha">{p.superfans_recibidos}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="grid grid-2" style={{ alignItems: "start", marginTop: 16 }}>
            <div className="panel">
              <h3>
                <IcoTrofeo tam={17} /> {t("Ranking global")}
              </h3>
              <p style={{ color: "var(--muted)", fontSize: 12.5, marginTop: 0 }}>
                {t("Los 25 primeros de todo Matcher, para comparar contra tu zona.")}
              </p>
              <div style={{ overflowX: "auto" }}>
                <table className="tabla">
                  <tbody>
                    {top.map((p, i) => (
                      <tr key={p.id}>
                        <td className="tnum" style={{ color: "var(--muted)" }}>
                          {i + 1}
                        </td>
                        <td>
                          <img className="mini-foto" src={p.portada} alt="" />
                        </td>
                        <td>
                          <b>{p.nombre}</b>
                        </td>
                        <td className="tnum">{p.likes_recibidos}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="panel">
              <h3>{t("Tus candidatos a match automático")}</h3>
              <p style={{ color: "var(--muted)", fontSize: 12.5, marginTop: 0 }}>
                Umbral de compatibilidad: {sugerencias?.umbral ?? "—"}%. Sólo entran los que además
                te pasan a vos todos sus filtros.
              </p>
              {sugerencias?.sugerencias?.length === 0 && (
                <p style={{ color: "var(--muted)", fontSize: 13 }}>
                  Nadie supera el umbral ahora mismo. Es a propósito: bajarlo para llenar la lista
                  sería mentir sobre el porcentaje.
                </p>
              )}
              <div className="chat-lista">
                {sugerencias?.sugerencias?.map((s) => (
                  <div key={s.id} className="chat-fila">
                    <img src={s.fotos?.[0]?.url} alt="" />
                    <div className="chat-cuerpo">
                      <b>
                        {s.nombre}, {s.edad}
                      </b>
                      <span>{s.motivos.join(" · ") || "Compatibilidad alta"}</span>
                    </div>
                    <span className="insignia insignia-comp">{s.compatibilidad}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}
