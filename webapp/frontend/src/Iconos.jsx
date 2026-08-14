// Set de íconos propio.
//
// Antes la navegación y las fichas usaban emoji (🔥 📍 💬 ⚽ 🗳️). Se ven
// distintos en cada teléfono —Android, iOS y Windows dibujan otra cosa—, no
// se pueden teñir con el color del tema y le dan a la app ese aire de
// plantilla armada a las apuradas. Estos son de trazo, heredan `currentColor`
// y comparten grilla de 24, ancho de trazo y remates redondeados, que es lo
// que hace que un set se lea como uno solo.

const BASE = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.7,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

function Svg({ tam = 22, children, ...resto }) {
  return (
    <svg width={tam} height={tam} {...BASE} {...resto} aria-hidden="true">
      {children}
    </svg>
  );
}

export const IcoLlama = (p) => (
  <Svg {...p}>
    <path d="M12 3c.4 3 2 4.2 3.4 5.6A6.6 6.6 0 0 1 17.5 14a5.5 5.5 0 0 1-11 0c0-1.6.6-2.8 1.5-3.8.2 1 .8 1.7 1.6 2 0-2.6.6-4.6 2.4-6.4Z" />
  </Svg>
);

export const IcoRadar = (p) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="9" />
    <circle cx="12" cy="12" r="4.6" />
    <circle cx="12" cy="12" r="1" fill="currentColor" />
    <path d="M12 12 18.4 5.6" />
  </Svg>
);

export const IcoChat = (p) => (
  <Svg {...p}>
    <path d="M20 14.5a2.5 2.5 0 0 1-2.5 2.5H9l-4 3.2V6.5A2.5 2.5 0 0 1 7.5 4h10A2.5 2.5 0 0 1 20 6.5Z" />
  </Svg>
);

export const IcoCorazon = ({ relleno = false, ...p }) => (
  <Svg {...p}>
    <path
      d="M12 20s-7.5-4.4-7.5-9.6A4.4 4.4 0 0 1 12 7.3a4.4 4.4 0 0 1 7.5 3.1C19.5 15.6 12 20 12 20Z"
      fill={relleno ? "currentColor" : "none"}
    />
  </Svg>
);

export const IcoEstrella = ({ relleno = false, ...p }) => (
  <Svg {...p}>
    <path
      d="m12 4 2.4 4.9 5.4.8-3.9 3.8.9 5.4-4.8-2.5-4.8 2.5.9-5.4-3.9-3.8 5.4-.8Z"
      fill={relleno ? "currentColor" : "none"}
    />
  </Svg>
);

export const IcoTrofeo = (p) => (
  <Svg {...p}>
    <path d="M7 4h10v5a5 5 0 0 1-10 0Z" />
    <path d="M7 6H4.6a3 3 0 0 0 3 3M17 6h2.4a3 3 0 0 1-3 3" />
    <path d="M12 14v3M8.6 20h6.8l-.6-3H9.2Z" />
  </Svg>
);

export const IcoFiltros = (p) => (
  <Svg {...p}>
    <path d="M4 7h16M7 12h10M10 17h4" />
  </Svg>
);

export const IcoPersona = (p) => (
  <Svg {...p}>
    <circle cx="12" cy="8.4" r="3.6" />
    <path d="M4.8 20a7.2 7.2 0 0 1 14.4 0" />
  </Svg>
);

export const IcoDiamante = (p) => (
  <Svg {...p}>
    <path d="M7 3h10l4 6-9 12L3 9Z" />
    <path d="M3 9h18M9.5 9 12 3M14.5 9 12 3M12 21 9.5 9M12 21l2.5-12" />
  </Svg>
);

export const IcoSalir = (p) => (
  <Svg {...p}>
    <path d="M15 5.5V4.2A1.2 1.2 0 0 0 13.8 3H5.2A1.2 1.2 0 0 0 4 4.2v15.6A1.2 1.2 0 0 0 5.2 21h8.6a1.2 1.2 0 0 0 1.2-1.2v-1.3" />
    <path d="M10 12h11m0 0-3.2-3.2M21 12l-3.2 3.2" />
  </Svg>
);

export const IcoCruz = (p) => (
  <Svg {...p}>
    <path d="M6.5 6.5l11 11M17.5 6.5l-11 11" />
  </Svg>
);

export const IcoRayo = (p) => (
  <Svg {...p}>
    <path d="M13.5 3 5 13.5h5.5L10 21l8.5-10.5H13Z" />
  </Svg>
);

export const IcoDeshacer = (p) => (
  <Svg {...p}>
    <path d="M4 9h9.5a5.5 5.5 0 1 1 0 11H8" />
    <path d="M4 9l4-4M4 9l4 4" />
  </Svg>
);

export const IcoPelota = (p) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="m12 8.2 3.2 2.3-1.2 3.8h-4l-1.2-3.8Z" />
    <path d="M12 3v5.2M4.2 10.3l4.6.2M19.8 10.3l-4.6.2M7.3 20l1.7-5.7M16.7 20 15 14.3" />
  </Svg>
);

// Urna con la ranura y la boleta entrando. La versión anterior era un techo
// a dos aguas sobre una caja y a 14 px se leía como un triángulo suelto: a
// ese tamaño sólo sobrevive una silueta simple y cerrada.
export const IcoVoto = (p) => (
  <Svg {...p}>
    <path d="M4 10.5h16v9H4Z" />
    <path d="M8.6 10.5V5.2h6.8v5.3" />
    <path d="M9.6 14.2h4.8" />
  </Svg>
);

export const IcoPin = (p) => (
  <Svg {...p}>
    <path d="M12 21s6.5-6 6.5-10.5a6.5 6.5 0 0 0-13 0C5.5 15 12 21 12 21Z" />
    <circle cx="12" cy="10.4" r="2.4" />
  </Svg>
);

export const IcoRegla = (p) => (
  <Svg {...p}>
    <path d="M12 3v18M8.5 5.5 12 3l3.5 2.5M8.5 18.5 12 21l3.5-2.5" />
  </Svg>
);

export const IcoVerificado = (p) => (
  <Svg {...p}>
    <path d="m12 2.8 2.4 1.8 3-.2.9 2.9 2.4 1.8-1.1 2.8 1.1 2.8-2.4 1.8-.9 2.9-3-.2L12 21.2l-2.4-1.8-3 .2-.9-2.9-2.4-1.8L4.4 12 3.3 9.2l2.4-1.8.9-2.9 3 .2Z" />
    <path d="m8.8 12 2.2 2.2 4.2-4.4" />
  </Svg>
);

export const IcoCamara = (p) => (
  <Svg {...p}>
    <path d="M3.5 8.5h3L8 6h8l1.5 2.5h3v10h-17Z" />
    <circle cx="12" cy="13" r="3.3" />
  </Svg>
);
