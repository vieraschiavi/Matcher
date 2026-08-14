"""Modelos del dominio. Español, igual que MV Kobra AI y MV Cliente IA.

Todo lo que se persiste pasa por acá: los `dict` sueltos entre backend y motor
fueron el origen de la mitad de los bugs de perfiles incompletos, así que el
almacén serializa y deserializa exclusivamente estas dataclases.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

# ---------------------------------------------------------------------------
# Vocabularios cerrados. Son str y no Enum a propósito: viajan tal cual a JSON,
# a SQLite y al frontend sin serializadores intermedios.
# ---------------------------------------------------------------------------
GENEROS = ("mujer", "hombre", "trans", "otro")
ORIENTACIONES = ("mujeres", "hombres", "todos")   # heredado: ver Preferencias.generos
POLITICAS = ("izquierda", "derecha", "neutro")

# Qué busca cada persona. Es multi-selección: casi nadie quiere una sola cosa,
# y obligar a elegir una es lo que hace que el dato no sirva.
INTENCIONES = (
    "amistad",
    "tomar_algo",
    "algo_casual",
    "sexo",
    "relacion_formal",
    "salir_a_bailar",
    "disponible_hoy",
)

# "Disponible hoy" no es una intención permanente: se prende y vence. Si no
# venciera, a la semana la mitad del padrón figuraría disponible y el filtro
# dejaría de significar algo.
HORAS_DISPONIBLE = 24
PLANES = ("gratis", "plus", "gold")
TIPOS_INTERACCION = ("like", "superfan", "pass")

# Reglas duras de medios que pidió el producto.
MAX_FOTOS = 10
MAX_VIDEOS = 2
MAX_SEGUNDOS_VIDEO = 30

EDAD_MINIMA = 18
EDAD_MAXIMA = 99
ALTURA_MINIMA_CM = 130
ALTURA_MAXIMA_CM = 230

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")


class DatosInvalidos(ValueError):
    """Error de validación del dominio. El backend lo traduce a HTTP 400."""


@dataclass
class Media:
    """Una foto o un video corto del perfil.

    `url` puede ser una ruta servida por el backend o un data-URI en la demo.
    `orden` decide qué se muestra primero en la tarjeta; la foto 0 es la
    portada, y es la única obligatoria para poder aparecer en el deck.
    """

    id: str
    tipo: str  # "foto" | "video"
    url: str
    orden: int = 0
    segundos: float | None = None  # sólo videos
    aprobada: bool = True

    def a_dict(self) -> dict:
        return {
            "id": self.id,
            "tipo": self.tipo,
            "url": self.url,
            "orden": self.orden,
            "segundos": self.segundos,
            "aprobada": self.aprobada,
        }

    @staticmethod
    def desde_dict(d: dict) -> Media:
        return Media(
            id=str(d["id"]),
            tipo=d.get("tipo", "foto"),
            url=d["url"],
            orden=int(d.get("orden", 0)),
            segundos=d.get("segundos"),
            aprobada=bool(d.get("aprobada", True)),
        )


@dataclass
class Preferencias:
    """Lo que el usuario busca. Todo opcional salvo el rango de edad: un deck
    sin límite de edad es la queja número uno en las reseñas de la competencia.

    `equipo` y `politica` son listas y no un valor único porque el caso real es
    "me da igual izquierda o neutro, derecha no" — con un valor único eso
    obliga a dos búsquedas.
    """

    # TODOS los filtros de lista siguen la misma regla: **lista vacía = Todos**.
    # Es la que hace que la UI pueda ser una sola (chips multi-selección con un
    # botón "Todos" que limpia) para género, política, equipo e intención.
    generos: list[str] = field(default_factory=list)     # vacío = todos
    edad_min: int = 18
    edad_max: int = 99
    altura_min_cm: int | None = None
    altura_max_cm: int | None = None
    politicas: list[str] = field(default_factory=list)   # vacío = cualquiera
    equipos: list[str] = field(default_factory=list)     # vacío = cualquiera
    intenciones: list[str] = field(default_factory=list)  # vacío = cualquiera
    solo_mi_pais: bool = False
    distancia_max_km: int | None = None
    solo_verificados: bool = False
    intereses: list[str] = field(default_factory=list)

    @property
    def busca(self) -> str:
        """Compatibilidad con el valor único viejo. Se sigue exponiendo porque
        hay perfiles guardados con `busca` y clientes viejos que lo mandan."""
        if set(self.generos) == {"mujer"}:
            return "mujeres"
        if set(self.generos) == {"hombre"}:
            return "hombres"
        return "todos"

    def validar(self) -> None:
        for g in self.generos:
            if g not in GENEROS:
                raise DatosInvalidos(f"género desconocido: {g}")
        for i in self.intenciones:
            if i not in INTENCIONES:
                raise DatosInvalidos(f"intención desconocida: {i}")
        if not (EDAD_MINIMA <= self.edad_min <= self.edad_max <= EDAD_MAXIMA):
            raise DatosInvalidos("rango de edad inválido (18–99 y mín ≤ máx)")
        alturas = [a for a in (self.altura_min_cm, self.altura_max_cm) if a is not None]
        for a in alturas:
            if not (ALTURA_MINIMA_CM <= a <= ALTURA_MAXIMA_CM):
                raise DatosInvalidos("altura fuera de rango (130–230 cm)")
        if len(alturas) == 2 and self.altura_min_cm > self.altura_max_cm:  # type: ignore[operator]
            raise DatosInvalidos("altura mínima mayor que la máxima")
        for p in self.politicas:
            if p not in POLITICAS:
                raise DatosInvalidos(f"postura política desconocida: {p}")
        if self.distancia_max_km is not None and self.distancia_max_km <= 0:
            raise DatosInvalidos("la distancia máxima tiene que ser positiva")

    def a_dict(self) -> dict:
        return {
            "generos": list(self.generos),
            "busca": self.busca,          # derivado, para clientes viejos
            "edad_min": self.edad_min,
            "edad_max": self.edad_max,
            "altura_min_cm": self.altura_min_cm,
            "altura_max_cm": self.altura_max_cm,
            "politicas": list(self.politicas),
            "equipos": list(self.equipos),
            "intenciones": list(self.intenciones),
            "solo_mi_pais": self.solo_mi_pais,
            "distancia_max_km": self.distancia_max_km,
            "solo_verificados": self.solo_verificados,
            "intereses": list(self.intereses),
        }

    @staticmethod
    def desde_dict(d: dict | None) -> Preferencias:
        d = d or {}
        # Migración en lectura: los perfiles viejos guardaron `busca` como
        # valor único. Se traduce acá y no en una migración de tabla porque el
        # perfil vive como JSON — así un perfil viejo sigue funcionando sin
        # tocar la base.
        generos = list(d.get("generos") or [])
        if not generos and d.get("busca") in ("mujeres", "hombres"):
            generos = ["mujer"] if d["busca"] == "mujeres" else ["hombre"]
        return Preferencias(
            generos=generos,
            edad_min=int(d.get("edad_min", 18)),
            edad_max=int(d.get("edad_max", 99)),
            altura_min_cm=d.get("altura_min_cm"),
            altura_max_cm=d.get("altura_max_cm"),
            politicas=list(d.get("politicas") or []),
            equipos=list(d.get("equipos") or []),
            intenciones=list(d.get("intenciones") or []),
            solo_mi_pais=bool(d.get("solo_mi_pais", False)),
            distancia_max_km=d.get("distancia_max_km"),
            solo_verificados=bool(d.get("solo_verificados", False)),
            intereses=list(d.get("intereses") or []),
        )


@dataclass
class Perfil:
    """Un usuario de la app.

    `sintetico` viaja en el registro y se muestra en la interfaz: los perfiles
    de la demo son personas inventadas y eso se dice, no se disimula. Misma
    regla que en MV Cliente IA.
    """

    id: str
    email: str
    nombre: str
    nacimiento: date
    genero: str
    altura_cm: int
    pais: str
    ciudad: str                       # id del catálogo geo.CIUDADES
    politica: str = "neutro"
    equipo: str = ""                  # "" = no le interesa el fútbol
    bio: str = ""
    intereses: list[str] = field(default_factory=list)
    intenciones: list[str] = field(default_factory=list)
    # Cuándo vence el "disponible hoy". Se guarda aparte de la lista porque la
    # intención es permanente y la disponibilidad no.
    disponible_hasta: datetime | None = None
    fotos: list[Media] = field(default_factory=list)
    videos: list[Media] = field(default_factory=list)
    preferencias: Preferencias = field(default_factory=Preferencias)
    plan: str = "gratis"
    plan_vence: datetime | None = None
    verificado: bool = False
    activo: bool = True
    sintetico: bool = False
    creado: datetime = field(default_factory=datetime.utcnow)
    ultima_actividad: datetime = field(default_factory=datetime.utcnow)
    # Señales que alimentan el ranking "más votados". Se recalculan solos.
    likes_recibidos: int = 0
    superfans_recibidos: int = 0
    vistas_recibidas: int = 0

    # -- derivados ---------------------------------------------------------
    def edad(self, hoy: date | None = None) -> int:
        hoy = hoy or date.today()
        años = hoy.year - self.nacimiento.year
        if (hoy.month, hoy.day) < (self.nacimiento.month, self.nacimiento.day):
            años -= 1
        return años

    @property
    def es_premium(self) -> bool:
        if self.plan == "gratis":
            return False
        if self.plan_vence and self.plan_vence < datetime.utcnow():
            return False
        return True

    @property
    def disponible_hoy(self) -> bool:
        return bool(self.disponible_hasta and self.disponible_hasta > datetime.utcnow())

    @property
    def intenciones_vigentes(self) -> list[str]:
        """Las intenciones tal como las ve el resto.

        `disponible_hoy` se agrega o se saca según el reloj, no según lo que
        haya quedado guardado en la lista: un perfil que dice "disponible hoy"
        desde hace cinco días le está mintiendo a todo el mundo.
        """
        vigentes = [i for i in self.intenciones if i != "disponible_hoy"]
        if self.disponible_hoy:
            vigentes.append("disponible_hoy")
        return vigentes

    def marcar_disponible(self, horas: int = HORAS_DISPONIBLE) -> None:
        self.disponible_hasta = datetime.utcnow() + timedelta(hours=horas)
        if "disponible_hoy" not in self.intenciones:
            self.intenciones.append("disponible_hoy")

    @property
    def portada(self) -> str | None:
        fotos = sorted((f for f in self.fotos if f.aprobada), key=lambda f: f.orden)
        return fotos[0].url if fotos else None

    @property
    def completo(self) -> bool:
        """Un perfil sin foto no entra al deck. Es la regla que más sube la
        calidad percibida en las reseñas: nadie quiere swipear siluetas."""
        return bool(self.portada) and bool(self.nombre.strip())

    # -- validación --------------------------------------------------------
    def validar(self) -> None:
        if not _EMAIL.match(self.email or ""):
            raise DatosInvalidos(f"email inválido: {self.email!r}")
        if not self.nombre.strip():
            raise DatosInvalidos("el nombre no puede estar vacío")
        if self.genero not in GENEROS:
            raise DatosInvalidos(f"género desconocido: {self.genero}")
        if self.politica not in POLITICAS:
            raise DatosInvalidos(f"postura política desconocida: {self.politica}")
        for i in self.intenciones:
            if i not in INTENCIONES:
                raise DatosInvalidos(f"intención desconocida: {i}")
        if not (ALTURA_MINIMA_CM <= self.altura_cm <= ALTURA_MAXIMA_CM):
            raise DatosInvalidos("altura fuera de rango (130–230 cm)")
        if self.edad() < EDAD_MINIMA:
            raise DatosInvalidos("la app es sólo para mayores de 18 años")
        if self.plan not in PLANES:
            raise DatosInvalidos(f"plan desconocido: {self.plan}")
        if len(self.fotos) > MAX_FOTOS:
            raise DatosInvalidos(f"máximo {MAX_FOTOS} fotos por perfil")
        if len(self.videos) > MAX_VIDEOS:
            raise DatosInvalidos(f"máximo {MAX_VIDEOS} videos por perfil")
        for v in self.videos:
            if v.segundos is not None and v.segundos > MAX_SEGUNDOS_VIDEO:
                raise DatosInvalidos(f"los videos no pueden pasar de {MAX_SEGUNDOS_VIDEO} s")
        self.preferencias.validar()

    # -- serialización -----------------------------------------------------
    def a_dict(self, privado: bool = False) -> dict:
        """`privado=True` incluye email y preferencias: sólo para el dueño del
        perfil. La vista pública (la tarjeta del deck) nunca lleva el email —
        filtrarlo en el frontend es una fuga esperando a pasar."""
        base = {
            "id": self.id,
            "nombre": self.nombre,
            "edad": self.edad(),
            "genero": self.genero,
            "altura_cm": self.altura_cm,
            "pais": self.pais,
            "ciudad": self.ciudad,
            "politica": self.politica,
            "equipo": self.equipo,
            "bio": self.bio,
            "intereses": list(self.intereses),
            "intenciones": self.intenciones_vigentes,
            "disponible_hoy": self.disponible_hoy,
            "fotos": [f.a_dict() for f in self.fotos],
            "videos": [v.a_dict() for v in self.videos],
            "plan": self.plan,
            "es_premium": self.es_premium,
            "verificado": self.verificado,
            "sintetico": self.sintetico,
            "likes_recibidos": self.likes_recibidos,
            "superfans_recibidos": self.superfans_recibidos,
        }
        if privado:
            base |= {
                "email": self.email,
                "nacimiento": self.nacimiento.isoformat(),
                "preferencias": self.preferencias.a_dict(),
                "plan_vence": self.plan_vence.isoformat() if self.plan_vence else None,
                "activo": self.activo,
                "vistas_recibidas": self.vistas_recibidas,
            }
        return base


@dataclass
class Interaccion:
    """Un like / superfan / pass. Se guarda siempre, también el pass: sin eso
    el deck repite perfiles ya descartados y la app se siente rota."""

    id: str
    de_id: str
    a_id: str
    tipo: str
    momento: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Match:
    """Dos personas que se gustaron. `automatico=True` marca los que propuso el
    algoritmo sin que ninguno de los dos deslizara — se muestran distinto para
    no mentirle al usuario sobre por qué apareció ese chat."""

    id: str
    a_id: str
    b_id: str
    momento: datetime = field(default_factory=datetime.utcnow)
    automatico: bool = False
    compatibilidad: float = 0.0

    def otro(self, id_usuario: str) -> str:
        return self.b_id if self.a_id == id_usuario else self.a_id


@dataclass
class Mensaje:
    id: str
    match_id: str
    de_id: str
    texto: str
    momento: datetime = field(default_factory=datetime.utcnow)
    leido: bool = False

    def a_dict(self) -> dict:
        return {
            "id": self.id,
            "match_id": self.match_id,
            "de_id": self.de_id,
            "texto": self.texto,
            "momento": self.momento.isoformat(),
            "leido": self.leido,
        }
