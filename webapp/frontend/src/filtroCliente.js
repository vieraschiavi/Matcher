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
