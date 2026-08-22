"""Freno de intentos: cuántas veces se puede errar la contraseña.

POR QUÉ EXISTE
Sin esto, `/api/login` acepta contraseñas a la velocidad que las mande quien
sea. Dos consecuencias, y la segunda es la que sorprende:

1. **Fuerza bruta y credential stuffing.** Una app de citas es un objetivo
   goloso: adentro hay conversaciones privadas, fotos y ubicación. Las listas
   de "email + contraseña" filtradas de otros sitios se prueban en masa, y sin
   freno el único límite es el ancho de banda del atacante.
2. **Es un DoS regalado.** Verificar una contraseña cuesta 260.000 iteraciones
   de PBKDF2 a propósito (`seguridad.ITERACIONES`) — es caro para el que
   adivina, pero lo paga el SERVIDOR. Un puñado de pedidos por segundo con
   cualquier contraseña deja la CPU al palo y la app deja de responder para
   todos. Por eso el freno se consulta **antes** de hashear: a un pedido
   frenado no se le gasta un ciclo.

DOS LLAVES, Y NO VALEN LO MISMO
- **Por email** — es la que protege de verdad una cuenta puntual. No se puede
  falsificar: quien quiere entrar a `ana@…` tiene que mandar `ana@…`.
- **Por IP** — atrapa al que rocía muchas cuentas distintas con una contraseña
  común. Es **best-effort**: la IP sale de `X-Forwarded-For`, que detrás de un
  proxy que no la reescriba se puede mentir. Sirve, pero no se apoya la
  seguridad ahí; la que sostiene es la de arriba.

DOS DETALLES QUE PARECEN MENORES
- Se cuenta el intento **exista o no** la cuenta. Si sólo se frenaran los
  emails registrados, un 429 sería la respuesta a "¿esta persona tiene cuenta
  acá?" — que es justo lo que el mensaje de error único se cuida de no decir.
- El acierto **limpia** los fallos de ese email. Si no, alguien que te sabe el
  mail te deja la cuenta trabada gritando contraseñas al aire, y el frenado
  termina siendo el dueño. La llave por IP no se limpia: un acierto entre
  cincuenta fallos sigue oliendo a barrido.
"""

from __future__ import annotations

from datetime import datetime, timedelta

# Ventana y topes. Ocho intentos por email es holgado para alguien que de
# verdad no se acuerda de la contraseña, y ridículo para adivinarla: con 8
# cada 15 minutos son 768 por día contra un espacio de claves de 8 caracteres.
VENTANA = timedelta(minutes=15)
TOPE_EMAIL = 8
TOPE_IP = 40


def _limite(llave: str) -> int:
    return TOPE_IP if llave.startswith("ip:") else TOPE_EMAIL


def _ahora(ahora: datetime | None) -> datetime:
    return ahora or datetime.utcnow()


def llaves(email: str, ip: str) -> list[str]:
    """Las llaves con las que se cuenta este intento.

    El email va normalizado igual que en el login (`strip().lower()`), porque
    si no `Ana@X` y `ana@x` son dos cubetas distintas para la misma cuenta y el
    tope se duplica escribiendo el mail con otra caja.
    """
    salida = []
    limpio = (email or "").strip().lower()
    if limpio:
        salida.append(f"email:{limpio[:200]}")
    if ip:
        salida.append(f"ip:{ip[:64]}")
    return salida


def espera(almacen, llaves_: list[str], ahora: datetime | None = None) -> int:
    """Segundos que faltan para poder intentar de nuevo. 0 = adelante.

    Se llama ANTES de verificar la contraseña: el pedido frenado no tiene que
    costar los 260.000 ciclos de PBKDF2 (ver el encabezado).
    """
    momento = _ahora(ahora)
    desde = (momento - VENTANA).isoformat()
    faltan = 0
    for llave in llaves_:
        filas = almacen.con.execute(
            "SELECT momento FROM intentos_login WHERE llave = ? AND momento >= ? "
            "ORDER BY momento",
            (llave, desde),
        ).fetchall()
        if len(filas) < _limite(llave):
            continue
        # El bloqueo se levanta solo, a medida que los intentos viejos salen de
        # la ventana. Un bloqueo de duración fija le da al atacante un reloj
        # para sincronizarse; éste lo obliga a esperar por cada intento.
        vence = datetime.fromisoformat(filas[0]["momento"]) + VENTANA
        faltan = max(faltan, int((vence - momento).total_seconds()) + 1)
    return max(0, faltan)


def anotar_fallo(almacen, llaves_: list[str], ahora: datetime | None = None) -> None:
    momento = _ahora(ahora)
    almacen.con.executemany(
        "INSERT INTO intentos_login (llave, momento) VALUES (?,?)",
        [(llave, momento.isoformat()) for llave in llaves_],
    )
    # Barrido barato de lo viejo. Sin esto la tabla crece para siempre con
    # datos que ya no se consultan: en SQLite sobre un disco chico eso termina
    # siendo el problema, no la fuerza bruta.
    almacen.con.execute(
        "DELETE FROM intentos_login WHERE momento < ?",
        ((momento - VENTANA * 4).isoformat(),),
    )
    almacen.con.commit()


def limpiar_email(almacen, email: str) -> None:
    """Acierto: se borran los fallos de ESE email, no los de la IP."""
    limpio = (email or "").strip().lower()
    if not limpio:
        return
    almacen.con.execute(
        "DELETE FROM intentos_login WHERE llave = ?", (f"email:{limpio[:200]}",)
    )
    almacen.con.commit()


def ip_de(request) -> str:
    """La IP del que pide, mirando primero el proxy.

    `request.client.host` detrás de Vercel/Railway es el proxy, o sea la misma
    para todo el mundo: frenar por eso sería frenar a todos juntos. El primer
    valor de `X-Forwarded-For` es el que ponen esas plataformas.

    OJO: ese encabezado lo puede escribir cualquiera si algún día esto queda
    expuesto sin proxy adelante. Por eso el freno por IP es el secundario y el
    que sostiene la seguridad es el freno por email (ver el encabezado).
    """
    reenviada = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if reenviada:
        return reenviada
    return getattr(getattr(request, "client", None), "host", "") or ""
