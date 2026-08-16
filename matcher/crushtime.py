"""Crush Time: adivinar quién te dio like, entre cuatro caras.

El juego de Happn, con las reglas de Matcher:

- **Siempre hay al menos una persona que te dio like en la ronda** — es la
  construcción del juego, no una promesa: la ronda se arma alrededor de un
  like pendiente real. Si hoy nadie nuevo te dio like, el juego lo dice; no
  se inventa un like falso (misma regla que el login: no se simula nada que
  en producción sería mentira).
- **Acertar ES el like de vuelta**: la otra persona ya te había dicho que sí,
  así que el acierto crea el match en el acto. Errar consume el turno y no
  revela quién era — si lo revelara, el segundo turno sería trámite.
- **Cupos por plan**: 1 ronda diaria gratis, 5 en los planes pagos. El pago
  compra volumen, nunca el derecho a jugar (regla 4, la misma que filtros).
- **El payload no dice quién es** (regla 8): las cuatro caras viajan en orden
  barajado con semilla del id de la ronda, sin ninguna marca. Hay un test que
  falla si el objetivo se distingue del resto.

Todo lo que muestra la ronda pasó los filtros duros del usuario: el premio de
adivinar no puede ser alguien que pediste no ver.
"""

from __future__ import annotations

import json
import random
import uuid
from datetime import datetime

from . import planes
from .filtros import pasa_filtros
from .modelos import DatosInvalidos, Perfil

OPCIONES = 4


class SinTurnos(DatosInvalidos):
    """Se acabaron las rondas de hoy. La API la traduce a 402 con el plan
    sugerido, igual que los likes."""

    def __init__(self, maximo: int):
        super().__init__(
            f"jugaste tus {maximo} ronda{'s' if maximo != 1 else ''} de hoy; "
            "mañana hay más, o con Plus tenés 5 por día"
        )
        self.maximo = maximo


def _hoy(ahora: datetime | None = None) -> str:
    return (ahora or datetime.utcnow()).date().isoformat()


def rondas_de_hoy(almacen, usuario_id: str, ahora: datetime | None = None) -> int:
    fila = almacen.con.execute(
        "SELECT COUNT(*) c FROM crushtime WHERE usuario_id = ? AND fecha = ?",
        (usuario_id, _hoy(ahora)),
    ).fetchone()
    return fila["c"]


def estado(almacen, perfil: Perfil, ahora: datetime | None = None) -> dict:
    maximo = planes.limites_de(perfil).crushtime_por_dia
    usadas = rondas_de_hoy(almacen, perfil.id, ahora)
    pendiente = almacen.con.execute(
        "SELECT id FROM crushtime WHERE usuario_id = ? AND resuelto = 0 "
        "ORDER BY momento DESC LIMIT 1",
        (perfil.id,),
    ).fetchone()
    return {
        "turnos_max": maximo,
        "turnos_usados": usadas,
        "turnos_restantes": max(0, maximo - usadas),
        "ronda_pendiente": pendiente["id"] if pendiente else None,
    }


def _pendientes_que_me_gustaron(almacen, perfil: Perfil) -> list[Perfil]:
    """Likes recibidos sin responder, con los filtros duros aplicados."""
    filas = almacen.con.execute(
        "SELECT DISTINCT de_id FROM interacciones WHERE a_id = ? AND tipo IN "
        "('like','superfan')",
        (perfil.id,),
    ).fetchall()
    respondidos = almacen.vistos_por(perfil.id)
    salida = []
    for f in filas:
        if f["de_id"] in respondidos:
            continue
        otro = almacen.perfil(f["de_id"])
        if otro and pasa_filtros(perfil, otro, reciproco=False)[0]:
            salida.append(otro)
    return salida


def ronda_valida(almacen, perfil: Perfil, fila) -> bool:
    """¿Todas las caras de esta ronda siguen pasando los filtros del usuario?

    Existe porque la ronda se guarda en la base y los filtros se cambian
    después. Si alguien juega una ronda, va a Filtros y pide "sólo mujeres",
    al volver se encontraba con la MISMA ronda de antes —tres hombres
    incluidos— porque retomar no revalidaba nada. Reportado desde el APK con
    una captura: cuatro caras, tres de ellas del género que el usuario había
    pedido no ver.

    En serverless pasa lo mismo sin tocar los filtros: la instancia que armó la
    ronda podía tener las preferencias viejas (ver `filtroCliente.js`).
    """
    for id_ in json.loads(fila["opciones"]):
        otro = almacen.perfil(id_)
        if not otro or not pasa_filtros(perfil, otro, reciproco=False)[0]:
            return False
    return True


def nueva_ronda(almacen, perfil: Perfil, ahora: datetime | None = None) -> dict:
    # Si quedó una ronda sin resolver, se retoma ésa: abrir otra sería una
    # forma gratis de descartar la difícil. Va ANTES del cupo a propósito —
    # retomar lo ya abierto no puede fallar por turnos, si no la ronda del
    # día queda inaccesible con el cupo de 1.
    abierta = almacen.con.execute(
        "SELECT * FROM crushtime WHERE usuario_id = ? AND resuelto = 0 LIMIT 1",
        (perfil.id,),
    ).fetchone()
    if abierta:
        if ronda_valida(almacen, perfil, abierta):
            return _armar_payload(almacen, abierta)
        # La ronda quedó vieja respecto de los filtros de hoy. Se BORRA en vez
        # de marcarse resuelta: marcarla resuelta le comería el turno al
        # usuario por un problema que no causó. Y al borrarla, el flujo sigue
        # abajo y arma una nueva con los filtros vigentes.
        almacen.con.execute("DELETE FROM crushtime WHERE id = ?", (abierta["id"],))
        almacen.con.commit()

    maximo = planes.limites_de(perfil).crushtime_por_dia
    if rondas_de_hoy(almacen, perfil.id, ahora) >= maximo:
        raise SinTurnos(maximo)

    gustaron = _pendientes_que_me_gustaron(almacen, perfil)
    if not gustaron:
        raise DatosInvalidos(
            "por ahora nadie nuevo te dio like; volvé más tarde y jugás"
        )

    rng = random.Random()
    objetivo = rng.choice(gustaron)

    # Señuelos: gente que pasa tus filtros y NO te dio like. Sin ese segundo
    # requisito, "errar" podría ser acertarle a otro que también te gustó, y
    # el juego no tendría respuesta correcta única.
    dieron_like = {p.id for p in gustaron}
    vistos = almacen.vistos_por(perfil.id)
    senuelos = [
        o for o in almacen.todos()
        if o.id != perfil.id
        and o.id not in dieron_like
        and o.id not in vistos
        and o.completo
        and o.activo
        and pasa_filtros(perfil, o, reciproco=False)[0]
    ]
    rng.shuffle(senuelos)
    elegidos = senuelos[: OPCIONES - 1]
    if not elegidos:
        # Con un universo muy filtrado puede no haber señuelos: una ronda de
        # una sola cara se acierta sola y regala el juego.
        raise DatosInvalidos(
            "no hay suficiente gente que pase tus filtros para armar la ronda"
        )

    ronda_id = uuid.uuid4().hex[:12]
    opciones = [objetivo.id] + [o.id for o in elegidos]
    almacen.con.execute(
        "INSERT INTO crushtime (id, usuario_id, fecha, objetivo_id, opciones, resuelto, momento) "
        "VALUES (?,?,?,?,?,0,?)",
        (ronda_id, perfil.id, _hoy(ahora), objetivo.id, json.dumps(opciones),
         (ahora or datetime.utcnow()).isoformat()),
    )
    almacen.con.commit()
    fila = almacen.con.execute("SELECT * FROM crushtime WHERE id = ?", (ronda_id,)).fetchone()
    return _armar_payload(almacen, fila)


def _armar_payload(almacen, fila) -> dict:
    """Las caras de la ronda, barajadas con semilla del id: el mismo orden en
    cada consulta (si no, recargar la pantalla reordena y confunde), pero SIN
    ninguna marca de quién es el objetivo."""
    ids = json.loads(fila["opciones"])
    rng = random.Random(fila["id"])
    rng.shuffle(ids)
    caras = []
    for id_ in ids:
        p = almacen.perfil(id_)
        if p:
            caras.append(p.a_dict())
    return {"ronda": fila["id"], "caras": caras}


def adivinar(almacen, perfil: Perfil, ronda_id: str, elegido_id: str) -> dict:
    fila = almacen.con.execute(
        "SELECT * FROM crushtime WHERE id = ? AND usuario_id = ?",
        (ronda_id, perfil.id),
    ).fetchone()
    if not fila:
        raise DatosInvalidos("esa ronda no existe o no es tuya")
    if fila["resuelto"]:
        raise DatosInvalidos("esa ronda ya se jugó")
    if elegido_id not in json.loads(fila["opciones"]):
        raise DatosInvalidos("esa persona no está en la ronda")

    almacen.con.execute("UPDATE crushtime SET resuelto = 1 WHERE id = ?", (ronda_id,))
    almacen.con.commit()

    if elegido_id != fila["objetivo_id"]:
        # No se revela quién era: el like sigue pendiente y puede volver a
        # aparecer en otra ronda. Revelarlo mata el juego.
        return {"acierto": False}

    # Acertar es el like de vuelta: la otra persona ya había dicho que sí.
    r = almacen.interactuar(perfil, elegido_id, "like")
    otro = almacen.perfil(elegido_id)
    return {
        "acierto": True,
        "match": r.get("match", False),
        "match_id": r.get("match_id"),
        "con": otro.a_dict() if otro else None,
    }
