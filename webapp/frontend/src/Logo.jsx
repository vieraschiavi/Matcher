// Logo de Matcher: un corazón partido en dos mitades que encajan.
//
// La idea es el "match": dos partes distintas que se completan. La "M" en un
// cuadrado que había antes no decía nada — podía ser cualquier app.
//
// Se dibuja en SVG y no como PNG para que se vea nítido en cualquier tamaño,
// desde los 28 px de la barra hasta la pantalla de bienvenida.

const IZQUIERDA = "M47 79 C47 79 17 60 17 40 C17 28 25 21 34 21 C40 21 45 24 47 29 Z";
const DERECHA = "M53 79 C53 79 83 60 83 40 C83 28 75 21 66 21 C60 21 55 24 53 29 Z";

export default function Logo({ tam = 34, radio = 0.24, id = "logo" }) {
  return (
    <svg
      width={tam}
      height={tam}
      viewBox="0 0 100 100"
      role="img"
      aria-label="Matcher"
      style={{ display: "block", flex: "none" }}
    >
      <defs>
        {/* El id tiene que ser único por instancia: dos SVG con el mismo id de
            gradiente en la misma página hacen que el navegador use el primero
            para los dos. */}
        <linearGradient id={`grad-${id}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#ff5c7a" />
          <stop offset="50%" stopColor="#f0407e" />
          <stop offset="100%" stopColor="#8e5bef" />
        </linearGradient>
      </defs>
      <rect width="100" height="100" rx={100 * radio} fill={`url(#grad-${id})`} />
      <g transform="translate(-2 0)">
        <path d={IZQUIERDA} fill="#fff" />
      </g>
      <g transform="translate(2 0)">
        <path d={DERECHA} fill="#fff" opacity="0.62" />
      </g>
    </svg>
  );
}
