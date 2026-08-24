"""Mandar un mail al dueño. Una sola vía, usada por todo el que avise algo.

POR QUÉ ESTÁ SEPARADO
Esto vivía adentro de `solicitudes.py`, atado al formulario de demo. Cuando
apareció la segunda cosa que hay que avisar —que alguien apretó "comprar"— la
alternativa era copiar cincuenta líneas de Resend y SMTP. Dos copias del mismo
envío se desincronizan a la primera: se arregla un timeout en una y la otra
sigue colgándose.

DOS REGLAS QUE NO SE TOCAN

1. **Nunca levanta.** Un aviso que falla no puede tirar abajo lo que lo
   disparó. Si el mail de "alguien quiere comprar" explota, la persona tiene
   que llegar igual a MercadoPago. Todos los errores se tragan acá adentro y
   la función devuelve `False`.

2. **No se loguea el detalle del error.** El mensaje de fallo de un proveedor
   de correo suele traer adentro la dirección de destino y a veces parte de la
   credencial. Un log con eso es una filtración escrita por nosotros mismos.

SOBRE EL SEGUNDO PLANO
`mandar_en_segundo_plano` existe porque hay un aviso que se dispara en medio
de un pago. Ahí el usuario está esperando que lo manden a MercadoPago, y meterle
una llamada HTTP más —con su timeout— en el camino crítico de una compra es el
peor lugar posible para agregar latencia. El hilo es `daemon`: si el proceso se
apaga antes de que salga, se pierde EL AVISO, nunca el pago (que ya está
escrito en la base y se ve en el panel).
"""

from __future__ import annotations

import json
import os
import smtplib
import threading
import urllib.request
from email.message import EmailMessage

# A dónde va el aviso. El pedido del dueño fue explícito: que caiga en su mail.
DESTINO_POR_DEFECTO = "vieraschiavi@gmail.com"

# Corto a propósito. Estos avisos salen en el camino de un pago o de un
# formulario: más de esto esperando a un proveedor de correo es peor que
# perder el aviso.
TIMEOUT_SEG = 8


def destino() -> str:
    return (
        os.getenv("MATCHER_EMAIL_DEMOS", DESTINO_POR_DEFECTO).strip()
        or DESTINO_POR_DEFECTO
    )


def _smtp_configurado() -> dict | None:
    host = os.getenv("MATCHER_SMTP_HOST", "").strip()
    usuario = os.getenv("MATCHER_SMTP_USUARIO", "").strip()
    clave = os.getenv("MATCHER_SMTP_CLAVE", "").strip()
    if not (host and usuario and clave):
        return None
    return {
        "host": host,
        "puerto": int(os.getenv("MATCHER_SMTP_PUERTO", "587")),
        "usuario": usuario,
        "clave": clave,
    }


def como_avisa() -> str:
    """Qué vía está configurada: `resend`, `smtp` o `ninguna`.

    Lo muestra el panel para que el dueño sepa si los avisos le llegan al mail
    o si tiene que entrar a mirarlos.
    """
    if os.getenv("RESEND_API_KEY", "").strip():
        return "resend"
    if _smtp_configurado():
        return "smtp"
    return "ninguna"


def _por_resend(asunto: str, cuerpo: str, responder_a: str) -> bool:
    """Resend: una sola API key, sin host ni puerto. Es lo más simple de
    configurar y tiene plan gratis.

    OJO CON EL REMITENTE. Para mandar desde `avisos@tudominio.com` hay que
    verificar el dominio en Resend (un par de registros DNS). Sin dominio
    verificado, Resend sólo deja el remitente `onboarding@resend.dev`, y desde
    ése **únicamente se puede escribir a la dirección de tu propia cuenta de
    Resend**. Para este uso alcanza —el aviso va justamente a tu mail— pero si
    algún día querés escribirle al cliente desde acá, hace falta el dominio.
    """
    clave = os.getenv("RESEND_API_KEY", "").strip()
    if not clave:
        return False
    remitente = os.getenv("MATCHER_EMAIL_REMITENTE", "onboarding@resend.dev").strip()
    carga = {
        "from": f"Matcher <{remitente}>",
        "to": [destino()],
        "subject": asunto,
        "text": cuerpo,
    }
    if responder_a:
        # Responder va directo a la persona, sin copiar la dirección a mano:
        # es la diferencia entre contestar en 30 segundos o dejarlo para
        # después y no contestar nunca.
        carga["reply_to"] = responder_a
    pedido = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(carga).encode(),
        method="POST",
        headers={"Authorization": f"Bearer {clave}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(pedido, timeout=TIMEOUT_SEG) as r:
            return 200 <= r.status < 300
    except Exception:
        return False


def _por_smtp(asunto: str, cuerpo: str, responder_a: str) -> bool:
    """Alternativa para quien ya tiene servidor de correo y no quiere sumar
    otro servicio."""
    smtp = _smtp_configurado()
    if not smtp:
        return False
    try:
        m = EmailMessage()
        m["Subject"] = asunto
        m["From"] = smtp["usuario"]
        m["To"] = destino()
        if responder_a:
            m["Reply-To"] = responder_a
        m.set_content(cuerpo)
        with smtplib.SMTP(smtp["host"], smtp["puerto"], timeout=TIMEOUT_SEG) as s:
            s.starttls()
            s.login(smtp["usuario"], smtp["clave"])
            s.send_message(m)
        return True
    except Exception:
        return False


def mandar(asunto: str, cuerpo: str, responder_a: str = "") -> bool:
    """Manda el mail y devuelve si salió. NUNCA levanta.

    Resend primero porque se configura con una sola variable; SMTP queda para
    quien ya tiene servidor propio. Si no hay ninguno de los dos devuelve
    `False` sin hacer nada — y el que llamó tiene que seguir funcionando igual,
    nunca prometerle a nadie un mail que el sistema no puede mandar.
    """
    return _por_resend(asunto, cuerpo, responder_a) or _por_smtp(
        asunto, cuerpo, responder_a
    )


def mandar_en_segundo_plano(asunto: str, cuerpo: str, responder_a: str = "") -> None:
    """Igual que `mandar`, pero sin hacer esperar a nadie.

    Para los avisos que se disparan en medio de un pago: el usuario está
    esperando que lo manden a la pasarela, y una llamada HTTP más en el camino
    crítico de una compra es exactamente donde no hay que agregar latencia.

    `daemon=True` a propósito: si el proceso se apaga antes de que salga, se
    pierde el aviso — nunca el pago, que ya está escrito en la base y se ve en
    el panel. Perder un mail es molesto; demorar un checkout cuesta la venta.
    """
    if como_avisa() == "ninguna":
        return  # nada que mandar: ni siquiera se levanta el hilo
    threading.Thread(
        target=mandar, args=(asunto, cuerpo, responder_a), daemon=True
    ).start()
