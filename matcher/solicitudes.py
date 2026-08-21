"""Pedidos de demo: la demo deja de ser pública y pasa a ser bajo pedido.

POR QUÉ CAMBIÓ
Una demo abierta le regala el producto a la competencia. Quien entra se lleva
el artefacto entero —las pantallas, los flujos, las decisiones de diseño— sin
dejar rastro y sin que nadie le venda nada. Un video muestra el RESULTADO; una
demo abierta entrega la INGENIERÍA.

Ahora: el video queda público (es el resultado visual, y sirve para atraer), y
para ver la app andando hay que pedirlo. Eso da tres cosas que una demo abierta
no da: no se regala el artefacto, queda registrado quién pidió y con qué mail,
y la demo se hace acompañada — o sea, vendiendo.

TRES DECISIONES QUE IMPORTAN

1. **Se guarda ANTES de avisar.** Si el mail falla —credenciales mal, el SMTP
   caído, sin red— el pedido ya está en la base y aparece en el panel. Al
   revés, un pedido se perdería sin que nadie se entere: el prospecto cree que
   pidió y del otro lado no llegó nada.
2. **Sin SMTP configurado esto igual funciona.** No manda mail y lo dice; el
   pedido queda en el panel. Nunca se le promete al que pide un mail que el
   sistema no puede mandar (regla 10 del producto).
3. **Son datos personales de un tercero.** Nombre, mail, empresa y país de
   alguien que todavía no es cliente. No se loguean, no se devuelven por
   ninguna ruta pública, y sólo los lee el dueño.
"""

from __future__ import annotations

import json
import os
import re
import smtplib
import urllib.request
import uuid
from datetime import datetime, timedelta
from email.message import EmailMessage

from .modelos import DatosInvalidos

# A dónde va el aviso. El pedido del dueño fue explícito: que caiga en su mail.
DESTINO_POR_DEFECTO = "vieraschiavi@gmail.com"

# Tope de pedidos por dirección de mail en una ventana. No es anti-spam serio
# —eso es un captcha o un WAF— pero corta el caso tonto de apretar el botón
# veinte veces, que es el que llena la bandeja de entrada de verdad.
TOPE_POR_EMAIL = 3
VENTANA = timedelta(hours=24)

LARGOS = {"nombre": 120, "empresa": 120, "pais": 60, "email": 200, "mensaje": 1000}

# Validación deliberadamente laxa: sirve para atajar el error de tipeo, no para
# decidir si una dirección existe. Eso lo dice el mail que rebota, no un regex
# — y un regex estricto de más rechaza direcciones válidas y raras.
_EMAIL = re.compile(r"^[^@\s]+@[^@\s.]+\.[^@\s]+$")


def _limpio(valor: str, campo: str) -> str:
    texto = " ".join((valor or "").split())
    return texto[: LARGOS[campo]]


def validar(datos: dict) -> dict:
    """Devuelve los campos limpios o explota con el motivo."""
    nombre = _limpio(datos.get("nombre", ""), "nombre")
    email = _limpio(datos.get("email", ""), "email").lower()
    empresa = _limpio(datos.get("empresa", ""), "empresa")
    pais = _limpio(datos.get("pais", ""), "pais")
    mensaje = _limpio(datos.get("mensaje", ""), "mensaje")

    if len(nombre.split()) < 2:
        raise DatosInvalidos("poné tu nombre y apellido")
    if not _EMAIL.match(email):
        raise DatosInvalidos("revisá el email")
    if not empresa:
        raise DatosInvalidos("falta la empresa (si sos independiente, poné 'independiente')")
    if not pais:
        raise DatosInvalidos("falta el país")
    return {
        "nombre": nombre, "email": email, "empresa": empresa,
        "pais": pais, "mensaje": mensaje,
    }


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


def destino() -> str:
    return os.getenv("MATCHER_EMAIL_DEMOS", DESTINO_POR_DEFECTO).strip() or DESTINO_POR_DEFECTO


def _asunto(datos: dict) -> str:
    return f"Demo de Matcher · {datos['nombre']} ({datos['empresa']})"


def _cuerpo(datos: dict) -> str:
    return (
        f"Pidieron una demo de Matcher.\n\n"
        f"Nombre:  {datos['nombre']}\n"
        f"Email:   {datos['email']}\n"
        f"Empresa: {datos['empresa']}\n"
        f"País:    {datos['pais']}\n\n"
        f"Mensaje:\n{datos['mensaje'] or '(sin mensaje)'}\n\n"
        f"Respondé este mail para contestarle directo.\n"
    )


def _avisar_resend(datos: dict) -> bool:
    """Resend: una sola API key, sin host ni puerto. Es lo más simple de
    configurar en Vercel y tiene plan gratis.

    OJO CON EL REMITENTE. Para mandar desde `demos@tudominio.com` hay que
    verificar el dominio en Resend (un par de registros DNS). Sin dominio
    verificado, Resend sólo deja el remitente `onboarding@resend.dev`, y desde
    ése **únicamente se puede escribir a la dirección de tu propia cuenta de
    Resend**. Para este uso alcanza —el aviso va justamente a tu mail— pero si
    algún día querés escribirle al prospecto desde acá, hace falta el dominio.
    """
    clave = os.getenv("RESEND_API_KEY", "").strip()
    if not clave:
        return False
    remitente = os.getenv("MATCHER_EMAIL_REMITENTE", "onboarding@resend.dev").strip()
    cuerpo = json.dumps({
        "from": f"Matcher <{remitente}>",
        "to": [destino()],
        "subject": _asunto(datos),
        "text": _cuerpo(datos),
        # Responder va directo al prospecto, sin copiar la dirección a mano:
        # es la diferencia entre contestar en 30 segundos o dejarlo para
        # después y no contestar nunca.
        "reply_to": datos["email"],
    }).encode()
    pedido = urllib.request.Request(
        "https://api.resend.com/emails",
        data=cuerpo,
        method="POST",
        headers={"Authorization": f"Bearer {clave}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(pedido, timeout=15) as r:
            return 200 <= r.status < 300
    except Exception:
        return False


def _avisar_smtp(datos: dict) -> bool:
    """Alternativa por SMTP, para quien ya tiene un servidor de correo y no
    quiere sumar otro servicio."""
    smtp = _smtp_configurado()
    if not smtp:
        return False
    try:
        m = EmailMessage()
        m["Subject"] = _asunto(datos)
        m["From"] = smtp["usuario"]
        m["To"] = destino()
        m["Reply-To"] = datos["email"]
        m.set_content(_cuerpo(datos))
        with smtplib.SMTP(smtp["host"], smtp["puerto"], timeout=15) as s:
            s.starttls()
            s.login(smtp["usuario"], smtp["clave"])
            s.send_message(m)
        return True
    except Exception:
        return False


def _avisar(datos: dict) -> bool:
    """Manda el mail. Devuelve si salió. NUNCA levanta: el pedido ya está
    guardado y perder el aviso no puede tirar abajo la respuesta al que pidió.

    Resend primero porque es el que se configura con una sola variable; SMTP
    queda para quien ya tiene servidor propio. Si no hay ninguno de los dos, el
    pedido igual queda en el panel — nunca se le promete al que pide un mail
    que el sistema no puede mandar (regla 10 del producto).

    Los errores se tragan a propósito y sin loguear el detalle: el mensaje de
    fallo del proveedor puede traer adentro la dirección del prospecto.
    """
    return _avisar_resend(datos) or _avisar_smtp(datos)


def como_avisa() -> str:
    """Qué vía está configurada. Lo muestra el panel para que el dueño sepa si
    los pedidos le llegan al mail o si tiene que entrar a mirarlos."""
    if os.getenv("RESEND_API_KEY", "").strip():
        return "resend"
    if _smtp_configurado():
        return "smtp"
    return "ninguna"


def crear(almacen, datos: dict, origen: str = "") -> dict:
    limpio = validar(datos)

    recientes = almacen.con.execute(
        "SELECT COUNT(*) c FROM solicitudes_demo WHERE email = ? AND momento >= ?",
        (limpio["email"], (datetime.utcnow() - VENTANA).isoformat()),
    ).fetchone()["c"]
    if recientes >= TOPE_POR_EMAIL:
        raise DatosInvalidos(
            "ya tenemos tu pedido; te escribimos a la brevedad al mail que dejaste"
        )

    id_ = uuid.uuid4().hex[:16]
    almacen.con.execute(
        "INSERT INTO solicitudes_demo "
        "(id, nombre, email, empresa, pais, mensaje, origen, estado, momento) "
        "VALUES (?,?,?,?,?,?,?,'nueva',?)",
        (id_, limpio["nombre"], limpio["email"], limpio["empresa"], limpio["pais"],
         limpio["mensaje"], (origen or "")[:120], datetime.utcnow().isoformat()),
    )
    almacen.con.commit()

    # El aviso va DESPUÉS de guardar, y su resultado no cambia el del pedido.
    avisado = _avisar(limpio)
    if avisado:
        almacen.con.execute(
            "UPDATE solicitudes_demo SET avisado = 1 WHERE id = ?", (id_,)
        )
        almacen.con.commit()
    return {"id": id_, "avisado": avisado}


def listar(almacen, limite: int = 200) -> list[dict]:
    """Para el panel del dueño. No hay ruta pública que devuelva esto."""
    filas = almacen.con.execute(
        "SELECT * FROM solicitudes_demo ORDER BY momento DESC LIMIT ?", (limite,)
    ).fetchall()
    return [
        {
            "id": f["id"], "nombre": f["nombre"], "email": f["email"],
            "empresa": f["empresa"], "pais": f["pais"], "mensaje": f["mensaje"],
            "origen": f["origen"], "estado": f["estado"],
            "avisado": bool(f["avisado"]), "momento": f["momento"],
        }
        for f in filas
    ]


def marcar(almacen, id_: str, estado: str) -> None:
    """`nueva` → `agendada` → `hecha` (o `descartada`). Es el mínimo para no
    perder de vista a quién ya le contestaste."""
    if estado not in ("nueva", "agendada", "hecha", "descartada"):
        raise DatosInvalidos("estado desconocido")
    almacen.con.execute(
        "UPDATE solicitudes_demo SET estado = ? WHERE id = ?", (estado, id_)
    )
    almacen.con.commit()
