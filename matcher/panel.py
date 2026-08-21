"""El panel del dueño: cuántos clientes, cuántas descargas, cuánta plata.

POR QUÉ EXISTE
Hasta ahora, para saber cómo iba el negocio había que abrir la base con
`sqlite3` y escribir consultas a mano. Eso no es un producto: es un archivo.
Este módulo calcula los números y `/api/panel` los sirve, así se miran desde el
navegador o desde la app, sin correr una sola línea de Python.

DE DÓNDE SALEN LOS NÚMEROS
De la base, contando. No hay estimaciones ni proyecciones acá: eso es
`marketing/modelo_negocio.py`, que es otra cosa y está separado a propósito.
Un panel que mezcla lo que pasó con lo que uno espera que pase no sirve para
decidir nada.

EL NETO ES UNA ESTIMACIÓN Y SE DICE
Lo único que la app sabe con certeza es lo que facturó (bruto). La comisión
real la descuenta la pasarela y varía por medio de pago, por plan del vendedor
y por promoción; los impuestos dependen de cómo esté constituido el negocio.
Por eso el neto viaja con `estimado: true` y con el porcentaje usado a la
vista: un número que parece exacto y no lo es, es peor que uno que se declara
aproximado.
"""

from __future__ import annotations

from datetime import datetime, timedelta

# Comisión de la pasarela sobre el bruto. Es el mismo valor que usa el modelo
# de negocio (`marketing/modelo_negocio.py`), y es una ESTIMACIÓN de cobro web
# en Latinoamérica. Verificalo contra tu liquidación real de MercadoPago y
# corregilo acá si difiere: es un solo lugar.
COMISION_ESTIMADA = 0.054

# Ventanas de actividad. 7 días es "esta semana"; 30, "sigue con nosotros".
DIAS_ACTIVO = 30
DIAS_RECIENTE = 7

PLATAFORMAS = ("apk", "exe", "web", "ios")


def _iso(dias: int) -> str:
    return (datetime.utcnow() - timedelta(days=dias)).isoformat()


def _uno(con, sql: str, *args) -> int:
    fila = con.execute(sql, args).fetchone()
    return (fila[0] or 0) if fila else 0


def registrar_descarga(almacen, plataforma: str, referente: str = "") -> None:
    """Una descarga más. No guarda IP ni nada que identifique a la persona:
    para saber cuántos bajaron el programa no hace falta saber quiénes son, y
    un dato personal que no se guarda es un dato que no se puede filtrar."""
    if plataforma not in PLATAFORMAS:
        return
    almacen.con.execute(
        "INSERT INTO descargas (plataforma, referente, momento) VALUES (?,?,?)",
        (plataforma, (referente or "")[:120], datetime.utcnow().isoformat()),
    )
    almacen.con.commit()


def _usuarios(con) -> dict:
    # `sintetico` vive adentro del JSON del perfil. No hay columna, así que se
    # filtra por texto: es feo pero es una sola consulta y la alternativa era
    # una migración de esquema para un contador.
    reales = "datos NOT LIKE '%\"sintetico\": true%'"
    return {
        "total": _uno(con, f"SELECT COUNT(*) FROM perfiles WHERE {reales}"),
        "sinteticos": _uno(con, "SELECT COUNT(*) FROM perfiles WHERE datos LIKE '%\"sintetico\": true%'"),
        "borradas": _uno(con, "SELECT COUNT(*) FROM perfiles WHERE datos LIKE '%\"borrada\": true%'"),
        "activos_30d": _uno(
            con,
            f"SELECT COUNT(*) FROM perfiles WHERE {reales} AND datos > '' "
            "AND json_extract(datos, '$.ultima_actividad') >= ?",
            _iso(DIAS_ACTIVO),
        ),
        "activos_7d": _uno(
            con,
            f"SELECT COUNT(*) FROM perfiles WHERE {reales} "
            "AND json_extract(datos, '$.ultima_actividad') >= ?",
            _iso(DIAS_RECIENTE),
        ),
    }


def _planes(con) -> dict:
    salida = {}
    for codigo in ("gratis", "plus", "gold"):
        salida[codigo] = _uno(
            con,
            "SELECT COUNT(*) FROM perfiles WHERE json_extract(datos, '$.plan') = ? "
            "AND datos NOT LIKE '%\"sintetico\": true%'",
            codigo,
        )
    return salida


def _dinero(con) -> dict:
    """Sólo cuenta pagos en estado `pagado`. Un checkout abierto que nadie
    pagó no es plata, y meterlo en el total es mentirse a uno mismo."""
    filas = con.execute(
        "SELECT plan, periodo, monto, moneda, momento FROM pagos WHERE estado = 'pagado'"
    ).fetchall()
    bruto = sum(f["monto"] for f in filas)
    por_mes: dict[str, float] = {}
    for f in filas:
        mes = (f["momento"] or "")[:7]
        por_mes[mes] = round(por_mes.get(mes, 0.0) + f["monto"], 2)

    desde_30 = _iso(30)
    bruto_30 = sum(f["monto"] for f in filas if (f["momento"] or "") >= desde_30)
    return {
        "cobros": len(filas),
        "bruto": round(bruto, 2),
        "bruto_30d": round(bruto_30, 2),
        "neto_estimado": round(bruto * (1 - COMISION_ESTIMADA), 2),
        "comision_estimada_pct": round(COMISION_ESTIMADA * 100, 2),
        "estimado": True,
        "por_mes": dict(sorted(por_mes.items())),
        "moneda": filas[0]["moneda"] if filas else "USD",
        "pendientes": _uno(con, "SELECT COUNT(*) FROM pagos WHERE estado = 'pendiente'"),
    }


def _descargas(con) -> dict:
    total = {p: _uno(con, "SELECT COUNT(*) FROM descargas WHERE plataforma = ?", p)
             for p in PLATAFORMAS}
    return {
        "por_plataforma": total,
        "total": sum(total.values()),
        "ultimos_30d": _uno(con, "SELECT COUNT(*) FROM descargas WHERE momento >= ?", _iso(30)),
    }


def _actividad(con) -> dict:
    return {
        "matches": _uno(con, "SELECT COUNT(*) FROM matches"),
        "mensajes": _uno(con, "SELECT COUNT(*) FROM mensajes"),
        "videollamadas": _uno(con, "SELECT COUNT(*) FROM videollamadas WHERE estado = 'aceptada'"),
        "reportes": _uno(con, "SELECT COUNT(*) FROM reportes"),
    }


def resumen(almacen) -> dict:
    con = almacen.con
    usuarios = _usuarios(con)
    planes_ = _planes(con)
    pagando = planes_["plus"] + planes_["gold"]
    base = usuarios["total"] or 1
    return {
        "momento": datetime.utcnow().isoformat(),
        "usuarios": usuarios,
        "planes": planes_,
        "pagando": pagando,
        # Conversión sobre usuarios REALES, no sobre los sintéticos de la demo:
        # con la demo poblada, dividir por el total daría un número inventado.
        "conversion_pct": round(pagando * 100 / base, 2),
        "dinero": _dinero(con),
        "descargas": _descargas(con),
        "actividad": _actividad(con),
    }
