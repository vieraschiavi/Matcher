// Re-verificación de los filtros duros EN el cliente.
//
// El servidor ya filtra todas las listas (hay un test que barre los cinco
// endpoints). Esto existe por el despliegue serverless: guardás "sólo
// mujeres" en una instancia y el deck te lo puede armar otra que todavía
// tiene tus preferencias viejas — y un hombre se cuela con el servidor
// "funcionando bien". La promesa del producto es que el filtro se respeta
// BAJO NINGÚN CONCEPTO, así que la última línea de defensa corre acá, con
// las preferencias que este teléfono acaba de guardar.
//
// No es la fuga de la regla 8 (esconder con CSS lo que el servidor manda):
// esto descarta de más, nunca revela de menos, y sólo re-aplica el criterio
// que el servidor ya tiene.
//
// Se re-verifica lo que el payload trae en todas las listas: género y edad.
// Altura/política/equipo no viajan en todos los endpoints; el servidor sigue
// siendo el dueño de esos.

// --- memoria local de las preferencias --------------------------------------
//
// Medido contra el despliegue serverless: de 30 lecturas de /api/yo con el
// filtro en "mujer", 17 devolvieron `[]`. Cada instancia resiembra su propia
// base y el perfil vuelve a las preferencias por defecto, así que el deck que
// arma esa instancia trae de todo. En 30 decks: 45 de 202 tarjetas eran del
// género que el usuario NO pidió.
//
// El teléfono es el que sabe la verdad —fue el que hizo el cambio—, así que
// guarda las preferencias y las usa para el filtro duro del cliente. Esto NO
// reemplaza al servidor: el servidor sigue filtrando y sigue siendo el dueño
// del dato. Es la garantía de que la promesa del producto ("si pedís mujeres,
// no aparece un hombre BAJO NINGÚN CONCEPTO") se cumpla aunque el backend
// esté en un disco efímero.

const LLAVE = "matcher.preferencias";

export function recordarPreferencias(preferencias) {
  if (!preferencias) return;
  try {
    localStorage.setItem(LLAVE, JSON.stringify(preferencias));
  } catch {
    /* almacenamiento bloqueado: se sigue con lo que diga el servidor */
  }
}

export function preferenciasRecordadas() {
  try {
    const crudo = localStorage.getItem(LLAVE);
    return crudo ? JSON.parse(crudo) : null;
  } catch {
    return null;
  }
}

export function olvidarPreferencias() {
  try {
    localStorage.removeItem(LLAVE);
  } catch {
    /* nada que hacer */
  }
}

/**
 * Las preferencias que MANDAN para filtrar en el cliente.
 *
 * Gana lo guardado en este teléfono por sobre lo que devuelve el servidor:
 * si difieren es porque el servidor perdió el cambio, nunca al revés — la
 * única forma de cambiarlas es desde acá.
 */
export function preferenciasEfectivas(delServidor) {
  return preferenciasRecordadas() || delServidor || null;
}

export function pasaFiltroCliente(preferencias, persona) {
  if (!preferencias || !persona) return true;
  const generos = preferencias.generos || [];
  if (generos.length && persona.genero && !generos.includes(persona.genero)) return false;
  if (persona.edad != null) {
    if (preferencias.edad_min != null && persona.edad < preferencias.edad_min) return false;
    if (preferencias.edad_max != null && persona.edad > preferencias.edad_max) return false;
  }
  return true;
}

/** Filtra una lista de personas (o de objetos con la persona adentro). */
export function soloPermitidos(preferencias, lista, sacar = (x) => x) {
  return (lista || []).filter((x) => pasaFiltroCliente(preferencias, sacar(x)));
}
