import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, token } from "./api";

// Sesión + catálogos en un solo contexto. Los catálogos (países, ciudades,
// equipos) se piden una vez y se comparten: son ~40 KB y no cambian durante
// la sesión, pero se pedían en cuatro pantallas distintas.
const Ctx = createContext(null);

export function Proveedor({ children }) {
  const [perfil, setPerfil] = useState(null);
  const [cupos, setCupos] = useState(null);
  const [catalogos, setCatalogos] = useState(null);
  const [cargando, setCargando] = useState(true);

  const refrescar = useCallback(async () => {
    if (!token.leer()) {
      setPerfil(null);
      setCupos(null);
      setCargando(false);
      return;
    }
    try {
      const r = await api.yo();
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

  const entrar = async (email, clave) => {
    const r = await api.login(email, clave);
    token.guardar(r.token);
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

  const salir = async () => {
    try {
      await api.logout();
    } finally {
      token.borrar();
      setPerfil(null);
      setCupos(null);
    }
  };

  return (
    <Ctx.Provider
      value={{
        perfil, cupos, catalogos, cargando,
        entrar, entrarConToken, registrar, salir, refrescar, setCupos,
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
