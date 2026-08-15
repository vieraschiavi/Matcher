"""Planes, límites y precios.

La estrategia comercial del producto es una sola: **misma funcionalidad que la
competencia, a menos de la mitad de precio, y sin esconder los filtros detrás
del muro de pago.** Lo segundo es lo importante — la queja más repetida en las
reseñas de las apps grandes no es el precio, es pagar y sentir que el algoritmo
sigue sin respetar lo que pediste. Acá los filtros (edad, altura, política,
equipo, distancia) funcionan **completos en el plan gratis**; lo que se paga es
volumen (likes, superfans), visibilidad y ver quién te dio like.

Los precios de la competencia son REFERENCIA APROXIMADA de precios de lista
públicos y varían por país, edad y promociones. Están acá para armar la tabla
comparativa de la landing: **verificalos antes de publicar cualquier campaña**,
no los tomes como dato duro.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

MONEDA = "USD"


@dataclass(frozen=True)
class Limites:
    """`None` = ilimitado."""

    likes_por_dia: int | None
    superfans_por_semana: int
    ver_quien_me_dio_like: bool
    rebobinar: bool
    filtros_avanzados: int | None      # cuántos de altura/política/equipo puede usar
    automatch_por_dia: int
    boost_por_mes: int
    # Turnos diarios de Crush Time (adivinar quién te dio like). El juego
    # existe en el plan gratis —probarlo es lo que lo hace deseable— y el
    # pago compra volumen, igual que con los likes.
    crushtime_por_dia: int
    modo_incognito: bool
    sin_publicidad: bool
    fotos: int
    videos: int


@dataclass(frozen=True)
class Plan:
    codigo: str
    nombre: str
    precio_mes: float
    precio_anual: float           # total del año, ya con el descuento
    limites: Limites
    destacados: list[str] = field(default_factory=list)

    @property
    def precio_mes_en_anual(self) -> float:
        return round(self.precio_anual / 12, 2)

    def a_dict(self) -> dict:
        return {
            "codigo": self.codigo,
            "nombre": self.nombre,
            "moneda": MONEDA,
            "precio_mes": self.precio_mes,
            "precio_anual": self.precio_anual,
            "precio_mes_en_anual": self.precio_mes_en_anual,
            "destacados": list(self.destacados),
            "limites": {
                "likes_por_dia": self.limites.likes_por_dia,
                "superfans_por_semana": self.limites.superfans_por_semana,
                "ver_quien_me_dio_like": self.limites.ver_quien_me_dio_like,
                "rebobinar": self.limites.rebobinar,
                "filtros_avanzados": self.limites.filtros_avanzados,
                "automatch_por_dia": self.limites.automatch_por_dia,
                "boost_por_mes": self.limites.boost_por_mes,
                "crushtime_por_dia": self.limites.crushtime_por_dia,
                "modo_incognito": self.limites.modo_incognito,
                "sin_publicidad": self.limites.sin_publicidad,
                "fotos": self.limites.fotos,
                "videos": self.limites.videos,
            },
        }


PLANES: dict[str, Plan] = {
    "gratis": Plan(
        codigo="gratis",
        nombre="Matcher Free",
        precio_mes=0.0,
        precio_anual=0.0,
        limites=Limites(
            likes_por_dia=40,          # la competencia da ~25–50; acá 40 y sin trampa
            superfans_por_semana=1,
            ver_quien_me_dio_like=False,
            rebobinar=False,
            filtros_avanzados=None,    # <- TODOS los filtros, gratis. Es el diferencial.
            automatch_por_dia=1,
            boost_por_mes=0,
            crushtime_por_dia=1,
            modo_incognito=False,
            sin_publicidad=False,
            fotos=10,
            videos=2,
        ),
        destacados=[
            "Todos los filtros: edad, altura, política, equipo y distancia",
            "40 likes por día",
            "1 superfan por semana",
            "1 match automático por día",
            "Hasta 10 fotos y 2 videos",
        ],
    ),
    "plus": Plan(
        codigo="plus",
        nombre="Matcher Plus",
        precio_mes=3.99,
        precio_anual=29.90,            # 2.49/mes
        limites=Limites(
            likes_por_dia=None,
            superfans_por_semana=5,
            ver_quien_me_dio_like=True,
            rebobinar=True,
            filtros_avanzados=None,
            automatch_por_dia=5,
            boost_por_mes=1,
            crushtime_por_dia=5,
            modo_incognito=False,
            sin_publicidad=True,
            fotos=10,
            videos=2,
        ),
        destacados=[
            "Likes ilimitados",
            "Ves quién te dio like",
            "5 superfans por semana",
            "Rebobinar el último descarte",
            "5 matches automáticos por día",
            "5 turnos de Crush Time por día",
            "1 boost por mes · sin publicidad",
        ],
    ),
    "gold": Plan(
        codigo="gold",
        nombre="Matcher Gold",
        precio_mes=7.99,
        precio_anual=59.90,            # 4.99/mes
        limites=Limites(
            likes_por_dia=None,
            superfans_por_semana=15,
            ver_quien_me_dio_like=True,
            rebobinar=True,
            filtros_avanzados=None,
            automatch_por_dia=15,
            boost_por_mes=4,
            crushtime_por_dia=5,
            modo_incognito=True,
            sin_publicidad=True,
            fotos=10,
            videos=2,
        ),
        destacados=[
            "Todo lo de Plus",
            "15 superfans por semana",
            "15 matches automáticos por día",
            "4 boosts por mes",
            "Modo incógnito",
            "Prioridad en el deck",
        ],
    ),
}

# Referencia comercial para la tabla comparativa. VERIFICAR antes de publicar:
# son precios de lista públicos aproximados en USD y cambian por país y por
# promoción. Se guardan acá y no en el frontend para que haya un solo lugar
# donde corregirlos.
REFERENCIA_COMPETENCIA = [
    {"app": "Tinder Plus", "precio_mes_aprox": 15.99, "verificado": False},
    {"app": "Tinder Gold", "precio_mes_aprox": 29.99, "verificado": False},
    {"app": "Bumble Premium", "precio_mes_aprox": 29.99, "verificado": False},
    {"app": "Happn Premium", "precio_mes_aprox": 24.99, "verificado": False},
]


def plan_de(codigo: str) -> Plan:
    return PLANES.get(codigo, PLANES["gratis"])


def limites_de(perfil) -> Limites:
    """Los límites efectivos del perfil. Si el plan pago venció, vuelve a los
    de gratis — `Perfil.es_premium` ya contempla el vencimiento."""
    codigo = perfil.plan if getattr(perfil, "es_premium", False) else "gratis"
    return plan_de(codigo).limites


def vencimiento(periodo: str, desde: datetime | None = None) -> datetime:
    desde = desde or datetime.utcnow()
    return desde + (timedelta(days=365) if periodo == "anual" else timedelta(days=30))


def catalogo() -> dict:
    return {
        "moneda": MONEDA,
        "planes": [PLANES[c].a_dict() for c in ("gratis", "plus", "gold")],
        "referencia_competencia": REFERENCIA_COMPETENCIA,
        "aviso_referencia": (
            "Los precios de otras apps son referencia aproximada de precios de lista "
            "públicos y varían por país y promoción. Verificalos antes de usarlos en "
            "una campaña."
        ),
    }
