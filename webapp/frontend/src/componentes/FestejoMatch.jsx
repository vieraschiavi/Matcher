import { useEffect, useRef } from "react";

// Festejo del match: llamas de verdad + cartel que entra golpeando.
//
// Nada de emoji (🔥💛): el emoji lo dibuja el sistema operativo, cambia de
// forma entre Android/iOS/escritorio, no toma el color del tema y le da a la
// pantalla ese aire de plantilla. Acá el fuego son paths SVG con degradado
// propio, animados por CSS.
//
// El fuego se dibuja con TRES capas superpuestas (externa naranja, media
// ámbar, interna clara) desfasadas entre sí. Es lo que hace que una llama
// parezca viva: una sola silueta deformándose se lee como una gota temblando.
//
// Las partículas suben en vez de caer (una brasa sube, un confeti cae) y se
// generan una sola vez, con posiciones derivadas del índice: sin `Math.random`
// en el render, que en React estricto se ejecuta dos veces y saltaría todo.

function Llama({ retraso = 0, escala = 1, x = 0 }) {
  return (
    <svg
      className="llama"
      viewBox="0 0 64 96"
      style={{ "--retraso": `${retraso}s`, "--escala": escala, "--x": `${x}px` }}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={`fuego-ext-${retraso}`} x1="0" y1="1" x2="0" y2="0">
          <stop offset="0%" stopColor="#c9184a" />
          <stop offset="55%" stopColor="#ff4d6d" />
          <stop offset="100%" stopColor="#ff8a3d" />
        </linearGradient>
        <linearGradient id={`fuego-int-${retraso}`} x1="0" y1="1" x2="0" y2="0">
          <stop offset="0%" stopColor="#ff8a3d" />
          <stop offset="60%" stopColor="#f2b441" />
          <stop offset="100%" stopColor="#fff3c4" />
        </linearGradient>
      </defs>
      {/* Capa externa: la silueta grande de la llama. */}
      <path
        className="llama-capa llama-ext"
        fill={`url(#fuego-ext-${retraso})`}
        d="M32 95c15 0 25-9.6 25-23 0-10-5-16-11-23-2.3-2.7-4-6-4.6-9.6-.3-2-2.9-2.6-4-.9-2 3-3.4 6.6-3.7 10.6-3.6-2.7-5-7-4.6-12.4.1-2-2.2-3.2-3.7-1.8C18.6 41 12 51 12 64c0 17 8 31 20 31Z"
      />
      {/* Capa media: más angosta y con otro ritmo. */}
      <path
        className="llama-capa llama-med"
        fill={`url(#fuego-int-${retraso})`}
        d="M32 92c9 0 15-6.4 15-15 0-7-3.4-11-7.4-15.6-1.6-1.8-2.6-4-3-6.4-.3-1.7-2.6-2-3.4-.5-1.4 2.6-2.2 5.4-2.2 8.4-2.6-1.6-3.8-4.2-3.6-7.6-2.6 3.4-6.4 10-6.4 18C21 84 25 92 32 92Z"
      />
      {/* Núcleo claro: el corazón caliente. */}
      <path
        className="llama-capa llama-int"
        fill="#fff3c4"
        opacity="0.9"
        d="M32 88c5 0 8-3.4 8-8 0-4.4-2.6-6.6-4.6-9.6-.8-1.2-1.3-2.6-1.5-4-2 2.4-3.2 5-3.4 7.6-1.4-1-2-2.4-2-4.2-2 2.6-3.5 5.6-3.5 9.2 0 5 3 9 7 9Z"
      />
    </svg>
  );
}

export default function FestejoMatch({ con, compatibilidad, automatico, onChat, onSeguir }) {
  const caja = useRef(null);

  // Las brasas se calculan una vez: 18 posiciones distribuidas, con desfase.
  const brasas = useRef(
    Array.from({ length: 18 }, (_, i) => ({
      izq: 4 + ((i * 37) % 92),
      retraso: (i % 9) * 0.24,
      dur: 1.9 + (i % 5) * 0.32,
      tam: 4 + (i % 4) * 2.5,
    }))
  ).current;

  useEffect(() => {
    caja.current?.focus();
  }, []);

  return (
    <div className="festejo" role="dialog" aria-label="Es un match">
      <div className="festejo-brasas" aria-hidden="true">
        {brasas.map((b, i) => (
          <span
            key={i}
            style={{
              left: `${b.izq}%`,
              animationDelay: `${b.retraso}s`,
              animationDuration: `${b.dur}s`,
              width: b.tam,
              height: b.tam,
            }}
          />
        ))}
      </div>

      <div className="festejo-fuego" aria-hidden="true">
        <Llama retraso={0} escala={1} x={0} />
        <Llama retraso={0.35} escala={0.72} x={-52} />
        <Llama retraso={0.7} escala={0.66} x={54} />
      </div>

      <div className="festejo-cartel" ref={caja} tabIndex={-1}>
        <span className="festejo-match">MATCH</span>
        <p className="festejo-quien">
          {automatico
            ? `El algoritmo te emparejó con ${con?.nombre}`
            : `A ${con?.nombre} también le gustaste`}
        </p>
        {compatibilidad != null && (
          <span className="festejo-comp">{compatibilidad}% compatibles</span>
        )}
      </div>

      {con?.fotos?.[0]?.url && (
        <img className="festejo-cara" src={con.fotos[0].url} alt={`Foto de ${con.nombre}`} />
      )}

      <div className="festejo-botones">
        <button className="btn btn-bloque" onClick={onSeguir}>
          Seguir deslizando
        </button>
        <button className="btn btn-primario btn-bloque" onClick={onChat}>
          Mandar mensaje
        </button>
      </div>
    </div>
  );
}
