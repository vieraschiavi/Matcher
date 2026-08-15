import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { SESION_CAIDA, api, token } from "./api";
import { fijarIdioma, idioma, idiomaGuardado, resolverIdioma } from "./i18n";
import {
  olvidarPreferencias,
  preferenciasEfectivas,
  preferenciasRecordadas,
  recordarPreferencias,
} from "./filtroCliente";

// Sesión + catálogos en un solo contexto. Los catálogos (países, ciudades,
// equipos) se piden una vez y se comparten: son ~40 KB y no cambian durante
// la sesión, pero se pedían en cuatro pantallas distintas.
const Ctx = createContext(null);

// Comparación laxa: sólo los campos que el filtro duro del cliente usa. Un
// `JSON.stringify` de objetos con claves en distinto orden daría distinto y
// dispararía una escritura al servidor en cada lectura.
function mismasPreferencias(a, b) {
  const lista = (x) => JSON.stringify([...(x || [])].sort());
  return (
    lista(a.generos) === lista(b.generos) &&
    a.edad_min === b.edad_min &&
    a.edad_max === b.edad_max
  );
}

export function Proveedor({ children }) {
  const [perfil, setPerfil] = useState(null);
  const [cupos, setCupos] = useState(null);
  const [catalogos, setCatalogos] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [sesionCaida, setSesionCaida] = useState(false);
  const [lang, setLang] = useState(idioma());

  // El idioma se decide con el país del perfil (es lo pedido: el idioma sale
  // del país de localización) y el catálogo, que ya trae `idioma` por país.
  // Se recalcula cuando llega cualquiera de los dos, porque al arrancar no
  // están todavía y quedaba en español hasta recargar.
  useEffect(() => {
    if (idiomaGuardado()) return; // elección manual: no se pisa
    const elegido = resolverIdioma(perfil, catalogos?.paises);
    if (elegido !== idioma()) {
      fijarIdioma(elegido);
      setLang(elegido);
    }
  }, [perfil, catalogos]);

  // Elección explícita: ésta sí se guarda y gana sobre el país.
  const cambiarIdioma = (codigo) => {
    fijarIdioma(codigo, { persistir: true });
    setLang(codigo);
  };

  const refrescar = useCallback(async () => {
    if (!token.leer()) {
      setPerfil(null);
      setCupos(null);
      setCargando(false);
      return;
    }
    try {
      const r = await api.yo();
      // Si este teléfono recuerda otras preferencias que las que devolvió el
      // servidor, gana el teléfono y se las vuelve a imponer al servidor. Es
      // auto-reparación: la instancia que perdió el cambio queda al día sola.
      const recordadas = preferenciasRecordadas();
      const delServidor = r.perfil?.preferencias;
      if (recordadas && delServidor && !mismasPreferencias(recordadas, delServidor)) {
        r.perfil = { ...r.perfil, preferencias: { ...delServidor, ...recordadas } };
        api.editar({ preferencias: recordadas }).catch(() => {});
      }
      setPerfil(r.perfil);
      setCupos(r.cupos);
    } catch {
      setPerfil(null);
      setCupos(null);
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    api.catalogos().then(setCatalogos).catch(() => setCatalogos(null));
    refrescar();
  }, [refrescar]);

  // Si el servidor rechaza la sesión, se vuelve al login enseguida. Sin esto
  // la app quedaba con `perfil` en memoria y un token que ya no valía: cada
  // pantalla mostraba "Cargando…" para siempre y parecía que no funcionaba
  // nada.
  useEffect(() => {
    const caida = () => {
      setPerfil(null);
      setCupos(null);
      setCargando(false);
      // Sin este cartel, volver al login de golpe parece que la app se
      // reinició sola. Pasa de verdad cuando cambia la clave de firma del
      // servidor: los tokens viejos dejan de valer, una única vez.
      setSesionCaida(true);
    };
    window.addEventListener(SESION_CAIDA, caida);
    return () => window.removeEventListener(SESION_CAIDA, caida);
  }, []);

  const entrar = async (email, clave) => {
    const r = await api.login(email, clave);
    token.guardar(r.token);
    setSesionCaida(false);
    setPerfil(r.perfil);
    await refrescar();
  };

  // El callback del proveedor vuelve con el token en la URL. Se guarda y se
  // limpia el hash: dejar el token en la barra de direcciones lo mete en el
  // historial y en cualquier captura de pantalla.
  const entrarConToken = async (t) => {
    token.guardar(t);
    await refrescar();
  };

  const registrar = async (datos) => {
    const r = await api.registro(datos);
    token.guardar(r.token);
    setPerfil(r.perfil);
    await refrescar();
  };

  // Actualiza el perfil desde una respuesta que ya lo trae. Los endpoints de
  // fotos devuelven el perfil entero justamente para esto: pedirlo de nuevo
  // con GET /api/yo puede caer en otra instancia con estado viejo, y era la
  // causa de "borré una foto y desapareció otra".
  const aplicarPerfil = (p) => {
    if (p) setPerfil(p);
  };

  // Guardar filtros: se recuerdan en el teléfono ANTES de mandarlos, así el
  // cliente puede seguir filtrando aunque el servidor pierda el cambio.
  const guardarPreferencias = async (preferencias) => {
    recordarPreferencias(preferencias);
    const r = await api.editar({ preferencias });
    if (r?.perfil) setPerfil(r.perfil);
    return r;
  };

  const salir = async () => {
    try {
      await api.logout();
    } finally {
      token.borrar();
      olvidarPreferencias(); // otra persona en el mismo teléfono no hereda los filtros
      setPerfil(null);
      setCupos(null);
    }
  };

  return (
    <Ctx.Provider
      value={{
        perfil, cupos, catalogos, cargando, sesionCaida, lang, cambiarIdioma,
        entrar, entrarConToken, registrar, salir, refrescar, setCupos, aplicarPerfil,
        guardarPreferencias, preferenciasEfectivas,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useApp() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useApp fuera del Proveedor");
  return v;
}
