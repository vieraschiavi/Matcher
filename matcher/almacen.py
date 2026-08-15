"""Persistencia en SQLite (biblioteca estándar) y reglas de interacción.

Por qué SQLite y no un ORM: el motor tiene que poder correr desde un test,
desde el backend y desde un `.bat` sin instalar nada. Un solo archivo `.db`
también hace que la demo sea reproducible — se borra el archivo y se vuelve al
estado inicial.

El perfil se guarda como JSON en una columna y sólo se indexan `id` y `email`.
Es deliberado: el esquema del perfil todavía se mueve, y migrar columnas en
cada cambio de producto costaría más de lo que ahorra. Las consultas que
importan (deck, matches, cupos) van por tablas relacionales de verdad.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from pathlib import Path

from . import filtros, planes, scoring, seguridad
from .modelos import (
    DatosInvalidos,
    Match,
    Media,
    Mensaje,
    Perfil,
    Preferencias,
)

ESQUEMA = """
CREATE TABLE IF NOT EXISTS perfiles (
    id          TEXT PRIMARY KEY,
    email       TEXT NOT NULL UNIQUE,
    clave_hash  TEXT NOT NULL,
    datos       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS interacciones (
    id      TEXT PRIMARY KEY,
    de_id   TEXT NOT NULL,
    a_id    TEXT NOT NULL,
    tipo    TEXT NOT NULL,
    momento TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_int_de   ON interacciones(de_id, momento);
CREATE INDEX IF NOT EXISTS ix_int_a    ON interacciones(a_id, tipo);
CREATE UNIQUE INDEX IF NOT EXISTS ux_int_par ON interacciones(de_id, a_id);
CREATE TABLE IF NOT EXISTS matches (
    id             TEXT PRIMARY KEY,
    a_id           TEXT NOT NULL,
    b_id           TEXT NOT NULL,
    momento        TEXT NOT NULL,
    automatico     INTEGER NOT NULL DEFAULT 0,
    compatibilidad REAL NOT NULL DEFAULT 0,
    -- Cita a ciegas: el chat existe pero las fotos no viajan hasta que los
    -- dos escribieron lo suficiente (ver `aciegas.py`).
    ciego          INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_match_par ON matches(a_id, b_id);
CREATE TABLE IF NOT EXISTS mensajes (
    id       TEXT PRIMARY KEY,
    match_id TEXT NOT NULL,
    de_id    TEXT NOT NULL,
    texto    TEXT NOT NULL,
    momento  TEXT NOT NULL,
    leido    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_msg_match ON mensajes(match_id, momento);
CREATE TABLE IF NOT EXISTS pagos (
    id         TEXT PRIMARY KEY,
    usuario_id TEXT NOT NULL,
    plan       TEXT NOT NULL,
    periodo    TEXT NOT NULL,
    monto      REAL NOT NULL,
    moneda     TEXT NOT NULL,
    estado     TEXT NOT NULL,
    pasarela   TEXT NOT NULL,
    referencia TEXT NOT NULL,
    momento    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sesiones (
    token      TEXT PRIMARY KEY,
    usuario_id TEXT NOT NULL,
    creado     TEXT NOT NULL
);
-- Tokens firmados que ya no valen: sesiones cerradas y altas ya usadas. Sin
-- esta lista, la verificación por firma los seguiría aceptando y ni el logout
-- ni el "de un solo uso" del alta cerrarían nada.
CREATE TABLE IF NOT EXISTS tokens_revocados (
    token   TEXT PRIMARY KEY,
    momento TEXT NOT NULL
);
-- Crush Time: rondas del juego de adivinar quién te dio like. La fecha va
-- aparte del momento porque el cupo es POR DÍA y contar por fecha es un
-- índice simple; parsear timestamps para eso es buscarse un bug de huso.
CREATE TABLE IF NOT EXISTS crushtime (
    id          TEXT PRIMARY KEY,
    usuario_id  TEXT NOT NULL,
    fecha       TEXT NOT NULL,
    objetivo_id TEXT NOT NULL,
    opciones    TEXT NOT NULL,
    resuelto    INTEGER NOT NULL DEFAULT 0,
    momento     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_crush_dia ON crushtime(usuario_id, fecha);
CREATE TABLE IF NOT EXISTS reportes (
    id         TEXT PRIMARY KEY,
    de_id      TEXT NOT NULL,
    a_id       TEXT NOT NULL,
    motivo     TEXT NOT NULL,
    detalle    TEXT NOT NULL DEFAULT '',
    momento    TEXT NOT NULL
);
-- Login con Google: qué proveedor usó cada cuenta. Se guarda aparte del perfil
-- porque una misma cuenta puede sumar más de un proveedor con el tiempo.
CREATE TABLE IF NOT EXISTS identidades (
    proveedor  TEXT NOT NULL,
    email      TEXT NOT NULL,
    usuario_id TEXT NOT NULL,
    creado     TEXT NOT NULL,
    PRIMARY KEY (proveedor, email)
);
-- Alta a medio hacer: el proveedor ya confirmó el email, pero todavía faltan
-- los datos que sólo puede dar la persona (nacimiento, género, ciudad…). Se
-- guarda acá y no como perfil incompleto: un perfil a medias entra a consultas
-- que no lo esperan y ensucia el deck.
-- Ubicación: sólo la ÚLTIMA de cada persona, ya redondeada a celda de mapa.
-- No hay tabla de historial a propósito — ver matcher/cruces.py.
CREATE TABLE IF NOT EXISTS ubicaciones (
    usuario_id TEXT PRIMARY KEY,
    lat        REAL NOT NULL,
    lon        REAL NOT NULL,
    momento    TEXT NOT NULL
);
-- Pings efímeros para detectar cruces. Se borran solos a las 6 horas.
CREATE TABLE IF NOT EXISTS pings (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id TEXT NOT NULL,
    celda      TEXT NOT NULL,
    momento    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_ping_celda ON pings(celda, momento);
CREATE INDEX IF NOT EXISTS ix_ping_momento ON pings(momento);
-- Cruces acumulados. Par ordenado, igual que los matches.
CREATE TABLE IF NOT EXISTS cruces (
    a_id     TEXT NOT NULL,
    b_id     TEXT NOT NULL,
    veces    INTEGER NOT NULL DEFAULT 1,
    primera  TEXT NOT NULL,
    ultima   TEXT NOT NULL,
    cerca_de TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (a_id, b_id)
);
CREATE TABLE IF NOT EXISTS altas_pendientes (
    token     TEXT PRIMARY KEY,
    proveedor TEXT NOT NULL,
    email     TEXT NOT NULL,
    nombre    TEXT NOT NULL DEFAULT '',
    foto      TEXT NOT NULL DEFAULT '',
    creado    TEXT NOT NULL
);
"""

# Un alta a medio hacer no puede quedar viva para siempre: es un email
# verificado esperando a que alguien lo reclame.
VIDA_ALTA_PENDIENTE = timedelta(hours=2)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _dt(texto: str | None) -> datetime | None:
    return datetime.fromisoformat(texto) if texto else None


class SinCupo(Exception):
    """Se acabó el cupo del plan. La API lo traduce a HTTP 402 con el detalle
    de qué plan lo destraba — es el momento exacto donde se vende."""

    def __init__(self, mensaje: str, recurso: str, plan_sugerido: str = "plus"):
        super().__init__(mensaje)
        self.recurso = recurso
        self.plan_sugerido = plan_sugerido


class Almacen:
    """Acceso a la base.

    Dos cosas que parecen detalle y no lo son, las dos aprendidas de 500 en
    producción:

    1. **Una conexión por hilo.** FastAPI atiende los endpoints sincrónicos en
       un pool de hilos. Con una sola conexión compartida (`check_same_thread=
       False`) las transacciones de dos hilos se entreveran: uno abre y el otro
       cierra, y salta "cannot commit - no transaction is active".
    2. **`isolation_level="IMMEDIATE"`.** Con el default, la transacción arranca
       como lectora y pide subir a escritora en el primer UPDATE. Esa subida NO
       respeta `busy_timeout`: falla al toque con "database is locked". Pidiendo
       el lock de escritura de entrada, el que llega segundo hace la cola.

    En `:memory:` la conexión es única a propósito: cada conexión a memoria es
    una base distinta, así que una por hilo daría bases vacías.
    """

    def __init__(self, ruta: str | Path = ":memory:"):
        self.ruta = str(ruta)
        self.en_memoria = self.ruta == ":memory:"
        if not self.en_memoria:
            Path(self.ruta).parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._compartida = self._nueva_conexion() if self.en_memoria else None
        con = self.con
        con.executescript(ESQUEMA)
        # Migración mínima: CREATE IF NOT EXISTS no agrega columnas a una base
        # que ya existía. El ALTER falla con "duplicate column" cuando la
        # columna ya está, y eso es exactamente el caso feliz.
        try:
            con.execute("ALTER TABLE matches ADD COLUMN ciego INTEGER NOT NULL DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        con.commit()

    def _nueva_conexion(self) -> sqlite3.Connection:
        con = sqlite3.connect(
            self.ruta, check_same_thread=False, timeout=15, isolation_level="IMMEDIATE"
        )
        con.row_factory = sqlite3.Row
        if not self.en_memoria:
            # En serverless varias invocaciones corren en procesos distintos de
            # la MISMA instancia, todos sobre el mismo archivo en /tmp. WAL deja
            # leer mientras alguien escribe; sin él, un lector y un escritor a
            # la vez se pisan.
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA synchronous=NORMAL")
        con.execute("PRAGMA busy_timeout=15000")
        return con

    @property
    def con(self) -> sqlite3.Connection:
        if self._compartida is not None:
            return self._compartida
        con = getattr(self._local, "con", None)
        if con is None:
            con = self._nueva_conexion()
            self._local.con = con
        return con

    def cerrar(self) -> None:
        if self._compartida is not None:
            self._compartida.close()
            self._compartida = None
            return
        con = getattr(self._local, "con", None)
        if con is not None:
            con.close()
            self._local.con = None

    # ------------------------------------------------------------------
    # Serialización de perfiles
    # ------------------------------------------------------------------
    @staticmethod
    def _a_json(p: Perfil) -> str:
        return json.dumps(
            {
                "id": p.id,
                "email": p.email,
                "nombre": p.nombre,
                "nacimiento": p.nacimiento.isoformat(),
                "genero": p.genero,
                "altura_cm": p.altura_cm,
                "pais": p.pais,
                "ciudad": p.ciudad,
                "politica": p.politica,
                "equipo": p.equipo,
                "bio": p.bio,
                "intereses": p.intereses,
                "fotos": [m.a_dict() for m in p.fotos],
                "videos": [m.a_dict() for m in p.videos],
                "preferencias": p.preferencias.a_dict(),
                "plan": p.plan,
                "plan_vence": _iso(p.plan_vence),
                "verificado": p.verificado,
                "activo": p.activo,
                "sintetico": p.sintetico,
                "creado": _iso(p.creado),
                "ultima_actividad": _iso(p.ultima_actividad),
                "likes_recibidos": p.likes_recibidos,
                "superfans_recibidos": p.superfans_recibidos,
                "vistas_recibidas": p.vistas_recibidas,
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _desde_json(texto: str) -> Perfil:
        d = json.loads(texto)
        return Perfil(
            id=d["id"],
            email=d["email"],
            nombre=d["nombre"],
            nacimiento=date.fromisoformat(d["nacimiento"]),
            genero=d["genero"],
            altura_cm=int(d["altura_cm"]),
            pais=d["pais"],
            ciudad=d["ciudad"],
            politica=d.get("politica", "neutro"),
            equipo=d.get("equipo", ""),
            bio=d.get("bio", ""),
            intereses=list(d.get("intereses") or []),
            fotos=[Media.desde_dict(m) for m in d.get("fotos") or []],
            videos=[Media.desde_dict(m) for m in d.get("videos") or []],
            preferencias=Preferencias.desde_dict(d.get("preferencias")),
            plan=d.get("plan", "gratis"),
            plan_vence=_dt(d.get("plan_vence")),
            verificado=bool(d.get("verificado", False)),
            activo=bool(d.get("activo", True)),
            sintetico=bool(d.get("sintetico", False)),
            creado=_dt(d.get("creado")) or datetime.utcnow(),
            ultima_actividad=_dt(d.get("ultima_actividad")) or datetime.utcnow(),
            likes_recibidos=int(d.get("likes_recibidos", 0)),
            superfans_recibidos=int(d.get("superfans_recibidos", 0)),
            vistas_recibidas=int(d.get("vistas_recibidas", 0)),
        )

    # ------------------------------------------------------------------
    # Alta y lectura de perfiles
    # ------------------------------------------------------------------
    def crear_perfil(self, perfil: Perfil, clave: str) -> Perfil:
        perfil.email = perfil.email.strip().lower()
        perfil.validar()
        if self.buscar_por_email(perfil.email):
            raise DatosInvalidos("ya existe una cuenta con ese email")
        self.con.execute(
            "INSERT INTO perfiles (id, email, clave_hash, datos) VALUES (?,?,?,?)",
            (perfil.id, perfil.email, seguridad.hashear(clave), self._a_json(perfil)),
        )
        self.con.commit()
        return perfil

    def guardar_perfil(self, perfil: Perfil) -> Perfil:
        perfil.validar()
        cur = self.con.execute(
            "UPDATE perfiles SET email = ?, datos = ? WHERE id = ?",
            (perfil.email.strip().lower(), self._a_json(perfil), perfil.id),
        )
        if cur.rowcount == 0:
            raise DatosInvalidos(f"no existe el perfil {perfil.id}")
        self.con.commit()
        return perfil

    def perfil(self, id_: str) -> Perfil | None:
        fila = self.con.execute("SELECT datos FROM perfiles WHERE id = ?", (id_,)).fetchone()
        return self._desde_json(fila["datos"]) if fila else None

    def buscar_por_email(self, email: str) -> Perfil | None:
        fila = self.con.execute(
            "SELECT datos FROM perfiles WHERE email = ?", (email.strip().lower(),)
        ).fetchone()
        return self._desde_json(fila["datos"]) if fila else None

    def todos(self, incluir_inactivos: bool = False) -> list[Perfil]:
        filas = self.con.execute("SELECT datos FROM perfiles").fetchall()
        perfiles = [self._desde_json(f["datos"]) for f in filas]
        return perfiles if incluir_inactivos else [p for p in perfiles if p.activo]

    def cambiar_clave(self, id_: str, nueva: str) -> None:
        self.con.execute(
            "UPDATE perfiles SET clave_hash = ? WHERE id = ?", (seguridad.hashear(nueva), id_)
        )
        self.con.commit()

    # ------------------------------------------------------------------
    # Sesiones
    # ------------------------------------------------------------------
    def login(self, email: str, clave: str) -> tuple[Perfil, str] | None:
        fila = self.con.execute(
            "SELECT id, clave_hash, datos FROM perfiles WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()
        if not fila or not seguridad.verificar(clave, fila["clave_hash"]):
            return None
        perfil = self._desde_json(fila["datos"])
        if not perfil.activo:
            return None
        token = seguridad.firmar_sesion(perfil.id)
        self.con.execute(
            "INSERT INTO sesiones (token, usuario_id, creado) VALUES (?,?,?)",
            (token, perfil.id, datetime.utcnow().isoformat()),
        )
        self.con.commit()
        self.tocar(perfil.id)
        return perfil, token

    def abrir_sesion(self, perfil: Perfil) -> str:
        """Emite un token sin pedir contraseña.

        La usa el login con proveedor externo: ahí quien verificó la identidad
        es Google, no nosotros. No la expongas por HTTP sin esa verificación
        previa — sería un login sin credenciales.
        """
        token = seguridad.firmar_sesion(perfil.id)
        self.con.execute(
            "INSERT INTO sesiones (token, usuario_id, creado) VALUES (?,?,?)",
            (token, perfil.id, datetime.utcnow().isoformat()),
        )
        self.con.commit()
        self.tocar(perfil.id)
        return token

    # -- login con proveedor externo ------------------------------------
    def vincular_identidad(self, proveedor: str, email: str, usuario_id: str) -> None:
        self.con.execute(
            "INSERT OR REPLACE INTO identidades (proveedor, email, usuario_id, creado) "
            "VALUES (?,?,?,?)",
            (proveedor, email.strip().lower(), usuario_id, datetime.utcnow().isoformat()),
        )
        self.con.commit()

    def proveedores_de(self, usuario_id: str) -> list[str]:
        filas = self.con.execute(
            "SELECT proveedor FROM identidades WHERE usuario_id = ?", (usuario_id,)
        ).fetchall()
        return [f["proveedor"] for f in filas]

    def guardar_alta_pendiente(self, proveedor: str, email: str, nombre: str, foto: str) -> str:
        """Alta a medio hacer: el proveedor ya verificó el email y falta que la
        persona complete el resto. Devuelve el token del alta.

        Va firmado además de guardado, por el mismo motivo que las sesiones: el
        callback de Google puede caer en una instancia y la pantalla de
        "completar" pegarle a otra, que no tendría la fila y contestaría "el
        alta expiró" sin que haya expirado nada.

        Al consumirla se anota en `tokens_revocados`: borrar la fila no alcanza,
        porque la verificación por firma la resucitaría y el alta dejaría de ser
        de un solo uso.
        """
        self.con.execute(
            "DELETE FROM altas_pendientes WHERE creado < ?",
            ((datetime.utcnow() - VIDA_ALTA_PENDIENTE).isoformat(),),
        )
        token = seguridad.firmar_datos(
            {
                "p": proveedor,
                "e": email.strip().lower(),
                "nom": nombre,
                "f": foto,
            }
        )
        self.con.execute(
            "INSERT INTO altas_pendientes (token, proveedor, email, nombre, foto, creado) "
            "VALUES (?,?,?,?,?,?)",
            (token, proveedor, email.strip().lower(), nombre, foto,
             datetime.utcnow().isoformat()),
        )
        self.con.commit()
        return token

    def leer_alta_pendiente(self, token: str, consumir: bool = False) -> dict | None:
        if self._revocado(token):
            return None

        fila = self.con.execute(
            "SELECT * FROM altas_pendientes WHERE token = ?", (token,)
        ).fetchone()
        if fila:
            if _dt(fila["creado"]) < datetime.utcnow() - VIDA_ALTA_PENDIENTE:
                self.con.execute("DELETE FROM altas_pendientes WHERE token = ?", (token,))
                self.con.commit()
                return None
            if consumir:
                self.con.execute("DELETE FROM altas_pendientes WHERE token = ?", (token,))
                self._revocar(token)
                self.con.commit()
            return dict(fila)

        # No está en esta base: puede haberla emitido otra instancia.
        datos = seguridad.leer_datos(token, int(VIDA_ALTA_PENDIENTE.total_seconds()))
        if not datos:
            return None
        if consumir:
            self._revocar(token)
            self.con.commit()
        return {
            "token": token,
            "proveedor": datos.get("p", ""),
            "email": datos.get("e", ""),
            "nombre": datos.get("nom", ""),
            "foto": datos.get("f", ""),
        }

    def por_token(self, token: str) -> Perfil | None:
        fila = self.con.execute(
            "SELECT usuario_id FROM sesiones WHERE token = ?", (token,)
        ).fetchone()
        if fila:
            return self.perfil(fila["usuario_id"])

        # La sesión no está en ESTA base. Puede ser porque se cerró, o porque
        # el token lo emitió otra instancia serverless con su propio disco
        # efímero. La firma distingue los dos casos sin compartir estado.
        usuario_id = seguridad.leer_sesion(token)
        if not usuario_id or self._revocado(token):
            return None
        return self.perfil(usuario_id)

    def _revocado(self, token: str) -> bool:
        fila = self.con.execute(
            "SELECT 1 FROM tokens_revocados WHERE token = ?", (token,)
        ).fetchone()
        return fila is not None

    def _revocar(self, token: str) -> None:
        self.con.execute(
            "INSERT OR REPLACE INTO tokens_revocados (token, momento) VALUES (?,?)",
            (token, datetime.utcnow().isoformat()),
        )

    def logout(self, token: str) -> None:
        """Cierra la sesión.

        Se borra la fila y además se anota el token como revocado: si no,
        `por_token` lo aceptaría por la firma y el logout no cerraría nada.

        Ojo con el disco efímero: la lista de revocados se pierde igual que el
        resto de la base, así que ahí un token cerrado sigue sirviendo en otra
        instancia hasta que vence. Revocar de verdad necesita una base con
        disco (ver MATCHER_BD).
        """
        self.con.execute("DELETE FROM sesiones WHERE token = ?", (token,))
        if seguridad.leer_sesion(token):
            self._revocar(token)
        self.con.commit()

    def tocar(self, id_: str) -> None:
        """Marca actividad reciente. Alimenta `scoring.actividad`.

        Es la escritura más frecuente de todas —una por pedido autenticado— y
        la menos importante: si no se puede anotar porque otro proceso tiene la
        base tomada, se sigue. Antes esto tiraba la petición entera con un 500
        y el usuario perdía la pantalla por no poder guardar un timestamp.
        """
        p = self.perfil(id_)
        if not p:
            return
        p.ultima_actividad = datetime.utcnow()
        try:
            self.con.execute(
                "UPDATE perfiles SET datos = ? WHERE id = ?", (self._a_json(p), p.id)
            )
            self.con.commit()
        except sqlite3.OperationalError:
            pass

    # ------------------------------------------------------------------
    # Cupos
    # ------------------------------------------------------------------
    def _contar_desde(self, de_id: str, tipos: Iterable[str], desde: datetime) -> int:
        marcas = ",".join("?" for _ in tipos)
        fila = self.con.execute(
            f"SELECT COUNT(*) c FROM interacciones "
            f"WHERE de_id = ? AND tipo IN ({marcas}) AND momento >= ?",
            (de_id, *tipos, desde.isoformat()),
        ).fetchone()
        return fila["c"]

    def cupos(self, perfil: Perfil, ahora: datetime | None = None) -> dict:
        ahora = ahora or datetime.utcnow()
        lim = planes.limites_de(perfil)
        inicio_dia = datetime(ahora.year, ahora.month, ahora.day)
        inicio_semana = inicio_dia - timedelta(days=inicio_dia.weekday())
        likes_hoy = self._contar_desde(perfil.id, ("like",), inicio_dia)
        superfans_semana = self._contar_desde(perfil.id, ("superfan",), inicio_semana)
        automatch_hoy = self.con.execute(
            "SELECT COUNT(*) c FROM matches "
            "WHERE automatico = 1 AND (a_id = ? OR b_id = ?) AND momento >= ?",
            (perfil.id, perfil.id, inicio_dia.isoformat()),
        ).fetchone()["c"]
        return {
            "plan": perfil.plan if perfil.es_premium else "gratis",
            "likes_hoy": likes_hoy,
            "likes_max": lim.likes_por_dia,
            "likes_restantes": (
                None if lim.likes_por_dia is None else max(0, lim.likes_por_dia - likes_hoy)
            ),
            "superfans_semana": superfans_semana,
            "superfans_max": lim.superfans_por_semana,
            "superfans_restantes": max(0, lim.superfans_por_semana - superfans_semana),
            "automatch_hoy": automatch_hoy,
            "automatch_max": lim.automatch_por_dia,
            "ver_quien_me_dio_like": lim.ver_quien_me_dio_like,
            "rebobinar": lim.rebobinar,
            "modo_incognito": lim.modo_incognito,
        }

    # ------------------------------------------------------------------
    # Deck
    # ------------------------------------------------------------------
    def vistos_por(self, id_: str) -> set[str]:
        filas = self.con.execute(
            "SELECT a_id FROM interacciones WHERE de_id = ?", (id_,)
        ).fetchall()
        return {f["a_id"] for f in filas}

    def deck(self, perfil: Perfil, limite: int = 20, *, ahora: datetime | None = None) -> dict:
        universo = [p for p in self.todos() if p.id != perfil.id]
        vistos = self.vistos_por(perfil.id)
        elegibles = filtros.candidatos(perfil, universo, vistos=vistos)
        puntuados = scoring.ordenar_deck(perfil, elegibles, ahora=ahora)[:limite]
        por_id = {p.id: p for p in elegibles}
        tarjetas = []
        for fila in puntuados:
            otro = por_id[fila["id"]]
            tarjetas.append(otro.a_dict() | {
                "compatibilidad": fila["compatibilidad"],
                "popularidad": fila["popularidad"],
                "distancia_km": fila["distancia_km"],
                "motivos": fila["motivos"],
                "ola": fila["ola"],
            })
        # Contar la vista acá y no en el cliente: si la cuenta el frontend, un
        # scroll rápido infla las vistas y hunde la popularidad de todos.
        self._sumar_vistas([t["id"] for t in tarjetas])
        salida = {"tarjetas": tarjetas, "cupos": self.cupos(perfil, ahora)}
        if not tarjetas:
            salida["diagnostico"] = filtros.diagnostico(perfil, universo, vistos=vistos)
        return salida

    def _sumar_vistas(self, ids: list[str]) -> None:
        for id_ in ids:
            p = self.perfil(id_)
            if p:
                p.vistas_recibidas += 1
                self.con.execute(
                    "UPDATE perfiles SET datos = ? WHERE id = ?", (self._a_json(p), p.id)
                )
        self.con.commit()

    # ------------------------------------------------------------------
    # Interacciones
    # ------------------------------------------------------------------
    def interactuar(
        self, de: Perfil, a_id: str, tipo: str, *, ahora: datetime | None = None
    ) -> dict:
        """Registra un like / superfan / pass y crea el match si es recíproco.

        Devuelve `{"match": bool, ...}`. El chequeo de cupo va ANTES de tocar
        la base: si se registra la interacción y después falla el cupo, el
        perfil queda quemado (no vuelve a aparecer) sin que el like exista.
        """
        ahora = ahora or datetime.utcnow()
        if tipo not in ("like", "superfan", "pass"):
            raise DatosInvalidos(f"tipo de interacción desconocido: {tipo}")
        destino = self.perfil(a_id)
        if not destino:
            raise DatosInvalidos("ese perfil no existe")
        if a_id == de.id:
            raise DatosInvalidos("no podés interactuar con tu propio perfil")

        ya = self.con.execute(
            "SELECT tipo FROM interacciones WHERE de_id = ? AND a_id = ?", (de.id, a_id)
        ).fetchone()
        if ya:
            raise DatosInvalidos("ya interactuaste con ese perfil")

        cupos = self.cupos(de, ahora)
        if tipo == "like" and cupos["likes_restantes"] == 0:
            raise SinCupo(
                "Se te acabaron los likes de hoy. Con Plus son ilimitados.",
                "likes",
                "plus",
            )
        if tipo == "superfan" and cupos["superfans_restantes"] == 0:
            raise SinCupo(
                "Se te acabaron los superfans de la semana.", "superfans", "plus"
            )

        self.con.execute(
            "INSERT INTO interacciones (id, de_id, a_id, tipo, momento) VALUES (?,?,?,?,?)",
            (uuid.uuid4().hex[:16], de.id, a_id, tipo, ahora.isoformat()),
        )

        if tipo in ("like", "superfan"):
            if tipo == "like":
                destino.likes_recibidos += 1
            else:
                destino.superfans_recibidos += 1
            self.con.execute(
                "UPDATE perfiles SET datos = ? WHERE id = ?",
                (self._a_json(destino), destino.id),
            )
        self.con.commit()

        if tipo == "pass":
            return {"match": False, "cupos": self.cupos(de, ahora)}

        reciproco = self.con.execute(
            "SELECT tipo FROM interacciones WHERE de_id = ? AND a_id = ? AND tipo IN "
            "('like','superfan')",
            (a_id, de.id),
        ).fetchone()
        if not reciproco:
            return {"match": False, "cupos": self.cupos(de, ahora)}

        comp, _ = scoring.compatibilidad(de, destino)
        m = self._crear_match(de.id, a_id, automatico=False, compatibilidad=comp, ahora=ahora)
        return {
            "match": True,
            "match_id": m.id,
            "con": destino.a_dict(),
            "compatibilidad": comp,
            "cupos": self.cupos(de, ahora),
        }

    def rebobinar(self, perfil: Perfil) -> dict:
        """Deshace el último descarte. Es función paga — es el gancho más
        vendido de la categoría y no cuesta nada implementarlo bien."""
        if not planes.limites_de(perfil).rebobinar:
            raise SinCupo("Rebobinar es de Plus en adelante.", "rebobinar", "plus")
        fila = self.con.execute(
            "SELECT id, a_id FROM interacciones WHERE de_id = ? ORDER BY momento DESC LIMIT 1",
            (perfil.id,),
        ).fetchone()
        if not fila:
            return {"deshecho": False}
        self.con.execute("DELETE FROM interacciones WHERE id = ?", (fila["id"],))
        self.con.commit()
        return {"deshecho": True, "perfil_id": fila["a_id"]}

    def quien_me_dio_like(self, perfil: Perfil) -> dict:
        """En gratis devuelve sólo el conteo y las tarjetas borroneadas. Se
        decide en el servidor: mandar los perfiles completos y esconderlos con
        CSS es la fuga clásica de este feature."""
        filas = self.con.execute(
            "SELECT de_id, tipo FROM interacciones WHERE a_id = ? AND tipo IN "
            "('like','superfan') ORDER BY momento DESC",
            (perfil.id,),
        ).fetchall()
        ya_respondidos = self.vistos_por(perfil.id)
        pendientes = [f for f in filas if f["de_id"] not in ya_respondidos]

        # Los filtros duros valen también acá. Antes esta lista sólo miraba
        # `activo`: quien pedía ver únicamente mujeres se encontraba hombres en
        # "te gustaron". Que alguien me haya dado like no lo mete en el filtro
        # que YO puse — es justo al revés.
        #
        # reciproco=False: ya me dio like, así que exigir que yo entre en sus
        # preferencias no aporta nada y escondería gente que sí me quiere ver.
        #
        # El filtrado va ANTES del corte por plan a propósito: si no, el plan
        # gratis mostraría un contador de likes que no coincide con la lista
        # que se ve al pagar.
        visibles = []
        for f in pendientes:
            otro = self.perfil(f["de_id"])
            if not otro:
                continue
            ok, _ = filtros.pasa_filtros(perfil, otro, reciproco=False)
            if ok:
                visibles.append((f, otro))

        if not planes.limites_de(perfil).ver_quien_me_dio_like:
            return {
                "visible": False,
                "cantidad": len(visibles),
                "plan_sugerido": "plus",
                "perfiles": [],
            }
        perfiles = [
            otro.a_dict()
            | {"tipo": f["tipo"], "compatibilidad": scoring.compatibilidad(perfil, otro)[0]}
            for f, otro in visibles
        ]
        return {"visible": True, "cantidad": len(perfiles), "perfiles": perfiles}

    def top_del_dia(self, perfil: Perfil, limite: int = 12) -> list[dict]:
        """Los más likeados HOY que pasan tus filtros y a los que todavía no
        les respondiste — es una lista para dar like, no una vitrina.

        Distinto de "más votados": aquél es histórico y suavizado; éste es el
        pulso del día, crudo, y por eso engancha — cambia todos los días.
        """
        desde = datetime.utcnow().date().isoformat()
        filas = self.con.execute(
            "SELECT a_id, COUNT(*) c FROM interacciones "
            "WHERE tipo IN ('like','superfan') AND momento >= ? "
            "GROUP BY a_id ORDER BY c DESC",
            (desde,),
        ).fetchall()
        vistos = self.vistos_por(perfil.id)
        salida = []
        for f in filas:
            if f["a_id"] == perfil.id or f["a_id"] in vistos:
                continue
            otro = self.perfil(f["a_id"])
            if not otro or not otro.activo or not otro.completo:
                continue
            if not filtros.pasa_filtros(perfil, otro, reciproco=False)[0]:
                continue
            comp, _ = scoring.compatibilidad(perfil, otro)
            salida.append(otro.a_dict() | {"likes_hoy": f["c"], "compatibilidad": comp})
            if len(salida) >= limite:
                break
        return salida

    # ------------------------------------------------------------------
    # Matches y chat
    # ------------------------------------------------------------------
    def _crear_match(
        self,
        a: str,
        b: str,
        *,
        automatico: bool,
        compatibilidad: float,
        ahora: datetime | None = None,
        ciego: bool = False,
    ) -> Match:
        # Par ordenado: sin esto el mismo match entra dos veces (A,B) y (B,A).
        a, b = sorted([a, b])
        existe = self.con.execute(
            "SELECT * FROM matches WHERE a_id = ? AND b_id = ?", (a, b)
        ).fetchone()
        if existe:
            return Match(
                id=existe["id"],
                a_id=existe["a_id"],
                b_id=existe["b_id"],
                momento=_dt(existe["momento"]),
                automatico=bool(existe["automatico"]),
                compatibilidad=existe["compatibilidad"],
            )
        m = Match(
            id=uuid.uuid4().hex[:16],
            a_id=a,
            b_id=b,
            momento=ahora or datetime.utcnow(),
            automatico=automatico,
            compatibilidad=compatibilidad,
        )
        self.con.execute(
            "INSERT INTO matches (id, a_id, b_id, momento, automatico, compatibilidad, ciego) "
            "VALUES (?,?,?,?,?,?,?)",
            (m.id, m.a_id, m.b_id, m.momento.isoformat(), int(m.automatico), m.compatibilidad,
             int(ciego)),
        )
        self.con.commit()
        return m

    def matches_de(self, id_: str) -> list[dict]:
        filas = self.con.execute(
            "SELECT * FROM matches WHERE a_id = ? OR b_id = ? ORDER BY momento DESC",
            (id_, id_),
        ).fetchall()
        salida = []
        for f in filas:
            otro_id = f["b_id"] if f["a_id"] == id_ else f["a_id"]
            otro = self.perfil(otro_id)
            if not otro or not otro.activo:
                continue
            ultimo = self.con.execute(
                "SELECT texto, momento, de_id FROM mensajes WHERE match_id = ? "
                "ORDER BY momento DESC LIMIT 1",
                (f["id"],),
            ).fetchone()
            sin_leer = self.con.execute(
                "SELECT COUNT(*) c FROM mensajes WHERE match_id = ? AND de_id != ? AND leido = 0",
                (f["id"], id_),
            ).fetchone()["c"]
            # Cita a ciegas: hasta que los dos escribieron lo suficiente, las
            # fotos NO viajan. Regla 8 del producto: lo que decide el servidor
            # no lo esconde el cliente — mandar las fotos con un blur encima
            # sería la fuga clásica, así que acá directamente no salen del
            # servidor. El conteo es derivado de los mensajes: no hay un
            # estado "revelado" que pueda quedar desincronizado.
            es_ciego = bool(f["ciego"]) if "ciego" in f.keys() else False
            ciego = None
            datos_otro = otro.a_dict()
            if es_ciego:
                from . import aciegas

                ciego = aciegas.estado(self, f["id"], id_)
                if not ciego["revelado"]:
                    datos_otro = aciegas.silueta(otro)

            salida.append(
                {
                    "id": f["id"],
                    "momento": f["momento"],
                    "automatico": bool(f["automatico"]),
                    "compatibilidad": f["compatibilidad"],
                    "con": datos_otro,
                    "ciego": ciego,
                    "ultimo_mensaje": (
                        {"texto": ultimo["texto"], "momento": ultimo["momento"],
                         "mio": ultimo["de_id"] == id_}
                        if ultimo
                        else None
                    ),
                    "sin_leer": sin_leer,
                }
            )
        return salida

    def _match_de(self, match_id: str, id_usuario: str) -> sqlite3.Row:
        fila = self.con.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
        if not fila or id_usuario not in (fila["a_id"], fila["b_id"]):
            raise DatosInvalidos("ese match no existe o no es tuyo")
        return fila

    def enviar_mensaje(self, match_id: str, de: Perfil, texto: str) -> Mensaje:
        self._match_de(match_id, de.id)
        texto = (texto or "").strip()
        if not texto:
            raise DatosInvalidos("el mensaje está vacío")
        if len(texto) > 2000:
            raise DatosInvalidos("el mensaje es demasiado largo (máximo 2000 caracteres)")
        m = Mensaje(id=uuid.uuid4().hex[:16], match_id=match_id, de_id=de.id, texto=texto)
        self.con.execute(
            "INSERT INTO mensajes (id, match_id, de_id, texto, momento, leido) VALUES (?,?,?,?,?,0)",
            (m.id, m.match_id, m.de_id, m.texto, m.momento.isoformat()),
        )
        self.con.commit()
        return m

    def conversacion(self, match_id: str, de: Perfil) -> list[dict]:
        self._match_de(match_id, de.id)
        filas = self.con.execute(
            "SELECT * FROM mensajes WHERE match_id = ? ORDER BY momento", (match_id,)
        ).fetchall()
        self.con.execute(
            "UPDATE mensajes SET leido = 1 WHERE match_id = ? AND de_id != ?",
            (match_id, de.id),
        )
        self.con.commit()
        return [
            {
                "id": f["id"],
                "de_id": f["de_id"],
                "mio": f["de_id"] == de.id,
                "texto": f["texto"],
                "momento": f["momento"],
            }
            for f in filas
        ]

    def deshacer_match(self, match_id: str, de: Perfil) -> None:
        self._match_de(match_id, de.id)
        self.con.execute("DELETE FROM mensajes WHERE match_id = ?", (match_id,))
        self.con.execute("DELETE FROM matches WHERE id = ?", (match_id,))
        self.con.commit()

    # ------------------------------------------------------------------
    # Reportes y bloqueos
    # ------------------------------------------------------------------
    def reportar(self, de: Perfil, a_id: str, motivo: str, detalle: str = "") -> None:
        """Reportar también descarta: nadie quiere volver a cruzarse con quien
        acaba de reportar. El `INSERT OR IGNORE` cubre el caso de haber pasado
        antes por ese perfil."""
        self.con.execute(
            "INSERT INTO reportes (id, de_id, a_id, motivo, detalle, momento) VALUES (?,?,?,?,?,?)",
            (uuid.uuid4().hex[:16], de.id, a_id, motivo, detalle, datetime.utcnow().isoformat()),
        )
        self.con.execute(
            "INSERT OR IGNORE INTO interacciones (id, de_id, a_id, tipo, momento) "
            "VALUES (?,?,?,'pass',?)",
            (uuid.uuid4().hex[:16], de.id, a_id, datetime.utcnow().isoformat()),
        )
        self.con.commit()

    # ------------------------------------------------------------------
    # Ubicación, pings y cruces
    # ------------------------------------------------------------------
    def guardar_ubicacion(self, usuario_id: str, lat: float, lon: float, momento: datetime) -> None:
        """Pisa la anterior. Una fila por persona: no hay historial de
        recorridos, y no tenerlo es la única forma de no filtrarlo."""
        self.con.execute(
            "INSERT INTO ubicaciones (usuario_id, lat, lon, momento) VALUES (?,?,?,?) "
            "ON CONFLICT(usuario_id) DO UPDATE SET lat=excluded.lat, lon=excluded.lon, "
            "momento=excluded.momento",
            (usuario_id, lat, lon, momento.isoformat()),
        )
        self.con.commit()

    def ubicacion_de(self, usuario_id: str) -> dict | None:
        fila = self.con.execute(
            "SELECT lat, lon, momento FROM ubicaciones WHERE usuario_id = ?", (usuario_id,)
        ).fetchone()
        return dict(fila) if fila else None

    def guardar_ping(self, usuario_id: str, celda: str, momento: datetime) -> None:
        self.con.execute(
            "INSERT INTO pings (usuario_id, celda, momento) VALUES (?,?,?)",
            (usuario_id, celda, momento.isoformat()),
        )
        self.con.commit()

    def limpiar_pings(self, antes_de: datetime) -> int:
        cur = self.con.execute("DELETE FROM pings WHERE momento < ?", (antes_de.isoformat(),))
        self.con.commit()
        return cur.rowcount

    def detectar_cruces(
        self,
        usuario_id: str,
        celda: str,
        momento: datetime,
        ventana: timedelta,
        max_por_dia: int,
    ) -> list[dict]:
        """Quién más estuvo en esta celda dentro de la ventana. Suma el cruce
        y devuelve los nuevos."""
        filas = self.con.execute(
            "SELECT DISTINCT usuario_id FROM pings WHERE celda = ? AND usuario_id != ? "
            "AND momento >= ?",
            (celda, usuario_id, (momento - ventana).isoformat()),
        ).fetchall()

        inicio_dia = datetime(momento.year, momento.month, momento.day).isoformat()
        nuevos = []
        for fila in filas:
            otro = fila["usuario_id"]
            a, b = sorted([usuario_id, otro])
            existente = self.con.execute(
                "SELECT veces, ultima FROM cruces WHERE a_id = ? AND b_id = ?", (a, b)
            ).fetchone()

            if existente:
                # Un cruce por ventana, y con tope diario: quedarse una hora en
                # el mismo café no puede valer veinte cruces.
                if existente["ultima"] >= (momento - ventana).isoformat():
                    continue
                del_dia = self.con.execute(
                    "SELECT veces FROM cruces WHERE a_id = ? AND b_id = ? AND ultima >= ?",
                    (a, b, inicio_dia),
                ).fetchone()
                if del_dia and existente["veces"] >= max_por_dia and existente["ultima"] >= inicio_dia:
                    continue
                self.con.execute(
                    "UPDATE cruces SET veces = veces + 1, ultima = ?, cerca_de = ? "
                    "WHERE a_id = ? AND b_id = ?",
                    (momento.isoformat(), celda, a, b),
                )
            else:
                self.con.execute(
                    "INSERT INTO cruces (a_id, b_id, veces, primera, ultima, cerca_de) "
                    "VALUES (?,?,1,?,?,?)",
                    (a, b, momento.isoformat(), momento.isoformat(), celda),
                )
            nuevos.append({"otro_id": otro, "celda": celda})
        self.con.commit()
        return nuevos

    def sumar_cruce(
        self, a: str, b: str, veces: int, primera: datetime, ultima: datetime, celda: str = ""
    ) -> None:
        """Alta directa de un cruce. La usa el seed de la demo; el flujo real
        pasa por `detectar_cruces`."""
        a, b = sorted([a, b])
        self.con.execute(
            "INSERT INTO cruces (a_id, b_id, veces, primera, ultima, cerca_de) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(a_id, b_id) DO UPDATE SET veces = veces + excluded.veces, "
            "ultima = max(ultima, excluded.ultima)",
            (a, b, veces, primera.isoformat(), ultima.isoformat(), celda),
        )
        self.con.commit()

    def cruces_de(self, usuario_id: str, limite: int = 50) -> list[dict]:
        filas = self.con.execute(
            "SELECT CASE WHEN a_id = ? THEN b_id ELSE a_id END AS otro_id, "
            "veces, primera, ultima, cerca_de FROM cruces "
            "WHERE a_id = ? OR b_id = ? ORDER BY veces DESC, ultima DESC LIMIT ?",
            (usuario_id, usuario_id, usuario_id, limite),
        ).fetchall()
        return [dict(f) for f in filas]

    def total_cruces(self, usuario_id: str) -> tuple[int, int]:
        fila = self.con.execute(
            "SELECT COALESCE(SUM(veces), 0) total, COUNT(*) personas FROM cruces "
            "WHERE a_id = ? OR b_id = ?",
            (usuario_id, usuario_id),
        ).fetchone()
        return fila["total"], fila["personas"]

    # ------------------------------------------------------------------
    # Pagos
    # ------------------------------------------------------------------
    def registrar_pago(
        self,
        usuario_id: str,
        plan: str,
        periodo: str,
        monto: float,
        moneda: str,
        estado: str,
        pasarela: str,
        referencia: str,
    ) -> str:
        id_ = uuid.uuid4().hex[:16]
        self.con.execute(
            "INSERT INTO pagos (id, usuario_id, plan, periodo, monto, moneda, estado, "
            "pasarela, referencia, momento) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                id_, usuario_id, plan, periodo, monto, moneda, estado, pasarela,
                referencia, datetime.utcnow().isoformat(),
            ),
        )
        self.con.commit()
        return id_

    def pagos_de(self, usuario_id: str) -> list[dict]:
        filas = self.con.execute(
            "SELECT * FROM pagos WHERE usuario_id = ? ORDER BY momento DESC", (usuario_id,)
        ).fetchall()
        return [dict(f) for f in filas]

    def pago_por_referencia(self, referencia: str) -> dict | None:
        """La usa el webhook: ahí no hay una sesión de usuario, sólo lo que
        avisó la pasarela, así que hace falta encontrar de quién es el pago."""
        fila = self.con.execute(
            "SELECT * FROM pagos WHERE referencia = ?", (referencia,)
        ).fetchone()
        return dict(fila) if fila else None
