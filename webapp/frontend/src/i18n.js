// Traducción es / pt / en.
//
// El idioma sale del PAÍS DE LOCALIZACIÓN, que es lo pedido: un uruguayo ve
// español, un brasileño portugués, un canadiense inglés. El país lo elige la
// persona al registrarse y el catálogo (`/api/catalogos`) ya trae el idioma de
// cada uno (`geo.idioma_de`), así que no hay un segundo mapa país→idioma acá
// que se pueda desincronizar con el del motor.
//
// Orden de decisión: elección manual guardada → idioma del país del perfil →
// idioma del teléfono → español.
//
// Las claves del diccionario son el texto EN ESPAÑOL. Dos motivos: el código
// se sigue leyendo (`t("Todos los filtros, gratis")` dice qué va a salir en
// pantalla, `t("home.subtitulo")` no), y una cadena sin traducir cae sola al
// español en vez de mostrar la clave cruda al usuario.

const LLAVE = "matcher.idioma";
export const IDIOMAS = [
  { codigo: "es", nombre: "Español" },
  { codigo: "pt", nombre: "Português" },
  { codigo: "en", nombre: "English" },
];

const PT = {
  // -- navegación y chrome --
  "Descubrir": "Descobrir",
  "Radar": "Radar",
  "Chats": "Chats",
  "Matches": "Matches",
  "Likes": "Likes",
  "Perfil": "Perfil",
  "Mi perfil": "Meu perfil",
  "Filtros": "Filtros",
  "Planes": "Planos",
  "Más votados": "Mais votados",
  "Te gustaron": "Curtiram você",
  "Salir": "Sair",
  "Cargando…": "Carregando…",
  "Un momento…": "Um momento…",
  "Guardar": "Salvar",
  "Cancelar": "Cancelar",
  "Cerrar": "Fechar",

  // -- login / alta --
  "Entrar": "Entrar",
  "Crear cuenta": "Criar conta",
  "Crear mi cuenta": "Criar minha conta",
  "Email": "E-mail",
  "Contraseña": "Senha",
  "Nombre": "Nome",
  "Nacimiento": "Nascimento",
  "Sos": "Você é",
  "Altura (cm)": "Altura (cm)",
  "País": "País",
  "Ciudad": "Cidade",
  "Postura política": "Posição política",
  "Contá algo de vos": "Conte algo sobre você",
  "Probar la demo": "Testar a demo",
  "o con tu email": "ou com seu e-mail",
  "Continuar con Google": "Continuar com Google",
  "Continuar con Facebook": "Continuar com Facebook",
  "Filtrá por lo que de verdad te importa. Todos los filtros, gratis.":
    "Filtre pelo que realmente importa. Todos os filtros, de graça.",
  "Se cerró tu sesión y hay que entrar de nuevo. Tus datos están intactos.":
    "Sua sessão expirou e você precisa entrar de novo. Seus dados estão intactos.",
  "Tus hobbies (marcá los que quieras)": "Seus hobbies (marque os que quiser)",
  "Buscás (podés elegir varios; nada marcado = todos)":
    "Você busca (pode escolher vários; nada marcado = todos)",

  // -- géneros / política --
  "Mujer": "Mulher",
  "Hombre": "Homem",
  "Trans": "Trans",
  "Otro": "Outro",
  "Izquierda": "Esquerda",
  "Derecha": "Direita",
  "Neutro": "Neutro",

  // -- deck --
  "¡Es un match!": "É um match!",
  "Superfan": "Superfã",
  "★ Superfan": "★ Superfã",
  "Rebobinar": "Voltar",
  "No hay más perfiles por ahora": "Não há mais perfis por enquanto",
  "Probá agrandar el radio o aflojar algún filtro.":
    "Tente aumentar o raio ou afrouxar algum filtro.",
  "Sintético": "Sintético",
  "Cargando perfiles…": "Carregando perfis…",

  // -- filtros --
  "Sexo": "Sexo",
  "Edad": "Idade",
  "Altura": "Altura",
  "Distancia": "Distância",
  "¿Qué buscás?": "O que você busca?",
  "Equipo de fútbol": "Time de futebol",
  "Intereses que te importan": "Interesses que importam para você",
  "Guardar filtros": "Salvar filtros",
  "Podés elegir varios. Sin nada marcado, aparecen todos.":
    "Pode escolher vários. Sem nada marcado, aparecem todos.",
  "Todos los filtros están incluidos en el plan gratis. Se aplican como filtro duro: si pedís sólo hinchas de un equipo, no aparece nadie más — no se “compensa” con otra afinidad.":
    "Todos os filtros estão incluídos no plano grátis. São filtros rígidos: se você pedir só torcedores de um time, não aparece mais ninguém — não se “compensa” com outra afinidade.",
  "Multi-selección. Alcanza con que coincida una para aparecer en el deck del otro.":
    "Multisseleção. Basta uma coincidir para aparecer no deck do outro.",
  "Los equipos salen de tu país de localización. Sin nada marcado, aparecen todos.":
    "Os times vêm do seu país de localização. Sem nada marcado, aparecem todos.",

  // -- radar / mapa --
  "Mapa": "Mapa",
  "Por distancia": "Por distância",
  "Te cruzaste con": "Você cruzou com",
  "Cerca tuyo ahora": "Perto de você agora",
  "Mapa sin conexión · posiciones reales": "Mapa off-line · posições reais",
  "Todavía no sabemos dónde estás.": "Ainda não sabemos onde você está.",
  "Ubicándote…": "Localizando você…",
  "Quién hay cerca, ahora.": "Quem está perto, agora.",
  "Gente con la que te cruzaste de verdad, no sólo que está cerca ahora.":
    "Pessoas com quem você realmente cruzou, não só quem está perto agora.",
  "Todavía ninguno. Se van sumando solos mientras usás la app.":
    "Nenhum ainda. Vão aparecendo sozinhos enquanto você usa o app.",

  // -- chat --
  "Escribí algo…": "Escreva algo…",
  "Enviar": "Enviar",
  "Todavía no hay mensajes. Rompé el hielo.": "Ainda não há mensagens. Quebre o gelo.",
  "Todavía no tenés matches.": "Você ainda não tem matches.",

  // -- planes --
  "Gratis": "Grátis",
  "Incluido": "Incluído",
  "Mensual": "Mensal",
  "Anual (más barato)": "Anual (mais barato)",
  "/mes": "/mês",
  "Cargando planes…": "Carregando planos…",
  "Todos los filtros están en el plan gratis. Lo que se paga es volumen y visibilidad, no el derecho a filtrar por lo que te importa.":
    "Todos os filtros estão no plano grátis. O que se paga é volume e visibilidade, não o direito de filtrar pelo que importa para você.",
  "Elegido": "Escolhido",

  // -- cita a ciegas / likes --
  "Cita a ciegas": "Encontro às cegas",
  "Primero la charla, después las caras": "Primeiro a conversa, depois os rostos",
  "Revelado": "Revelado",
  "Las fotos se revelan cuando los dos escriben": "As fotos são reveladas quando os dois escrevem",
  "mensajes cada uno.": "mensagens cada um.",
  "Vos": "Você",
  "Responder like": "Responder like",
  "¿Borrar esta foto o video? No se puede deshacer.": "Excluir esta foto ou vídeo? Não dá para desfazer.",
  "Este servidor de demostración borra los datos cada vez que se reinicia: la cuenta y las fotos que subas se van a perder. Para probar sin sorpresas, usá una de las cuentas de demo de abajo.":
    "Este servidor de demonstração apaga os dados a cada reinício: a conta e as fotos que você subir vão se perder. Para testar sem surpresas, use uma das contas de demo abaixo.",
  // -- perfil / medios --
  "Tus fotos": "Suas fotos",
  "Tus videos": "Seus vídeos",
  "Sacar foto": "Tirar foto",
  "Grabar video": "Gravar vídeo",
  "Subir": "Enviar",
  "Borrar": "Excluir",
  "Idioma": "Idioma",
};

const EN = {
  "Descubrir": "Discover",
  "Radar": "Radar",
  "Chats": "Chats",
  "Matches": "Matches",
  "Likes": "Likes",
  "Perfil": "Profile",
  "Mi perfil": "My profile",
  "Filtros": "Filters",
  "Planes": "Plans",
  "Más votados": "Top rated",
  "Te gustaron": "Liked you",
  "Salir": "Log out",
  "Cargando…": "Loading…",
  "Un momento…": "One moment…",
  "Guardar": "Save",
  "Cancelar": "Cancel",
  "Cerrar": "Close",

  "Entrar": "Sign in",
  "Crear cuenta": "Create account",
  "Crear mi cuenta": "Create my account",
  "Email": "Email",
  "Contraseña": "Password",
  "Nombre": "Name",
  "Nacimiento": "Date of birth",
  "Sos": "You are",
  "Altura (cm)": "Height (cm)",
  "País": "Country",
  "Ciudad": "City",
  "Postura política": "Political leaning",
  "Contá algo de vos": "Tell us about you",
  "Probar la demo": "Try the demo",
  "o con tu email": "or with your email",
  "Continuar con Google": "Continue with Google",
  "Continuar con Facebook": "Continue with Facebook",
  "Filtrá por lo que de verdad te importa. Todos los filtros, gratis.":
    "Filter by what actually matters to you. Every filter, free.",
  "Se cerró tu sesión y hay que entrar de nuevo. Tus datos están intactos.":
    "Your session ended and you need to sign in again. Your data is intact.",
  "Tus hobbies (marcá los que quieras)": "Your hobbies (pick any)",
  "Buscás (podés elegir varios; nada marcado = todos)":
    "Looking for (pick several; nothing selected = everyone)",

  "Mujer": "Woman",
  "Hombre": "Man",
  "Trans": "Trans",
  "Otro": "Other",
  "Izquierda": "Left",
  "Derecha": "Right",
  "Neutro": "Neutral",

  "¡Es un match!": "It's a match!",
  "Superfan": "Superfan",
  "★ Superfan": "★ Superfan",
  "Rebobinar": "Undo",
  "No hay más perfiles por ahora": "No more profiles right now",
  "Probá agrandar el radio o aflojar algún filtro.":
    "Try widening the radius or loosening a filter.",
  "Sintético": "Synthetic",
  "Cargando perfiles…": "Loading profiles…",

  "Sexo": "Gender",
  "Edad": "Age",
  "Altura": "Height",
  "Distancia": "Distance",
  "¿Qué buscás?": "What are you looking for?",
  "Equipo de fútbol": "Football team",
  "Intereses que te importan": "Interests that matter to you",
  "Guardar filtros": "Save filters",
  "Podés elegir varios. Sin nada marcado, aparecen todos.":
    "Pick several. With nothing selected, everyone shows up.",
  "Todos los filtros están incluidos en el plan gratis. Se aplican como filtro duro: si pedís sólo hinchas de un equipo, no aparece nadie más — no se “compensa” con otra afinidad.":
    "Every filter is included in the free plan. They are hard filters: if you ask for one team's fans only, nobody else shows up — it is never “balanced out” by another affinity.",
  "Multi-selección. Alcanza con que coincida una para aparecer en el deck del otro.":
    "Multi-select. One match is enough to appear in someone's deck.",
  "Los equipos salen de tu país de localización. Sin nada marcado, aparecen todos.":
    "Teams come from your country of location. With nothing selected, all of them show up.",

  "Mapa": "Map",
  "Por distancia": "By distance",
  "Te cruzaste con": "You crossed paths with",
  "Cerca tuyo ahora": "Near you now",
  "Mapa sin conexión · posiciones reales": "Offline map · real positions",
  "Todavía no sabemos dónde estás.": "We don't know where you are yet.",
  "Ubicándote…": "Locating you…",
  "Quién hay cerca, ahora.": "Who's nearby, right now.",
  "Gente con la que te cruzaste de verdad, no sólo que está cerca ahora.":
    "People you actually crossed paths with, not just who is nearby now.",
  "Todavía ninguno. Se van sumando solos mientras usás la app.":
    "None yet. They add up on their own as you use the app.",

  "Escribí algo…": "Write something…",
  "Enviar": "Send",
  "Todavía no hay mensajes. Rompé el hielo.": "No messages yet. Break the ice.",
  "Todavía no tenés matches.": "You don't have any matches yet.",

  "Gratis": "Free",
  "Incluido": "Included",
  "Mensual": "Monthly",
  "Anual (más barato)": "Yearly (cheaper)",
  "/mes": "/mo",
  "Cargando planes…": "Loading plans…",
  "Todos los filtros están en el plan gratis. Lo que se paga es volumen y visibilidad, no el derecho a filtrar por lo que te importa.":
    "Every filter is in the free plan. What you pay for is volume and visibility, never the right to filter by what matters to you.",
  "Elegido": "Selected",

  // -- blind date / likes --
  "Cita a ciegas": "Blind date",
  "Primero la charla, después las caras": "Talk first, faces later",
  "Revelado": "Revealed",
  "Las fotos se revelan cuando los dos escriben": "Photos unlock once you both write",
  "mensajes cada uno.": "messages each.",
  "Vos": "You",
  "Responder like": "Like back",
  "¿Borrar esta foto o video? No se puede deshacer.": "Delete this photo or video? This cannot be undone.",
  "Este servidor de demostración borra los datos cada vez que se reinicia: la cuenta y las fotos que subas se van a perder. Para probar sin sorpresas, usá una de las cuentas de demo de abajo.":
    "This demo server wipes its data on every restart: any account and photos you upload will be lost. To try it without surprises, use one of the demo accounts below.",
  "Tus fotos": "Your photos",
  "Tus videos": "Your videos",
  "Sacar foto": "Take a photo",
  "Grabar video": "Record video",
  "Subir": "Upload",
  "Borrar": "Delete",
  "Idioma": "Language",
};

const DICC = { pt: PT, en: EN };

export function idiomaGuardado() {
  try {
    return localStorage.getItem(LLAVE) || "";
  } catch {
    return ""; // WebView con almacenamiento bloqueado
  }
}

// El idioma vigente vive en un módulo y no en el estado de React a propósito:
// `t()` se llama desde funciones sueltas y desde componentes, y pasar el
// idioma por props hasta la última hoja no aporta nada.
//
// Arranca con la elección guardada YA APLICADA. Antes arrancaba fijo en "es" y
// el efecto que resuelve el idioma sale temprano cuando hay elección manual
// —para no pisarla—, así que la elección se leía pero no se aplicaba nunca:
// la app quedaba en español por más que el usuario hubiera elegido inglés.
let actual = "es";

export function idioma() {
  return actual;
}

/**
 * Aplica un idioma. `persistir` sólo va en TRUE cuando lo eligió la persona.
 *
 * Guardar también el idioma deducido del país era un error sutil: quedaba
 * anotado como si fuera una elección manual y, a partir de ahí, cambiar el
 * país del perfil ya no cambiaba el idioma — la app se quedaba pegada al
 * primero que adivinó.
 */
export function fijarIdioma(codigo, { persistir = false } = {}) {
  actual = IDIOMAS.some((i) => i.codigo === codigo) ? codigo : "es";
  if (!persistir) return;
  try {
    localStorage.setItem(LLAVE, actual);
  } catch {
    /* si no se puede guardar, al menos vale para esta sesión */
  }
}

// Se aplica la elección guardada apenas `fijarIdioma` existe.
const _guardado = idiomaGuardado();
if (_guardado) fijarIdioma(_guardado);

/** Idioma del teléfono, recortado a los que existen. */
export function idiomaDelDispositivo() {
  const base = (navigator.language || "es").slice(0, 2).toLowerCase();
  return IDIOMAS.some((i) => i.codigo === base) ? base : "es";
}

/**
 * Decide el idioma: elección manual → país del perfil → teléfono.
 *
 * `paises` es el catálogo del backend, que ya trae el idioma de cada país.
 */
export function resolverIdioma(perfil, paises) {
  const manual = idiomaGuardado();
  if (manual) return manual;
  const pais = perfil?.pais && paises?.find((p) => p.codigo === perfil.pais);
  if (pais?.idioma) return pais.idioma;
  return idiomaDelDispositivo();
}

/**
 * Traduce. Sin entrada en el diccionario devuelve el español, que es legible;
 * nunca una clave cruda.
 *
 * Admite variables: t("Hola {nombre}", {nombre: "Ana"}).
 */
export function t(texto, vars) {
  let salida = DICC[actual]?.[texto] ?? texto;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) salida = salida.replaceAll(`{${k}}`, v);
  }
  return salida;
}
