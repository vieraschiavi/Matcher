"""API HTTP de Matcher (FastAPI).

Es una cáscara fina: toda la lógica vive en `matcher/`. Cada handler valida la
entrada, llama al motor y traduce las excepciones del dominio a HTTP. Si algún
handler empieza a decidir reglas de negocio, la regla va al motor — si no, el
APK y los tests dejan de ver el mismo comportamiento que la web.

El mismo proceso sirve el frontend compilado (`webapp/frontend/dist`), así que
en producción no hay CORS ni segundo servidor: una app, un puerto.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from matcher import (
    aciegas,
    automatch,
    boost,
    cruces,
    crushtime,
    demo,
    filtros,
    geo,
    medios,
    oauth,
    pagos,
    planes,
    radar,
    scoring,
    segundavuelta,
    seguridad,
    vitrinas,
)
from matcher.almacen import Almacen, SinCupo
from matcher.modelos import (
    GENEROS,
    ORIENTACIONES,
    POLITICAS,
    DatosInvalidos,
    Perfil,
    Preferencias,
)

RAIZ = Path(__file__).resolve().parents[2]
DIST = RAIZ / "webapp" / "frontend" / "dist"
RUTA_BD = os.getenv("MATCHER_BD", str(RAIZ / "datos" / "matcher.db"))
# La demo se puebla sola al arrancar salvo que se apague explícitamente. Es lo
# que hace que `uvicorn` + navegador funcione sin ningún paso previo.
POBLAR_DEMO = os.getenv("MATCHER_DEMO", "1") == "1"

app = FastAPI(title="Matcher API", version="1.0.0")

# Orígenes permitidos.
#
# Cuando la web se sirve desde este mismo proceso no hay CORS que valga (es
# same-origin). Esta lista existe por dos casos: el frontend en modo dev y —el
# que importa— el WebView de la app instalada, que NO es same-origin: el
# bundle vive local y el backend está en otro dominio.
#
# El origen del WebView depende del `androidScheme`/`iosScheme` de
# capacitor.config.json. Con "https" (que es lo recomendado, porque habilita
# las APIs que exigen contexto seguro: cámara y geolocalización) el origen
# es **https://localhost**, no capacitor://localhost. Faltaba justo ese y la
# app instalada moría con "Failed to fetch" en el login, sin más pista.
# Van los dos esquemas para que un cambio de configuración no lo rompa igual.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://localhost",        # WebView con androidScheme/iosScheme https
        "capacitor://localhost",    # WebView con el esquema capacitor://
        "ionic://localhost",
        "http://localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_almacen: Almacen | None = None


def almacenamiento_efimero() -> bool:
    """¿La base vive en un disco que se borra?

    En serverless (Vercel) el único directorio escribible es `/tmp`, y además
    cada instancia tiene el suyo: una cuenta creada en una instancia no existe
    en la de al lado, y desaparece del todo en el próximo arranque en frío.
    Medido: de 40 pedidos en paralelo con una cuenta recién creada, 25 dieron
    401 porque el perfil no estaba en esa instancia.

    Se puede forzar con MATCHER_EFIMERO=0 si la base de /tmp está sobre un
    disco montado de verdad.
    """
    forzado = os.getenv("MATCHER_EFIMERO", "").strip()
    if forzado:
        return forzado == "1"
    return RUTA_BD.startswith("/tmp/")


def almacen() -> Almacen:
    global _almacen
    if _almacen is None:
        _almacen = Almacen(RUTA_BD)
        if POBLAR_DEMO:
            demo.poblar(_almacen)
    return _almacen


# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------
def usuario(authorization: str = Header(default="")) -> Perfil:
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(401, "falta el token de sesión")
    perfil = almacen().por_token(token)
    if not perfil:
        raise HTTPException(401, "sesión inválida o vencida")
    return perfil


def usuario_opcional(authorization: str = Header(default="")) -> Perfil | None:
    """El de arriba pero sin exigir sesión. Lo usa "más votados", que se puede
    mirar sin cuenta pero, con sesión, tiene que respetar los filtros."""
    token = authorization.removeprefix("Bearer ").strip()
    return almacen().por_token(token) if token else None


# ---------------------------------------------------------------------------
# Errores del dominio → HTTP
# ---------------------------------------------------------------------------
@app.exception_handler(DatosInvalidos)
async def _datos_invalidos(_: Request, exc: DatosInvalidos):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(SinCupo)
async def _sin_cupo(_: Request, exc: SinCupo):
    # 402 Payment Required. Es literalmente el caso: se acabó el cupo gratis.
    return JSONResponse(
        status_code=402,
        content={
            "detail": str(exc),
            "recurso": exc.recurso,
            "plan_sugerido": exc.plan_sugerido,
        },
    )


# ---------------------------------------------------------------------------
# Esquemas de entrada
# ---------------------------------------------------------------------------
class AltaPreferencias(BaseModel):
    generos: list[str] = Field(default_factory=list)
    busca: str | None = None  # legado: un cliente viejo puede seguir mandándolo
    edad_min: int = 18
    edad_max: int = 99
    altura_min_cm: int | None = None
    altura_max_cm: int | None = None
    politicas: list[str] = Field(default_factory=list)
    equipos: list[str] = Field(default_factory=list)
    intenciones: list[str] = Field(default_factory=list)
    solo_mi_pais: bool = False
    distancia_max_km: int | None = None
    solo_verificados: bool = False
    intereses: list[str] = Field(default_factory=list)


class Registro(BaseModel):
    email: str
    clave: str
    nombre: str
    nacimiento: str            # ISO YYYY-MM-DD
    genero: str
    altura_cm: int
    # País y ciudad son opcionales en el alta: el formulario ya no los
    # pregunta (el país se deduce del idioma del teléfono) y se completan
    # después desde "Mi perfil". Sin ciudad no hay radar, y la UI lo dice.
    pais: str = ""
    ciudad: str = ""
    politica: str = "neutro"
    equipo: str = ""
    bio: str = ""
    intereses: list[str] = Field(default_factory=list)
    preferencias: AltaPreferencias | None = None


class Credenciales(BaseModel):
    email: str
    clave: str


class CompletarAlta(BaseModel):
    """Lo que falta después de que el proveedor confirmó el email."""

    alta: str                  # token del alta pendiente
    nacimiento: str            # ISO YYYY-MM-DD
    genero: str
    altura_cm: int
    pais: str
    ciudad: str
    nombre: str | None = None
    politica: str = "neutro"
    equipo: str = ""
    bio: str = ""
    intereses: list[str] = Field(default_factory=list)
    preferencias: AltaPreferencias | None = None


class CambioPerfil(BaseModel):
    nombre: str | None = None
    altura_cm: int | None = None
    pais: str | None = None
    ciudad: str | None = None
    politica: str | None = None
    equipo: str | None = None
    bio: str | None = None
    intereses: list[str] | None = None
    intenciones: list[str] | None = None
    preferencias: AltaPreferencias | None = None


class AltaFoto(BaseModel):
    url: str
    bytes: int | None = None


class AltaVideo(BaseModel):
    url: str
    segundos: float | None = None
    bytes: int | None = None


class Interaccion(BaseModel):
    a_id: str
    tipo: str  # like | superfan | pass


class AltaMensaje(BaseModel):
    texto: str


class AltaCheckout(BaseModel):
    plan: str
    periodo: str = "mensual"


class Confirmacion(BaseModel):
    referencia: str


class AltaReporte(BaseModel):
    a_id: str
    motivo: str
    detalle: str = ""


class Ubicacion(BaseModel):
    lat: float
    lon: float


# ---------------------------------------------------------------------------
# Salud y catálogos
# ---------------------------------------------------------------------------
@app.get("/api/salud")
def salud():
    return {
        "ok": True,
        "version": app.version,
        "perfiles": len(almacen().todos()),
        "demo": POBLAR_DEMO,
        "pasarela": os.getenv("MATCHER_PASARELA", "demo"),
        # Si esto es False en un despliegue serverless, las sesiones se caen
        # solas: cada instancia firma con una clave distinta. Es un booleano,
        # nunca el secreto — /api/salud es público.
        "sesiones_compartidas": seguridad.secreto_compartido(),
        # Si el almacenamiento es efímero, la interfaz avisa antes de dejar
        # crear una cuenta. Una cuenta que se pierde en el próximo arranque en
        # frío no es un detalle técnico: es alguien que sube diez fotos y las
        # pierde, y hay que decírselo ANTES, no después.
        "almacenamiento_efimero": almacenamiento_efimero(),
    }


@app.get("/api/catalogos")
def catalogos():
    """Todo lo que el frontend necesita para armar los selectores. Un solo
    viaje: en 4G, tres requests para llenar tres combos se nota."""
    return {
        "paises": geo.paises_ordenados(),
        "generos": list(GENEROS),
        "orientaciones": list(ORIENTACIONES),
        "politicas": list(POLITICAS),
        "intereses": demo.INTERESES,
        "limites": {
            "fotos": medios.MAX_FOTOS,
            "videos": medios.MAX_VIDEOS,
            "segundos_video": medios.MAX_SEGUNDOS_VIDEO,
        },
    }


@app.get("/api/planes")
def catalogo_planes():
    return planes.catalogo()


# ---------------------------------------------------------------------------
# Cuenta
# ---------------------------------------------------------------------------
@app.post("/api/registro")
def registro(datos: Registro):
    import uuid

    try:
        nacimiento = date.fromisoformat(datos.nacimiento)
    except ValueError as e:
        raise DatosInvalidos("fecha de nacimiento inválida (usá AAAA-MM-DD)") from e

    perfil = Perfil(
        id=uuid.uuid4().hex[:12],
        email=datos.email,
        nombre=datos.nombre,
        nacimiento=nacimiento,
        genero=datos.genero,
        altura_cm=datos.altura_cm,
        pais=datos.pais,
        ciudad=datos.ciudad,
        politica=datos.politica,
        equipo=datos.equipo,
        bio=datos.bio,
        intereses=datos.intereses,
        preferencias=Preferencias.desde_dict(
            datos.preferencias.model_dump() if datos.preferencias else None
        ),
    )
    a = almacen()
    a.crear_perfil(perfil, datos.clave)
    sesion = a.login(datos.email, datos.clave)
    if not sesion:  # pragma: no cover — sólo si el hash falla
        raise HTTPException(500, "no se pudo iniciar sesión tras el registro")
    _, token = sesion
    return {"token": token, "perfil": perfil.a_dict(privado=True)}


@app.post("/api/login")
def login(datos: Credenciales):
    sesion = almacen().login(datos.email, datos.clave)
    if not sesion:
        # Mismo mensaje para email inexistente y clave errada: distinguirlos
        # convierte el login en un enumerador de cuentas.
        raise HTTPException(401, "email o contraseña incorrectos")
    perfil, token = sesion
    return {"token": token, "perfil": perfil.a_dict(privado=True)}


# ---------------------------------------------------------------------------
# Login con proveedor externo (Google)
# ---------------------------------------------------------------------------
def _base_publica(request: Request) -> str:
    """La URL pública del backend, para armar el redirect_uri.

    Se puede fijar con `MATCHER_URL_PUBLICA` y hay que hacerlo detrás de un
    proxy o en el APK: ahí `request.base_url` es la interna y el proveedor
    rechaza el callback por redirect_uri distinto al registrado.
    """
    return os.getenv("MATCHER_URL_PUBLICA", "").rstrip("/") or str(request.base_url).rstrip("/")


@app.get("/api/auth/proveedores")
def proveedores_de_login():
    """Sólo los que están configurados de verdad. El frontend no muestra un
    botón de "Continuar con Google" que no puede funcionar."""
    return {"proveedores": oauth.disponibles()}


@app.get("/api/auth/{nombre}/inicio")
def iniciar_login(nombre: str, request: Request, destino: str = oauth.DESTINO_WEB):
    """`destino=app` cuando el login sale de la app instalada: la vuelta va por
    enlace profundo en vez de una página web (ver `oauth.url_de_vuelta`)."""
    url, estado = oauth.url_de_autorizacion(nombre, _base_publica(request), destino)
    return {"url": url, "state": estado}


@app.get("/api/auth/{nombre}/callback")
def callback_login(
    nombre: str,
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
):
    """Vuelta del proveedor. Termina siempre en una redirección: a `/entrar`
    con el token si la cuenta ya existe, o a `/completar` si es la primera vez.

    A dónde va esa redirección lo decide el `destino` que viaja FIRMADO adentro
    del `state` — la web del backend, o un enlace profundo a la app instalada.
    Antes el valor que devolvía `consumir_estado` se descartaba y siempre se
    volvía a la web: en el APK eso significaba que el login "funcionaba" pero
    el token quedaba en el origen de la web y la app nunca se enteraba.
    """
    base = _base_publica(request)
    # Si el `state` no se puede leer no hay destino confiable, así que el error
    # vuelve por la web: es el único destino que no depende de datos del
    # atacante.
    if error:
        return RedirectResponse(
            oauth.url_de_vuelta(base, oauth.DESTINO_WEB, "/entrar", {"error": error})
        )

    destino = oauth.consumir_estado(state)
    acceso = oauth.intercambiar_codigo(nombre, code, base)
    datos = oauth.datos_del_usuario(nombre, acceso)

    a = almacen()
    perfil = a.buscar_por_email(datos["email"])
    if perfil:
        # La cuenta ya existe (por email y clave, o por un login anterior).
        # Se vincula la identidad y se entra: obligar a poner la contraseña a
        # quien acaba de probar su email con Google no protege de nada.
        if not perfil.activo:
            return RedirectResponse(
                oauth.url_de_vuelta(base, destino, "/entrar", {"error": "cuenta_desactivada"})
            )
        a.vincular_identidad(nombre, datos["email"], perfil.id)
        token = a.abrir_sesion(perfil)
        return RedirectResponse(oauth.url_de_vuelta(base, destino, "/entrar", {"token": token}))

    alta = a.guardar_alta_pendiente(nombre, datos["email"], datos["nombre"], datos["foto"])
    return RedirectResponse(oauth.url_de_vuelta(base, destino, "/completar", {"alta": alta}))


@app.get("/api/auth/alta/{token_alta}")
def leer_alta(token_alta: str):
    datos = almacen().leer_alta_pendiente(token_alta)
    if not datos:
        raise HTTPException(410, "el alta expiró; volvé a entrar con el proveedor")
    return {
        "email": datos["email"],
        "nombre": datos["nombre"],
        "foto": datos["foto"],
        "proveedor": datos["proveedor"],
    }


@app.post("/api/auth/completar")
def completar_alta(datos: CompletarAlta):
    """Crea la cuenta con el email que ya verificó el proveedor."""
    import uuid

    a = almacen()
    pendiente = a.leer_alta_pendiente(datos.alta, consumir=True)
    if not pendiente:
        raise HTTPException(410, "el alta expiró; volvé a entrar con el proveedor")
    try:
        nacimiento = date.fromisoformat(datos.nacimiento)
    except ValueError as e:
        raise DatosInvalidos("fecha de nacimiento inválida (usá AAAA-MM-DD)") from e

    perfil = Perfil(
        id=uuid.uuid4().hex[:12],
        email=pendiente["email"],
        nombre=(datos.nombre or pendiente["nombre"] or "").strip(),
        nacimiento=nacimiento,
        genero=datos.genero,
        altura_cm=datos.altura_cm,
        pais=datos.pais,
        ciudad=datos.ciudad,
        politica=datos.politica,
        equipo=datos.equipo,
        bio=datos.bio,
        intereses=datos.intereses,
        preferencias=Preferencias.desde_dict(
            datos.preferencias.model_dump() if datos.preferencias else None
        ),
        # El email lo confirmó el proveedor. No es lo mismo que "perfil
        # verificado" (eso es identidad con documento), así que NO se marca.
        verificado=False,
    )
    # Sin contraseña utilizable: se entra por el proveedor. Si alguna vez quiere
    # una, va por "olvidé mi contraseña" contra ese email.
    a.crear_perfil(perfil, seguridad.nuevo_token())
    a.vincular_identidad(pendiente["proveedor"], perfil.email, perfil.id)
    token = a.abrir_sesion(perfil)
    return {"token": token, "perfil": perfil.a_dict(privado=True)}


@app.post("/api/logout")
def logout(authorization: str = Header(default="")):
    almacen().logout(authorization.removeprefix("Bearer ").strip())
    return {"ok": True}


@app.get("/api/yo")
def yo(perfil: Perfil = Depends(usuario)):
    a = almacen()
    return {
        "perfil": perfil.a_dict(privado=True),
        "cupos": a.cupos(perfil),
        "medios": medios.resumen(perfil),
    }


@app.patch("/api/yo")
def editar(cambio: CambioPerfil, perfil: Perfil = Depends(usuario)):
    for campo in ("nombre", "altura_cm", "pais", "ciudad", "politica", "equipo", "bio"):
        valor = getattr(cambio, campo)
        if valor is not None:
            setattr(perfil, campo, valor)
    if cambio.intereses is not None:
        perfil.intereses = cambio.intereses
    if cambio.intenciones is not None:
        # "disponible_hoy" no se toca desde acá: tiene su propio endpoint
        # porque lleva un vencimiento, no es un valor que se guarda y listo.
        perfil.intenciones = [i for i in cambio.intenciones if i != "disponible_hoy"]
    if cambio.preferencias is not None:
        perfil.preferencias = Preferencias.desde_dict(cambio.preferencias.model_dump())
    almacen().guardar_perfil(perfil)
    return {"perfil": perfil.a_dict(privado=True)}


@app.post("/api/yo/disponible")
def marcar_disponible(perfil: Perfil = Depends(usuario)):
    """Prende "disponible hoy" por 24 h. Vence solo: sin vencimiento, a la
    semana medio padrón figuraría disponible y el filtro no diría nada."""
    perfil.marcar_disponible()
    almacen().guardar_perfil(perfil)
    return {"disponible_hasta": perfil.disponible_hasta.isoformat()}


@app.delete("/api/yo/disponible")
def apagar_disponible(perfil: Perfil = Depends(usuario)):
    perfil.disponible_hasta = None
    almacen().guardar_perfil(perfil)
    return {"ok": True}


@app.delete("/api/yo")
def borrar_cuenta(perfil: Perfil = Depends(usuario)):
    """Borra la cuenta de verdad: datos personales, ubicación y sesiones.

    Era una baja lógica (`activo = False`) y tenía dos problemas que aparecieron
    en la auditoría: el email quedaba ocupado, así que la persona no podía
    volver a registrarse NI entrar; y las dos tiendas exigen borrado real de
    cuenta (Apple 5.1.1(v), Google Play), no una desactivación.

    El detalle de qué se borra y qué se conserva está en `almacen.borrar_cuenta`.
    """
    almacen().borrar_cuenta(perfil)
    return {"ok": True, "borrada": True}


# ---------------------------------------------------------------------------
# Medios
# ---------------------------------------------------------------------------
# Los tres endpoints de medios devuelven el perfil ENTERO ya actualizado.
# Antes devolvían un resumen y el cliente hacía un GET /api/yo aparte; en
# serverless ese segundo pedido puede caer en otra instancia con otra base y
# devolver el estado viejo — se borraba una foto y en pantalla desaparecía
# otra. Con el perfil en la misma respuesta, lo que se ve es lo que hizo
# exactamente la instancia que procesó el cambio.
@app.post("/api/yo/fotos")
def subir_foto(datos: AltaFoto, perfil: Perfil = Depends(usuario)):
    media = medios.agregar_foto(perfil, datos.url, bytes_=datos.bytes)
    almacen().guardar_perfil(perfil)
    return {
        "media": media.a_dict(),
        "medios": medios.resumen(perfil),
        "perfil": perfil.a_dict(privado=True),
    }


@app.post("/api/yo/videos")
def subir_video(datos: AltaVideo, perfil: Perfil = Depends(usuario)):
    media = medios.agregar_video(
        perfil, datos.url, segundos=datos.segundos, bytes_=datos.bytes
    )
    almacen().guardar_perfil(perfil)
    return {
        "media": media.a_dict(),
        "medios": medios.resumen(perfil),
        "perfil": perfil.a_dict(privado=True),
    }


@app.delete("/api/yo/medios/{id_media}")
def borrar_media(id_media: str, perfil: Perfil = Depends(usuario)):
    if not medios.borrar(perfil, id_media):
        raise HTTPException(404, "no existe ese archivo en tu perfil")
    almacen().guardar_perfil(perfil)
    return {"medios": medios.resumen(perfil), "perfil": perfil.a_dict(privado=True)}


@app.post("/api/yo/medios/orden")
def reordenar_medios(ids: list[str] = Body(embed=True), perfil: Perfil = Depends(usuario)):
    medios.reordenar(perfil, ids)
    almacen().guardar_perfil(perfil)
    return {"perfil": perfil.a_dict(privado=True)}


# ---------------------------------------------------------------------------
# Deck e interacciones
# ---------------------------------------------------------------------------
@app.get("/api/deck")
def deck(limite: int = 20, perfil: Perfil = Depends(usuario)):
    a = almacen()
    a.tocar(perfil.id)
    return a.deck(perfil, limite=min(max(limite, 1), 50))


@app.post("/api/interacciones")
def interactuar(datos: Interaccion, perfil: Perfil = Depends(usuario)):
    return almacen().interactuar(perfil, datos.a_id, datos.tipo)


@app.post("/api/rebobinar")
def rebobinar(perfil: Perfil = Depends(usuario)):
    return almacen().rebobinar(perfil)


@app.get("/api/likes-recibidos")
def likes_recibidos(perfil: Perfil = Depends(usuario)):
    return almacen().quien_me_dio_like(perfil)


# ---------------------------------------------------------------------------
# Radar, ubicación y cruces
# ---------------------------------------------------------------------------
@app.post("/api/ubicacion")
def actualizar_ubicacion(datos: Ubicacion, perfil: Perfil = Depends(usuario)):
    """Ping de ubicación. Devuelve los cruces nuevos que detectó.

    Lo que se guarda es la CELDA, no la coordenada: el cliente manda precisión
    de GPS y el servidor la tira a propósito.
    """
    if not (-90 <= datos.lat <= 90 and -180 <= datos.lon <= 180):
        raise DatosInvalidos("coordenadas fuera de rango")
    return cruces.registrar_ping(almacen(), perfil, datos.lat, datos.lon)


@app.get("/api/radar")
def ver_radar(radio_km: float = radar.RADIO_DEFECTO_KM, perfil: Perfil = Depends(usuario)):
    a = almacen()
    a.tocar(perfil.id)
    return radar.alrededor(a, perfil, radio_km=radio_km)


@app.get("/api/cruces")
def mis_cruces(perfil: Perfil = Depends(usuario)):
    a = almacen()
    return {"resumen": cruces.resumen(a, perfil), "personas": cruces.de(a, perfil)}


@app.get("/api/ranking")
def ranking(limite: int = 20, perfil: Perfil | None = Depends(usuario_opcional)):
    """"Más votados". Se puede mirar sin cuenta: es la vitrina de la app y lo
    que la hace divertida aunque no estés swipeando.

    Pero CON sesión respeta tus filtros. Se escapaba: era el único listado de
    gente que ni siquiera recibía el usuario, así que quien pedía ver sólo
    mujeres encontraba hombres acá. La vitrina no es excusa — la regla es que
    el filtro vale en todas las pantallas.
    """
    universo = almacen().todos()
    if perfil:
        universo = [
            o for o in universo if filtros.pasa_filtros(perfil, o, reciproco=False)[0]
        ]
    return {"top": scoring.top_votados(universo, min(max(limite, 1), 50))}


# ---------------------------------------------------------------------------
# Match automático
# ---------------------------------------------------------------------------
@app.get("/api/automatch/sugerencias")
def sugerencias_automatch(perfil: Perfil = Depends(usuario)):
    a = almacen()
    salida = automatch.sugerencias(a, perfil)
    return {
        "umbral": automatch.UMBRAL,
        "cupos": a.cupos(perfil),
        "sugerencias": [
            s["perfil"].a_dict()
            | {"compatibilidad": s["compatibilidad"], "motivos": s["motivos"]}
            for s in salida
        ],
    }


@app.post("/api/automatch")
def correr_automatch(perfil: Perfil = Depends(usuario)):
    a = almacen()
    creados = automatch.proponer(a, perfil)
    return {"creados": creados, "cupos": a.cupos(perfil)}


# ---------------------------------------------------------------------------
# Matches y chat
# ---------------------------------------------------------------------------
@app.get("/api/boost")
def boost_estado(perfil: Perfil = Depends(usuario)):
    return boost.estado(almacen(), perfil)


@app.post("/api/boost")
def boost_activar(perfil: Perfil = Depends(usuario)):
    try:
        return boost.activar(almacen(), perfil)
    except boost.SinBoosts as e:
        raise SinCupo(str(e), recurso="boost", plan_sugerido="plus") from e


@app.get("/api/top-dia")
def top_del_dia(perfil: Perfil = Depends(usuario)):
    """Los más likeados de HOY, filtrados y listos para dar like."""
    return {"top": almacen().top_del_dia(perfil)}


# ---------------------------------------------------------------------------
# Vitrinas: disponibles hoy y más likeados por zona
# ---------------------------------------------------------------------------
@app.get("/api/disponibles")
def disponibles(limite: int = 60, perfil: Perfil = Depends(usuario)):
    """Quién dijo que sale hoy. Ordenado por cercanía antes que por puntaje:
    en esta sección "está cerca" vale más que "es muy compatible"."""
    return vitrinas.disponibles_hoy(almacen(), perfil, limite=limite)


@app.get("/api/segunda-vuelta")
def segunda_vuelta(perfil: Perfil = Depends(usuario)):
    """Los descartes viejos que hoy pasarían tus filtros. Mirar es gratis;
    repescar gasta un like común (ver `matcher/segundavuelta.py`)."""
    return {
        "dias_espera": segundavuelta.DIAS_ESPERA,
        "personas": segundavuelta.candidatos(almacen(), perfil),
    }


@app.post("/api/segunda-vuelta/{a_id}")
def repescar(a_id: str, perfil: Perfil = Depends(usuario)):
    return segundavuelta.repescar(almacen(), perfil, a_id)


@app.get("/api/mas-likeados")
def mas_likeados(
    alcance: str = "ciudad",
    limite: int = vitrinas.TOPE_LISTA,
    perfil: Perfil = Depends(usuario),
):
    """Los 200 más likeados del barrio, de la ciudad o del mundo.

    Pide sesión —a diferencia de `/api/ranking`, que es la vitrina pública— por
    dos motivos: el alcance se calcula contra TU ciudad y TU posición, y la
    lista respeta TUS filtros. Sin usuario no hay ninguna de las dos cosas.
    """
    return vitrinas.mas_likeados(almacen(), perfil, alcance=alcance, limite=limite)


# ---------------------------------------------------------------------------
# Crush Time
# ---------------------------------------------------------------------------
@app.get("/api/crushtime")
def crushtime_estado(perfil: Perfil = Depends(usuario)):
    return crushtime.estado(almacen(), perfil)


@app.post("/api/crushtime/ronda")
def crushtime_ronda(perfil: Perfil = Depends(usuario)):
    try:
        return crushtime.nueva_ronda(almacen(), perfil)
    except crushtime.SinTurnos as e:
        # Mismo contrato que los likes agotados: 402 con plan sugerido, así el
        # frontend reusa el muro de pago que ya existe.
        raise SinCupo(str(e), recurso="crushtime", plan_sugerido="plus") from e


@app.post("/api/crushtime/adivinar")
def crushtime_adivinar(
    ronda: str = Body(embed=True),
    elegido: str = Body(embed=True),
    perfil: Perfil = Depends(usuario),
):
    return crushtime.adivinar(almacen(), perfil, ronda, elegido)


@app.post("/api/aciegas")
def cita_a_ciegas(perfil: Perfil = Depends(usuario)):
    """Abre una cita a ciegas: chat sí, fotos no, hasta que los dos escriban.

    La elección respeta los filtros duros de los dos lados; las fotos no
    salen del servidor hasta la revelación (ver `matcher/aciegas.py`).
    """
    m = aciegas.crear(almacen(), perfil)
    return {"match_id": m.id, "umbral": aciegas.UMBRAL}


@app.get("/api/matches")
def lista_matches(perfil: Perfil = Depends(usuario)):
    return {"matches": almacen().matches_de(perfil.id)}


@app.get("/api/matches/{match_id}/mensajes")
def leer_chat(match_id: str, perfil: Perfil = Depends(usuario)):
    return {"mensajes": almacen().conversacion(match_id, perfil)}


@app.post("/api/matches/{match_id}/mensajes")
def escribir_chat(match_id: str, datos: AltaMensaje, perfil: Perfil = Depends(usuario)):
    m = almacen().enviar_mensaje(match_id, perfil, datos.texto)
    return {"mensaje": m.a_dict()}


@app.delete("/api/matches/{match_id}")
def borrar_match(match_id: str, perfil: Perfil = Depends(usuario)):
    almacen().deshacer_match(match_id, perfil)
    return {"ok": True}


@app.post("/api/reportes")
def reportar(datos: AltaReporte, perfil: Perfil = Depends(usuario)):
    almacen().reportar(perfil, datos.a_id, datos.motivo, datos.detalle)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Pagos
# ---------------------------------------------------------------------------
@app.post("/api/pagos/checkout")
def checkout(datos: AltaCheckout, perfil: Perfil = Depends(usuario)):
    return {"checkout": pagos.iniciar(almacen(), perfil, datos.plan, datos.periodo).a_dict()}


@app.post("/api/pagos/confirmar")
def confirmar_pago(datos: Confirmacion, perfil: Perfil = Depends(usuario)):
    a = almacen()
    resultado = pagos.confirmar(a, perfil, datos.referencia)
    return {"resultado": resultado, "perfil": a.perfil(perfil.id).a_dict(privado=True)}


@app.post("/api/pagos/cancelar")
def cancelar_plan(perfil: Perfil = Depends(usuario)):
    return pagos.cancelar(almacen(), perfil)


@app.get("/api/pagos")
def historial_pagos(perfil: Perfil = Depends(usuario)):
    return {"pagos": almacen().pagos_de(perfil.id)}


@app.get("/api/pagos/planes-disponibles")
def pasarelas_disponibles():
    """Qué pasarela está activa y si sus credenciales están completas. Sirve
    para que la UI de Planes le avise al usuario ANTES de que llegue al
    checkout, en vez de fallar recién al tocar "Pagar"."""
    nombre = os.getenv("MATCHER_PASARELA", "demo")
    try:
        pagos.pasarela_activa()
        lista = True
    except DatosInvalidos:
        lista = False
    return {"pasarela": nombre, "configurada": lista}


async def _webhook(request: Request, nombre_pasarela: str) -> JSONResponse:
    """Cuerpo común a los tres webhooks: verificar la firma ANTES de tocar
    nada. Un webhook sin verificar es que cualquiera en internet pueda
    activarte un plan gratis mandando el POST a mano."""
    cuerpo = await request.body()
    pasarela = pagos.pasarela_por_nombre(nombre_pasarela)
    if not pasarela.verificar_webhook(cuerpo, dict(request.headers)):
        raise HTTPException(400, "firma inválida")

    try:
        datos = json.loads(cuerpo or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(400, "cuerpo inválido") from None

    # Cada proveedor manda "cuál es mi pago" en un lugar distinto del cuerpo.
    referencia = (
        datos.get("external_reference")  # MercadoPago (cuando viene en el payload)
        or datos.get("order_id")  # dLocal
        or next(
            (
                u.get("reference_id")
                for u in datos.get("resource", {}).get("purchase_units", [])  # PayPal
            ),
            None,
        )
    )
    if not referencia:
        # No es un error del cliente: es un evento que este webhook no sabe
        # interpretar (p.ej. una notificación de MercadoPago que sólo trae el
        # id de pago y hay que ir a buscarlo a la API). Se responde 200 para
        # que el proveedor no reintente indefinidamente, y no se confirma nada.
        return JSONResponse({"ok": True, "procesado": False})

    resultado = pagos.confirmar_por_referencia(almacen(), referencia)
    return JSONResponse({"ok": True, "procesado": True, "resultado": resultado})


@app.post("/api/pagos/webhook/mercadopago")
async def webhook_mercadopago(request: Request):
    return await _webhook(request, "mercadopago")


@app.post("/api/pagos/webhook/paypal")
async def webhook_paypal(request: Request):
    return await _webhook(request, "paypal")


@app.post("/api/pagos/webhook/dlocal")
async def webhook_dlocal(request: Request):
    return await _webhook(request, "dlocal")


# ---------------------------------------------------------------------------
# Frontend compilado
# ---------------------------------------------------------------------------
if DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/")
    def raiz():
        return FileResponse(DIST / "index.html")

    @app.get("/{ruta:path}")
    def spa(ruta: str):
        """HashRouter, así que todo lo que no sea /api cae en index.html."""
        archivo = DIST / ruta
        if archivo.is_file():
            return FileResponse(archivo)
        return FileResponse(DIST / "index.html")


def main() -> None:  # pragma: no cover
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("MATCHER_HOST", "127.0.0.1"),
        port=int(os.getenv("MATCHER_PUERTO", "8820")),
    )


if __name__ == "__main__":  # pragma: no cover
    main()
