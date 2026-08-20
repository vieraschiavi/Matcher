import { t } from "../i18n";

/**
 * Paginador de listas de gente.
 *
 * Existe por dos razones distintas, y las dos importan:
 *
 * 1. **Rendimiento.** "Te gustaron" puede tener cientos de personas. Pintar
 *    trescientas fotos de una sola vez en el WebView de un teléfono de gama
 *    baja lo deja pensando varios segundos antes de mostrar nada.
 * 2. **Orientación.** Sin páginas no hay forma de saber cuánta lista falta:
 *    se scrollea a ciegas. "3 / 12" contesta eso en dos caracteres.
 *
 * No hace `fetch`: recibe la lista entera ya filtrada y sólo recorta. El corte
 * de plan y el filtro duro los decide el servidor (reglas 4 y 9); este
 * componente no puede ni debe volver a opinar sobre eso.
 */
export const POR_PAGINA = 12;

export function rebanar(lista, pagina, porPagina = POR_PAGINA) {
  const desde = (pagina - 1) * porPagina;
  return (lista || []).slice(desde, desde + porPagina);
}

export function totalPaginas(lista, porPagina = POR_PAGINA) {
  return Math.max(1, Math.ceil((lista?.length || 0) / porPagina));
}

export default function Paginador({ pagina, total, onCambiar }) {
  // Una sola página no necesita controles: mostrar "1 / 1" con dos flechas
  // apagadas es ruido que ocupa lugar y no informa nada.
  if (total <= 1) return null;
  const ir = (n) => {
    onCambiar(Math.min(total, Math.max(1, n)));
    // Al cambiar de página el ojo tiene que volver arriba, si no aparece la
    // página nueva empezada por el medio y parece que no pasó nada.
    try {
      document.querySelector(".main")?.scrollTo({ top: 0, behavior: "smooth" });
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch {
      /* WebView viejo sin scroll suave: da igual, ya cambió la página */
    }
  };
  return (
    <nav className="paginador" aria-label={t("Páginas")}>
      <button
        className="btn"
        onClick={() => ir(pagina - 1)}
        disabled={pagina <= 1}
        aria-label={t("Página anterior")}
      >
        ‹ {t("Anterior")}
      </button>
      <span className="pagina-actual" aria-live="polite">
        {pagina} / {total}
      </span>
      <button
        className="btn"
        onClick={() => ir(pagina + 1)}
        disabled={pagina >= total}
        aria-label={t("Página siguiente")}
      >
        {t("Siguiente")} ›
      </button>
    </nav>
  );
}
