import { useRef, useState } from "react";
import { IDIOMAS, t } from "../i18n";
import { api, duracionVideo, leerArchivo } from "../api";
import Camara from "../componentes/Camara";
import { useApp } from "../estado";
import { INTENCIONES, alternar } from "../vocabulario";

export default function MiPerfil() {
  const { perfil, catalogos, refrescar, aplicarPerfil, lang, cambiarIdioma } = useApp();
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [borrador, setBorrador] = useState(null);
  const [camara, setCamara] = useState(null); // "foto" | "video" | null
  const inputFoto = useRef(null);
  const inputVideo = useRef(null);

  if (!perfil || !catalogos) return <p className="page-sub">{t("Cargando…")}</p>;

  const p = borrador || {
    nombre: perfil.nombre,
    bio: perfil.bio,
    altura_cm: perfil.altura_cm,
    pais: perfil.pais,
    ciudad: perfil.ciudad,
    politica: perfil.politica,
    equipo: perfil.equipo,
    intereses: perfil.intereses,
    intenciones: perfil.intenciones.filter((i) => i !== "disponible_hoy"),
  };
  const paisSel = catalogos.paises.find((x) => x.codigo === p.pais);
  const set = (k, v) => {
    setBorrador({ ...p, [k]: v });
    setOk("");
  };

  const guardar = async () => {
    setError("");
    try {
      await api.editar(p);
      await refrescar();
      setBorrador(null);
      setOk("Perfil actualizado.");
    } catch (e) {
      setError(e.message);
    }
  };

  const subirFotos = async (ev) => {
    setError("");
    // Se sube de a una y en orden: el backend valida el tope de 10 por
    // llamada, así que mandarlas en paralelo hace que el error caiga en una
    // foto al azar y el usuario no entiende cuál falló.
    for (const archivo of [...ev.target.files]) {
      try {
        const { url, bytes } = await leerArchivo(archivo);
        const r = await api.subirFoto(url, bytes);
        aplicarPerfil(r.perfil);
      } catch (e) {
        setError(e.message);
        break;
      }
    }
    ev.target.value = "";
  };

  const subirVideos = async (ev) => {
    setError("");
    for (const archivo of [...ev.target.files]) {
      try {
        const segundos = await duracionVideo(archivo);
        if (segundos && segundos > catalogos.limites.segundos_video) {
          setError(
            `"${archivo.name}" dura ${Math.round(segundos)} s y el máximo son ${catalogos.limites.segundos_video} s.`
          );
          break;
        }
        const { url, bytes } = await leerArchivo(archivo);
        const r = await api.subirVideo(url, segundos, bytes);
        aplicarPerfil(r.perfil);
      } catch (e) {
        setError(e.message);
        break;
      }
    }
    ev.target.value = "";
  };

  // El borrado usa el perfil que DEVUELVE el DELETE, no una relectura: la
  // relectura podía caer en otra instancia con estado viejo y en pantalla
  // "desaparecía" otra foto que la que se tocó. Y se confirma antes: en un
  // teléfono el dedo pifia, y una foto borrada no se recupera.
  const quitar = async (id) => {
    if (!window.confirm(t("¿Borrar esta foto o video? No se puede deshacer."))) return;
    setError("");
    try {
      const r = await api.borrarMedia(id);
      aplicarPerfil(r.perfil);
    } catch (e) {
      setError(e.message);
    }
  };

  // Lo que devuelve la cámara ({url, bytes[, segundos]}) es exactamente lo
  // mismo que produce `leerArchivo` sobre un archivo subido: el resto del
  // flujo (validar tope, llamar a la API, refrescar) no se bifurca.
  const fotoDeCamara = async ({ url, bytes }) => {
    setCamara(null);
    setError("");
    try {
      const r = await api.subirFoto(url, bytes);
      aplicarPerfil(r.perfil);
    } catch (e) {
      setError(e.message);
    }
  };

  const videoDeCamara = async ({ url, bytes, segundos }) => {
    setCamara(null);
    setError("");
    try {
      const r = await api.subirVideo(url, segundos, bytes);
      aplicarPerfil(r.perfil);
    } catch (e) {
      setError(e.message);
    }
  };

  const hacerPortada = async (id) => {
    const orden = [id, ...perfil.fotos.filter((f) => f.id !== id).map((f) => f.id)];
    const r = await api.ordenarMedios(orden);
    aplicarPerfil(r.perfil);
  };

  const libresFoto = catalogos.limites.fotos - perfil.fotos.length;
  const libresVideo = catalogos.limites.videos - perfil.videos.length;

  return (
    <>
      <h1 className="page-title">{t("Mi perfil")}</h1>
      <p className="page-sub">
        Hasta {catalogos.limites.fotos} fotos y {catalogos.limites.videos} videos de{" "}
        {catalogos.limites.segundos_video} segundos. La primera foto es la portada: es lo único que
        se ve antes de que alguien decida deslizar.
      </p>

      {/* El idioma se elige solo por el país, pero tiene que poder corregirse:
          hay brasileños en Uruguay y uruguayos en Miami, y adivinarle el
          idioma a alguien sin dejarlo cambiarlo es peor que no adivinar. */}
      <div className="panel" style={{ marginBottom: 16 }}>
        <h3>{t("Idioma")}</h3>
        <div className="chips">
          {IDIOMAS.map((i) => (
            <button
              key={i.codigo}
              type="button"
              className={`chip ${lang === i.codigo ? "on" : ""}`}
              onClick={() => cambiarIdioma(i.codigo)}
            >
              {i.nombre}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-2" style={{ alignItems: "start" }}>
        <div className="panel">
          <h3>
            Fotos ({perfil.fotos.length}/{catalogos.limites.fotos})
          </h3>
          <div className="galeria">
            {perfil.fotos.map((f, i) => (
              <figure key={f.id} className={i === 0 ? "portada" : ""}>
                <img src={f.url} alt="" onClick={() => hacerPortada(f.id)} />
                <button className="quitar" onClick={() => quitar(f.id)} title="Quitar">
                  ✕
                </button>
              </figure>
            ))}
            {libresFoto > 0 && (
              <>
                <figure className="camara-boton" onClick={() => setCamara("foto")}>
                  <span>📷</span>
                  <span>Sacar foto</span>
                </figure>
                <figure className="vacio" onClick={() => inputFoto.current.click()}>
                  +
                </figure>
              </>
            )}
          </div>
          <input
            ref={inputFoto}
            type="file"
            accept="image/*"
            multiple
            hidden
            onChange={subirFotos}
          />
          <p style={{ color: "var(--faint)", fontSize: 12, marginBottom: 0 }}>
            Tocá una foto para hacerla portada. Quedan {libresFoto} lugares.
          </p>
        </div>

        <div className="panel">
          <h3>
            Videos ({perfil.videos.length}/{catalogos.limites.videos})
          </h3>
          <div className="galeria">
            {perfil.videos.map((v) => (
              <figure key={v.id}>
                <video src={v.url} muted loop playsInline />
                <button className="quitar" onClick={() => quitar(v.id)}>
                  ✕
                </button>
              </figure>
            ))}
            {libresVideo > 0 && (
              <>
                <figure className="camara-boton" onClick={() => setCamara("video")}>
                  <span>🎥</span>
                  <span>Grabar</span>
                </figure>
                <figure className="vacio" onClick={() => inputVideo.current.click()}>
                  +
                </figure>
              </>
            )}
          </div>
          <input
            ref={inputVideo}
            type="file"
            accept="video/*"
            multiple
            hidden
            onChange={subirVideos}
          />
          <p style={{ color: "var(--faint)", fontSize: 12, marginBottom: 0 }}>
            Los perfiles con video reciben bastantes más respuestas que los que sólo tienen fotos.
          </p>
        </div>

        <div className="panel">
          <h3>Vos</h3>
          <label className="campo">
            <span>Nombre</span>
            <input value={p.nombre} onChange={(e) => set("nombre", e.target.value)} />
          </label>
          <label className="campo">
            <span>Bio</span>
            <textarea
              value={p.bio}
              maxLength={500}
              onChange={(e) => set("bio", e.target.value)}
              placeholder="Una línea que dé pie a una respuesta."
            />
          </label>
          <div className="fila">
            <label className="campo">
              <span>Altura (cm)</span>
              <input
                type="number"
                min={130}
                max={230}
                value={p.altura_cm}
                onChange={(e) => set("altura_cm", Number(e.target.value))}
              />
            </label>
            <label className="campo">
              <span>Postura política</span>
              <select value={p.politica} onChange={(e) => set("politica", e.target.value)}>
                <option value="izquierda">Izquierda</option>
                <option value="derecha">Derecha</option>
                <option value="neutro">Neutro</option>
              </select>
            </label>
          </div>
        </div>

        <div className="panel">
          <h3>Dónde estás</h3>
          <div className="fila">
            <label className="campo">
              <span>País</span>
              <select
                value={p.pais}
                onChange={(e) => {
                  const nuevo = catalogos.paises.find((x) => x.codigo === e.target.value);
                  // Cambiar de país invalida el equipo: los catálogos son por
                  // país y dejar "Peñarol" en un perfil de México rompe el
                  // filtro de equipo del otro lado.
                  setBorrador({
                    ...p,
                    pais: e.target.value,
                    ciudad: nuevo?.ciudades[0]?.id || "",
                    equipo: "",
                  });
                }}
              >
                {catalogos.paises.map((x) => (
                  <option key={x.codigo} value={x.codigo}>
                    {x.nombre}
                  </option>
                ))}
              </select>
            </label>
            <label className="campo">
              <span>Ciudad</span>
              <select value={p.ciudad} onChange={(e) => set("ciudad", e.target.value)}>
                {paisSel?.ciudades.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nombre}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label className="campo">
            <span>Equipo de {paisSel?.nombre}</span>
            <select value={p.equipo} onChange={(e) => set("equipo", e.target.value)}>
              <option value="">No me interesa el fútbol</option>
              {paisSel?.equipos.map((e) => (
                <option key={e} value={e}>
                  {e}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="panel">
          <h3>¿Qué buscás?</h3>
          <p style={{ color: "var(--muted)", fontSize: 12.5, marginTop: 0 }}>
            Se muestra en tu tarjeta. Multi-selección.
          </p>
          <div className="chips">
            {INTENCIONES.filter((i) => i.v !== "disponible_hoy").map((i) => (
              <button
                key={i.v}
                className={`chip ${p.intenciones.includes(i.v) ? "on" : ""}`}
                onClick={() => set("intenciones", alternar(p.intenciones, i.v))}
              >
                {i.icono} {i.t}
              </button>
            ))}
          </div>
          <hr style={{ border: "none", borderTop: "1px solid var(--line)", margin: "14px 0" }} />
          <DisponibleHoy perfil={perfil} refrescar={refrescar} />
        </div>

        <div className="panel" style={{ gridColumn: "1 / -1" }}>
          <h3>Intereses</h3>
          <div className="chips">
            {catalogos.intereses.map((i) => (
              <button
                key={i}
                className={`chip ${p.intereses.includes(i) ? "on" : ""}`}
                onClick={() =>
                  set(
                    "intereses",
                    p.intereses.includes(i)
                      ? p.intereses.filter((x) => x !== i)
                      : [...p.intereses, i]
                  )
                }
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
      {ok && (
        <div className="aviso aviso-ok" style={{ marginTop: 16 }}>
          {ok}
        </div>
      )}
      <button
        className="btn btn-primario"
        style={{ marginTop: 16 }}
        disabled={!borrador}
        onClick={guardar}
      >
        Guardar cambios
      </button>

      {camara && (
        <Camara
          modo={camara}
          segundosMax={catalogos.limites.segundos_video}
          onListo={camara === "foto" ? fotoDeCamara : videoDeCamara}
          onCerrar={() => setCamara(null)}
        />
      )}
    </>
  );
}

// "Disponible hoy" es su propio botón y no un chip más: vence solo a las 24 h
// y eso lo maneja el servidor (`Perfil.marcar_disponible`), no el borrador de
// edición que se guarda a mano.
function DisponibleHoy({ perfil, refrescar }) {
  const [ocupado, setOcupado] = useState(false);
  const activo = perfil.disponible_hoy;

  const prender = async () => {
    setOcupado(true);
    try {
      await api.marcarDisponible();
      await refrescar();
    } finally {
      setOcupado(false);
    }
  };
  const apagar = async () => {
    setOcupado(true);
    try {
      await api.apagarDisponible();
      await refrescar();
    } finally {
      setOcupado(false);
    }
  };

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 6 }}>
        <span style={{ fontWeight: 800 }}>⚡ Disponible hoy</span>
        {activo && <span className="insignia insignia-comp">Activo</span>}
      </div>
      <p style={{ color: "var(--muted)", fontSize: 12.5, margin: "0 0 10px" }}>
        Se apaga solo a las 24 h — no queda prendido para siempre.
      </p>
      <button className="btn btn-bloque" disabled={ocupado} onClick={activo ? apagar : prender}>
        {activo ? "Apagar" : "Activar por 24 h"}
      </button>
    </div>
  );
}
