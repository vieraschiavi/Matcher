import { useEffect, useRef, useState } from "react";

// Cámara en el momento, sin salir de la app. `modo="foto"` saca una toma;
// `modo="video"` graba hasta `segundosMax` con cuenta regresiva. Devuelve lo
// mismo que sube el selector de archivos ({url, bytes}) para no bifurcar el
// resto del flujo de subida.
export default function Camara({ modo, segundosMax = 30, onListo, onCerrar }) {
  const video = useRef(null);
  const stream = useRef(null);
  const grabador = useRef(null);
  const trozos = useRef([]);
  const [espejo, setEspejo] = useState(true); // frontal se ve en espejo, natural para selfies
  const [frontal, setFrontal] = useState(true);
  const [grabando, setGrabando] = useState(false);
  const [segundos, setSegundos] = useState(0);
  const [error, setError] = useState("");
  const temporizador = useRef(null);

  const abrirCamara = async (usarFrontal) => {
    detenerStream();
    setError("");
    try {
      const s = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: usarFrontal ? "user" : "environment" },
        audio: modo === "video",
      });
      stream.current = s;
      setEspejo(usarFrontal);
      if (video.current) video.current.srcObject = s;
    } catch {
      setError(
        "No pudimos acceder a la cámara. Revisá los permisos del navegador, o subí un archivo."
      );
    }
  };

  useEffect(() => {
    abrirCamara(frontal);
    return detenerStream;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [frontal]);

  function detenerStream() {
    stream.current?.getTracks().forEach((t) => t.stop());
    clearInterval(temporizador.current);
  }

  const sacarFoto = () => {
    const v = video.current;
    const lienzo = document.createElement("canvas");
    lienzo.width = v.videoWidth;
    lienzo.height = v.videoHeight;
    const ctx = lienzo.getContext("2d");
    if (espejo) {
      ctx.translate(lienzo.width, 0);
      ctx.scale(-1, 1);
    }
    ctx.drawImage(v, 0, 0);
    lienzo.toBlob(
      (blob) => {
        const lector = new FileReader();
        lector.onload = () => onListo({ url: lector.result, bytes: blob.size });
        lector.readAsDataURL(blob);
      },
      "image/jpeg",
      0.85
    );
  };

  const empezarGrabacion = () => {
    if (!stream.current) return;
    trozos.current = [];
    const tipo = MediaRecorder.isTypeSupported("video/webm;codecs=vp9")
      ? "video/webm;codecs=vp9"
      : "video/webm";
    const rec = new MediaRecorder(stream.current, { mimeType: tipo });
    rec.ondataavailable = (e) => e.data.size > 0 && trozos.current.push(e.data);
    rec.onstop = () => {
      const blob = new Blob(trozos.current, { type: tipo });
      const lector = new FileReader();
      lector.onload = () =>
        onListo({ url: lector.result, bytes: blob.size, segundos: segundosMax - segundos });
      lector.readAsDataURL(blob);
    };
    grabador.current = rec;
    rec.start();
    setGrabando(true);
    setSegundos(segundosMax);
    temporizador.current = setInterval(() => {
      setSegundos((s) => {
        if (s <= 1) {
          rec.stop();
          setGrabando(false);
          clearInterval(temporizador.current);
          return 0;
        }
        return s - 1;
      });
    }, 1000);
  };

  const pararGrabacion = () => {
    grabador.current?.stop();
    setGrabando(false);
    clearInterval(temporizador.current);
  };

  const cerrar = () => {
    detenerStream();
    onCerrar();
  };

  return (
    <div className="velo-modal" onClick={cerrar}>
      <div className="modal camara-modal" onClick={(e) => e.stopPropagation()}>
        <h2 style={{ fontSize: 19 }}>{modo === "foto" ? "Sacar foto" : "Grabar video"}</h2>
        {error ? (
          <div className="aviso aviso-error">{error}</div>
        ) : (
          <div className="camara-visor">
            <video
              ref={video}
              autoPlay
              playsInline
              muted
              style={{ transform: espejo ? "scaleX(-1)" : "none" }}
            />
            {grabando && (
              <div className="camara-cuenta">
                ● {segundos}s
              </div>
            )}
          </div>
        )}
        <div className="camara-acciones">
          <button className="btn" onClick={() => setFrontal((f) => !f)} disabled={grabando}>
            🔄 Cambiar cámara
          </button>
          {modo === "foto" ? (
            <button className="btn btn-primario" onClick={sacarFoto} disabled={!!error}>
              📸 Capturar
            </button>
          ) : grabando ? (
            <button className="btn btn-primario" onClick={pararGrabacion}>
              ■ Cortar
            </button>
          ) : (
            <button className="btn btn-primario" onClick={empezarGrabacion} disabled={!!error}>
              ● Grabar (máx. {segundosMax}s)
            </button>
          )}
        </div>
        <button className="btn btn-fantasma btn-bloque" onClick={cerrar} style={{ marginTop: 8 }}>
          Cancelar
        </button>
      </div>
    </div>
  );
}
