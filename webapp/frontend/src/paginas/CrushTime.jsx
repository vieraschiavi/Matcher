import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ErrorApi } from "../api";
import { festejarMatch } from "../avisos";
import { useApp } from "../estado";
import { t } from "../i18n";
import { IcoCorazon, IcoDiana } from "../Iconos";

// Crush Time: cuatro caras, una te dio like, adiviná cuál.
//
// Las reglas de verdad viven en el motor (`matcher/crushtime.py`): acá no hay
// ninguna pista de quién es el objetivo porque el payload no la trae — no es
// que la escondemos, es que no viaja (regla 8). Acertar crea el match en el
// acto: la otra persona ya había dicho que sí.
export default function CrushTime() {
  const navegar = useNavigate();
  const { perfil } = useApp();
  const [estado, setEstado] = useState(null);
  const [ronda, setRonda] = useState(null);
  const [resultado, setResultado] = useState(null); // {acierto, con?, match_id?}
  const [elegida, setElegida] = useState(null);
  const [aviso, setAviso] = useState("");
  const [muro, setMuro] = useState(false);

  const cargarEstado = () => api.crushtime().then(setEstado).catch(() => setEstado(null));
  useEffect(() => {
    cargarEstado();
  }, []);

  const jugar = async () => {
    setAviso("");
    setResultado(null);
    setElegida(null);
    try {
      const r = await api.crushtimeRonda();
      setRonda(r);
    } catch (e) {
      if (e instanceof ErrorApi && e.sinCupo) setMuro(true);
      else setAviso(e.message);
    }
  };

  const adivinar = async (id) => {
    if (elegida || !ronda) return; // una sola elección por ronda
    setElegida(id);
    try {
      const r = await api.crushtimeAdivinar(ronda.ronda, id);
      setResultado(r);
      if (r.acierto) {
        // El fuego también acá: acertar en el juego es un match de verdad.
        festejarMatch({ ...r, compatibilidad: r.con?.compatibilidad });
      } else {
        try { navigator.vibrate?.(60); } catch { /* sin vibrador */ }
      }
      cargarEstado();
    } catch (e) {
      setAviso(e.message);
      setElegida(null);
    }
  };

  const cerrarRonda = () => {
    setRonda(null);
    setResultado(null);
    setElegida(null);
  };

  return (
    <>
      <h1 className="page-title">Crush Time</h1>
      <p className="page-sub">
        {t("Cuatro caras. Una te dio like. Si adivinás cuál, es match instantáneo.")}{" "}
        {estado && (
          <b>
            {t("Turnos de hoy")}: {estado.turnos_restantes}/{estado.turnos_max}
          </b>
        )}
      </p>

      {aviso && <div className="aviso aviso-info" style={{ marginBottom: 14 }}>{aviso}</div>}

      {!ronda && (
        <div className="panel crush-portada">
          <span className="crush-icono"><IcoDiana tam={40} /></span>
          <h3>{t("¿Quién te dio like?")}</h3>
          <p>
            {t("Siempre hay al menos una persona que te dio like en la ronda. Errar no la revela: seguí jugando.")}
          </p>
          <button
            className="btn btn-primario btn-bloque"
            onClick={jugar}
            disabled={estado?.turnos_restantes === 0 && !estado?.ronda_pendiente}
          >
            {estado?.ronda_pendiente ? t("Seguir la ronda") : t("Jugar")}
          </button>
          {estado?.turnos_restantes === 0 && !estado?.ronda_pendiente && (
            <p className="crush-agotado">
              {t("Se acabaron los turnos de hoy.")}{" "}
              {perfil?.plan === "gratis" && t("Con Plus tenés 5 por día.")}
            </p>
          )}
        </div>
      )}

      {ronda && (
        <div className="crush-grilla">
          {ronda.caras.map((c) => {
            const esElegida = elegida === c.id;
            const acierto = resultado?.acierto && esElegida;
            const error = resultado && !resultado.acierto && esElegida;
            return (
              <button
                key={c.id}
                className={`crush-carta ${acierto ? "acierto" : ""} ${error ? "error" : ""}`}
                onClick={() => adivinar(c.id)}
                disabled={!!resultado}
              >
                <img src={c.fotos?.[0]?.url} alt={`Foto de ${c.nombre}`} />
                <div className="crush-nombre">
                  {c.nombre}, {c.edad}
                </div>
                {acierto && <span className="crush-sello acierto"><IcoCorazon tam={26} relleno /></span>}
                {error && <span className="crush-sello error">✕</span>}
              </button>
            );
          })}
        </div>
      )}

      {resultado && (
        <div className="panel crush-resultado">
          {resultado.acierto ? (
            <>
              <h3>{t("¡Acertaste! Es un match")}</h3>
              <div style={{ display: "flex", gap: 9, marginTop: 10 }}>
                <button className="btn btn-bloque" onClick={cerrarRonda}>
                  {t("Otra ronda")}
                </button>
                <button
                  className="btn btn-primario btn-bloque"
                  onClick={() => navegar(`/matches/${resultado.match_id}`)}
                >
                  {t("Mandar mensaje")}
                </button>
              </div>
            </>
          ) : (
            <>
              <h3>{t("No era")}</h3>
              <p style={{ color: "var(--muted)", margin: "4px 0 10px" }}>
                {t("No te decimos quién fue: su like sigue pendiente y puede volver a aparecer.")}{" "}
                {estado && `${t("Turnos de hoy")}: ${estado.turnos_restantes}/${estado.turnos_max}.`}
              </p>
              <button className="btn btn-primario btn-bloque" onClick={cerrarRonda}>
                {estado?.turnos_restantes > 0 ? t("Otra ronda") : t("Listo por hoy")}
              </button>
            </>
          )}
        </div>
      )}

      {muro && (
        <div className="velo-modal" onClick={() => setMuro(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>{t("Se acabaron los turnos de hoy.")}</h2>
            <p style={{ color: "var(--muted)" }}>
              {t("Con Plus tenés 5 por día.")}
            </p>
            <button className="btn btn-primario btn-bloque" onClick={() => navegar("/planes")}>
              {t("Ver planes")}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
