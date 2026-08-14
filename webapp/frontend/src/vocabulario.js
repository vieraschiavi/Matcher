// Vocabulario compartido entre Filtros, Mi perfil y Entrar: mismas etiquetas
// en los tres lugares donde aparece género/intención, para que no se
// desincronicen (ya pasó: un lugar decía "No binarie" y otro "Otro/a").

export const GENEROS = [
  { v: "mujer", t: "Mujer" },
  { v: "hombre", t: "Hombre" },
  { v: "trans", t: "Trans" },
  { v: "otro", t: "Otro" },
];

export const INTENCIONES = [
  { v: "amistad", t: "Amistad", icono: "🤝" },
  { v: "tomar_algo", t: "Tomar algo", icono: "🍹" },
  { v: "algo_casual", t: "Algo casual", icono: "😉" },
  { v: "relacion_formal", t: "Relación formal", icono: "💞" },
  { v: "salir_a_bailar", t: "Salir a bailar", icono: "💃" },
  { v: "sexo", t: "Sexo", icono: "🔥" },
  { v: "disponible_hoy", t: "Disponible hoy", icono: "⚡" },
];

export const POLITICAS = [
  { v: "izquierda", t: "Izquierda" },
  { v: "derecha", t: "Derecha" },
  { v: "neutro", t: "Neutro" },
];

// Alterna un valor dentro de una lista. Lista vacía = "Todos", que es distinto
// de "ninguno": si el usuario destilda todo, el filtro se apaga solo.
export const alternar = (lista, v) =>
  lista.includes(v) ? lista.filter((x) => x !== v) : [...lista, v];
