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


def registrar_descarga(almacen, plataforma: str, referente: str = "", perfil=None) -> None:
    """Una descarga más, con la cuenta que la bajó y el plan que tenía.

    NO se guarda la IP. Para responder "quién bajó qué" alcanza con la cuenta,
    que ya la tenemos porque la descarga exige sesión; la IP no agrega nada a
    esa pregunta y es un dato personal más que se puede filtrar.

    El plan va CONGELADO acá y no se lee del perfil al mirar el panel: si se
    leyera después, un cliente que hoy es Gold figuraría como si siempre lo
    hubiera sido, y se perdería justo el dato que sirve — que bajó el programa
    siendo gratis y pagó más tarde.
    """
    if plataforma not in PLATAFORMAS:
        return
    almacen.con.execute(
        "INSERT INTO descargas (plataforma, referente, usuario_id, plan, momento) "
        "VALUES (?,?,?,?,?)",
        (
            plataforma,
            (referente or "")[:120],
            getattr(perfil, "id", "") or "",
            getattr(perfil, "plan", "") or "",
            datetime.utcnow().isoformat(),
        ),
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
    """Cuántas cuentas hay en cada plan, SIN las del dueño.

    Las cuentas de `MATCHER_CUENTAS_DUENIO` están en Gold porque `duenio.py`
    se las pone, no porque hayan pagado. Contarlas acá inflaba las dos cifras
    que este panel existe para responder: en una base recién estrenada decía
    "Pagando: 2 · 66,67% de conversión" al lado de "Facturado: USD 0" — dos
    números que se contradicen en la misma pantalla, y el equivocado es el que
    uno mira para decidir si el negocio funciona.

    La plata nunca estuvo mal (`_dinero` sólo suma cobros reales); lo que
    estaba mal era el CONTEO de clientes que pagan.
    """
    from . import duenio

    del_duenio = duenio.emails()
    salida = {}
    for codigo in ("gratis", "plus", "gold"):
        filas = con.execute(
            "SELECT email FROM perfiles WHERE json_extract(datos, '$.plan') = ? "
            "AND datos NOT LIKE '%\"sintetico\": true%'",
            (codigo,),
        ).fetchall()
        salida[codigo] = sum(
            1 for f in filas if (f["email"] or "").strip().lower() not in del_duenio
        )
    salida["del_duenio"] = len(del_duenio)
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
    por_plan = {
        f["plan"] or "(anónima)": f["c"]
        for f in con.execute(
            "SELECT plan, COUNT(*) c FROM descargas GROUP BY plan"
        ).fetchall()
    }
    return {
        "por_plataforma": total,
        # Con qué plan bajaron el programa. `(anónima)` son las descargas de
        # antes de que la descarga exigiera cuenta: de ésas no se sabe quién
        # fue, y decirlo es mejor que meterlas en "gratis" y ensuciar el dato.
        "por_plan": por_plan,
        "total": sum(total.values()),
        "ultimos_30d": _uno(con, "SELECT COUNT(*) FROM descargas WHERE momento >= ?", _iso(30)),
    }


def clientes(almacen, limite: int = 500) -> list[dict]:
    """Cliente por cliente: qué plan tiene, hasta cuándo, cuánto pagó y qué
    bajó. Es la vista que contesta "¿este cliente tiene lo que pagó?" sin
    abrir la base.

    Sólo cuentas REALES: los perfiles sintéticos de la demo no son clientes y
    mezclarlos acá convierte la lista en un número inventado.

    No incluye la contraseña ni el hash, obviamente, pero tampoco la bio, las
    fotos ni la ubicación: esto es la vista comercial, no una ventana a la
    cuenta de la gente. Un panel de administración que muestra el perfil
    entero es la forma más común de que un dato personal termine donde no va.
    """
    import json as _json

    filas = almacen.con.execute(
        "SELECT id, email, datos FROM perfiles "
        "WHERE datos NOT LIKE '%\"sintetico\": true%' "
        "ORDER BY json_extract(datos, '$.ultima_actividad') DESC LIMIT ?",
        (limite,),
    ).fetchall()

    pagado: dict[str, float] = {}
    for f in almacen.con.execute(
        "SELECT usuario_id, SUM(monto) t FROM pagos WHERE estado = 'pagado' "
        "GROUP BY usuario_id"
    ).fetchall():
        pagado[f["usuario_id"]] = round(f["t"] or 0.0, 2)

    bajadas: dict[str, list] = {}
    for f in almacen.con.execute(
        "SELECT usuario_id, plataforma, plan, momento FROM descargas "
        "WHERE usuario_id <> '' ORDER BY momento DESC"
    ).fetchall():
        bajadas.setdefault(f["usuario_id"], []).append(
            {"plataforma": f["plataforma"], "plan": f["plan"], "momento": f["momento"]}
        )

    salida = []
    for f in filas:
        d = _json.loads(f["datos"]) if f["datos"] else {}
        if d.get("borrada"):
            continue
        salida.append({
            "id": f["id"],
            "email": f["email"],
            "nombre": d.get("nombre", ""),
            "plan": d.get("plan", "gratis"),
            "plan_vence": d.get("plan_vence"),
            "pagado": pagado.get(f["id"], 0.0),
            "descargas": bajadas.get(f["id"], []),
            "ultima_actividad": d.get("ultima_actividad"),
        })
    return salida


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
    # La base de la conversión también saca las cuentas del dueño: si están
    # arriba y abajo de la división, el porcentaje sale de comparar clientes
    # con no-clientes.
    base = max(1, usuarios["total"] - planes_["del_duenio"])
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
