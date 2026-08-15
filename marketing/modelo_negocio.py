"""Modelo financiero de Matcher y generador de `docs/PLAN_NEGOCIO.md`.

Por qué esto es un programa y no un documento escrito a mano: un plan de
negocio con números tipeados queda viejo la primera vez que se toca un precio.
Acá los precios salen de `matcher.planes` —la misma fuente que usa la app— y
todo lo demás son supuestos declarados arriba de todo, en un solo lugar. Se
cambia un supuesto, se corre `python3 -m marketing.modelo_negocio` y el
documento sale de nuevo. **No editar `docs/PLAN_NEGOCIO.md` a mano.**

Advertencia que viaja también dentro del documento generado: esto es un
MODELO, no un pronóstico. Los supuestos de conversión, churn y costo por
instalación son rangos de mercado razonables para una app de citas chica y sin
marca; ninguno está medido sobre Matcher, porque Matcher todavía no tuvo un
solo usuario real. El valor del modelo no es el número final, es ver **qué
supuesto** manda el resultado — y ese, en todos los escenarios, es el mismo.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

from matcher import planes

MESES = 24
CORTES = (3, 6, 9, 12, 18, 24)


# ─────────────────────────────────────────────────────────────────────────────
# Supuestos de costos. Todos en USD.
# ─────────────────────────────────────────────────────────────────────────────

# Comisión de las tiendas. Apple (Small Business Program) y Google Play cobran
# 15 % mientras la facturación anual del desarrollador no pase USD 1.000.000;
# arriba de eso, 30 %. A la escala de este plan aplica el 15 %, pero la
# suscripción comprada DENTRO de la app tiene que pasar por su cobro: la
# pasarela propia (MercadoPago / dLocal / PayPal) sólo es válida en la web.
COMISION_TIENDA = 0.15
COMISION_TIENDA_ALTA = 0.30          # a partir de USD 1M/año facturados
UMBRAL_COMISION_ALTA = 1_000_000.0

# Pasarela web: ~3,5 % + IVA + retiro internacional. Se redondea a 5,4 %.
COMISION_WEB = 0.054

# Alta única en las tiendas.
ALTA_GOOGLE_PLAY = 25.0              # pago único, de por vida
CUOTA_APPLE_ANUAL = 99.0             # se paga en el mes 1 y en el 13

# Infraestructura. Escalones reales de un host con disco (Fly.io / Render):
# no crece lineal, crece por saltos cuando hay que sumar máquina.
def hosting(usuarios: int) -> float:
    if usuarios < 2_000:
        return 12.0                  # 1 máquina chica + volumen de 3 GB
    if usuarios < 10_000:
        return 35.0                  # 2 máquinas + volumen de 20 GB + Postgres
    if usuarios < 40_000:
        return 120.0
    if usuarios < 150_000:
        return 380.0
    return 900.0


# Fotos: hoy viajan como data-URI dentro de la base (ver docs/PUBLICAR.md). Con
# usuarios reales van a un bucket. 4 fotos por usuario, ~450 KB cada una
# después de comprimir = 1,8 MB por usuario acumulado, más el tráfico de
# servirlas (la foto del deck se ve muchas veces).
GB_POR_USUARIO = 0.0018
PRECIO_GB_MES = 0.023                # almacenamiento de objetos
PRECIO_GB_TRAFICO = 0.09             # egreso/CDN
GB_TRAFICO_POR_USUARIO_MES = 0.06    # ~60 MB de fotos vistas por usuario/mes

# Moderación. NO es opcional y no es sólo un costo: sin moderación de fotos y
# de chat, una app de citas se llena de abuso en la primera semana y es causal
# de baja en Play y en App Store.
COSTO_MODERACION_AUTOMATICA = 0.0015  # por imagen analizada (API de visión)
FOTOS_POR_ALTA = 4
COSTO_HORA_HUMANA = 15.0
ALTAS_POR_HORA_REVISION = 300.0       # revisar altas nuevas y perfiles reportados
USUARIOS_POR_HORA_SOPORTE = 2_000.0   # reportes, denuncias, bajas, consultas

# Cosas fijas que no dependen de la escala.
DOMINIO_ANUAL = 15.0
CORREO_TRANSACCIONAL_MES = 10.0       # verificación de email y avisos
CONTADOR_MES = 60.0                   # unipersonal en Uruguay, mínimo realista
LEGAL_UNICO = 250.0                   # política de privacidad + términos revisados

# Impuestos. Uruguay: IRAE 25 % sobre la renta neta fiscal, y las pérdidas se
# arrastran hasta 5 años. Se cobra sobre el resultado ANUAL positivo, no mes a
# mes, y recién después de compensar lo perdido antes.
IRAE = 0.25


# ─────────────────────────────────────────────────────────────────────────────
# Escenarios
# ─────────────────────────────────────────────────────────────────────────────


def rampa(valores: list[tuple[int, float]]) -> list[float]:
    """Presupuesto mensual descrito como tramos (hasta_mes, monto)."""
    salida: list[float] = []
    for mes in range(1, MESES + 1):
        monto = 0.0
        for hasta, valor in valores:
            if mes <= hasta:
                monto = valor
                break
        salida.append(monto)
    return salida


@dataclass(frozen=True)
class Escenario:
    codigo: str
    nombre: str
    resumen: str
    presupuesto: list[float]          # marketing por mes
    cpi: float                        # costo por instalación (USD)
    alta_por_instalacion: float       # instalaciones que completan el registro
    organicos_base: float             # altas/mes que no vienen de pauta
    factor_viral: float               # altas extra por usuario activo y mes
    # Probabilidad de que un usuario gratis ACTIVO empiece a pagar en un mes
    # cualquiera. No es "cuántos de los que se registran pagan": mucha gente
    # paga recién al tercer o cuarto mes, cuando ya le importa quién le dio
    # like. Modelarlo sólo en el mes del alta subestima el negocio.
    conversion_mensual: float
    churn_usuario: float              # baja mensual del padrón
    churn_suscriptor: float           # baja mensual del suscriptor
    mezcla_gold: float                # de los que pagan, cuántos van a Gold
    mezcla_anual: float               # cuántos pagan el plan anual
    share_tienda: float               # pagos que pasan por Apple/Google
    horas_propias: float = 0.0        # horas/mes de trabajo propio no pagado

    # ── Palanca de precio ────────────────────────────────────────────────
    # Cuánto se multiplican los precios de `matcher.planes`. 1.0 = los de hoy.
    # Subir el precio NO es gratis y el modelo tiene que decirlo: cobrar más
    # espanta gente antes de pagar (elasticidad de conversión) y hace que el
    # que ya paga aguante menos (elasticidad de churn). Un modelo que sube el
    # precio y deja la conversión quieta siempre "demuestra" que hay que
    # cobrar más, y es mentira.
    multiplicador_precio: float = 1.0
    # 1,0 = elástico puro (al doble de precio, la mitad de conversión, la
    # facturación no se mueve). Abajo de 1 conviene subir; arriba, no. Se
    # asume 0,8: Matcher se compara contra una competencia mucho más cara, así
    # que aguanta algo de suba antes de que la gente se vaya.
    elasticidad_conversion: float = 0.8
    # Cuánto se acelera la baja del suscriptor al subir el precio.
    elasticidad_churn: float = 0.25

    @property
    def conversion_efectiva(self) -> float:
        return self.conversion_mensual * self.multiplicador_precio ** (
            -self.elasticidad_conversion
        )

    @property
    def churn_suscriptor_efectivo(self) -> float:
        return min(
            0.95,
            self.churn_suscriptor * self.multiplicador_precio ** self.elasticidad_churn,
        )

    @property
    def conversion_de_por_vida(self) -> float:
        """De cada 100 registrados, cuántos llegan alguna vez a pagar. Sale de
        competir la conversión mensual contra la baja del padrón."""
        total = self.conversion_efectiva + self.churn_usuario
        return self.conversion_efectiva / total if total else 0.0

    @property
    def share_pagador(self) -> float:
        """Qué porcentaje del padrón activo está pagando, en estado estable."""
        total = self.conversion_efectiva + self.churn_suscriptor_efectivo
        return self.conversion_efectiva / total if total else 0.0

    def precio(self, codigo: str) -> float:
        return planes.PLANES[codigo].precio_mes * self.multiplicador_precio

    # Cuánto vale un suscriptor por mes, ya neto de comisión.
    def arpu_bruto(self) -> float:
        plus, gold = planes.PLANES["plus"], planes.PLANES["gold"]
        mensual = (1 - self.mezcla_gold) * plus.precio_mes + self.mezcla_gold * gold.precio_mes
        anual = (
            (1 - self.mezcla_gold) * plus.precio_mes_en_anual
            + self.mezcla_gold * gold.precio_mes_en_anual
        )
        base = (1 - self.mezcla_anual) * mensual + self.mezcla_anual * anual
        return base * self.multiplicador_precio

    def comision(self, facturacion_anualizada: float = 0.0) -> float:
        tienda = (
            COMISION_TIENDA_ALTA
            if facturacion_anualizada > UMBRAL_COMISION_ALTA
            else COMISION_TIENDA
        )
        return self.share_tienda * tienda + (1 - self.share_tienda) * COMISION_WEB

    def arpu_neto(self, facturacion_anualizada: float = 0.0) -> float:
        return self.arpu_bruto() * (1 - self.comision(facturacion_anualizada))


ESCENARIOS: list[Escenario] = [
    Escenario(
        codigo="pesimista",
        nombre="Pesimista",
        resumen=(
            "La app funciona pero no engancha: la conversión se queda en el piso "
            "del mercado, el boca a boca no arranca y hay que comprar cada usuario."
        ),
        # Se empieza chico, se sube un poco al ver que no prende, y se sostiene.
        presupuesto=rampa([(3, 200.0), (12, 400.0), (24, 400.0)]),
        cpi=1.60,
        alta_por_instalacion=0.35,
        organicos_base=120.0,
        factor_viral=0.010,
        conversion_mensual=0.006,
        churn_usuario=0.30,
        churn_suscriptor=0.45,
        mezcla_gold=0.20,
        mezcla_anual=0.10,
        share_tienda=0.85,
        horas_propias=60.0,
    ),
    Escenario(
        codigo="base",
        nombre="Base",
        resumen=(
            "El caso realista: se domina una zona chica (un barrio, una ciudad "
            "universitaria), la densidad alcanza para que haya matches y una parte "
            "del crecimiento se vuelve orgánica."
        ),
        presupuesto=rampa([(3, 300.0), (6, 600.0), (12, 1_200.0), (24, 2_000.0)]),
        cpi=1.20,
        alta_por_instalacion=0.45,
        organicos_base=300.0,
        factor_viral=0.025,
        conversion_mensual=0.015,
        churn_usuario=0.22,
        churn_suscriptor=0.32,
        mezcla_gold=0.28,
        mezcla_anual=0.18,
        share_tienda=0.80,
        horas_propias=80.0,
    ),
    Escenario(
        codigo="optimista",
        nombre="Optimista",
        resumen=(
            "El diferencial pega: 'los filtros se respetan y sale una fracción' "
            "se vuelve el argumento de prensa y de boca a boca. Conversión alta "
            "por precio bajo y churn contenido."
        ),
        presupuesto=rampa([(3, 500.0), (6, 1_200.0), (12, 3_000.0), (24, 6_000.0)]),
        cpi=0.90,
        alta_por_instalacion=0.55,
        organicos_base=700.0,
        factor_viral=0.055,
        conversion_mensual=0.022,
        churn_usuario=0.16,
        churn_suscriptor=0.22,
        mezcla_gold=0.35,
        mezcla_anual=0.30,
        share_tienda=0.72,
        horas_propias=120.0,
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# El modelo
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Mes:
    numero: int
    instalaciones: float
    altas: float
    usuarios: float
    suscriptores: float
    nuevos_suscriptores: float
    ingreso_bruto: float
    ingreso_neto: float
    marketing: float
    infra: float
    moderacion: float
    fijos: float
    costo_total: float
    resultado: float                  # antes de impuestos
    impuesto: float = 0.0

    @property
    def resultado_neto(self) -> float:
        return self.resultado - self.impuesto


@dataclass
class Corrida:
    escenario: Escenario
    meses: list[Mes] = field(default_factory=list)

    def acumulado(self, hasta: int) -> float:
        return sum(m.resultado_neto for m in self.meses[:hasta])

    def mes(self, numero: int) -> Mes:
        return self.meses[numero - 1]

    @property
    def punto_de_equilibrio(self) -> int | None:
        """Primer mes con resultado mensual positivo."""
        for m in self.meses:
            if m.resultado_neto > 0:
                return m.numero
        return None

    @property
    def equilibrio_acumulado(self) -> int | None:
        """Primer mes en que se recuperó todo lo invertido."""
        for m in self.meses:
            if self.acumulado(m.numero) > 0:
                return m.numero
        return None


def correr(e: Escenario) -> Corrida:
    usuarios = 0.0
    suscriptores = 0.0
    corrida = Corrida(escenario=e)
    # Resultado fiscal acumulado desde el arranque. Mientras sea negativo hay
    # pérdida para compensar y no se paga IRAE; la ley uruguaya deja
    # arrastrarla hasta 5 años, o sea todo el horizonte de este modelo.
    fiscal_acumulado = 0.0

    for numero in range(1, MESES + 1):
        marketing = e.presupuesto[numero - 1]
        instalaciones = marketing / e.cpi if e.cpi else 0.0
        altas = instalaciones * e.alta_por_instalacion + e.organicos_base + e.factor_viral * usuarios

        usuarios = usuarios * (1 - e.churn_usuario) + altas

        # Los que pagan salen de la base GRATIS activa, no del alta del mes: la
        # suscripción se compra cuando ya te importa quién te dio like.
        libres = max(0.0, usuarios - suscriptores)
        nuevos = libres * e.conversion_efectiva
        suscriptores = min(
            usuarios, suscriptores * (1 - e.churn_suscriptor_efectivo) + nuevos
        )

        bruto = suscriptores * e.arpu_bruto()
        neto = suscriptores * e.arpu_neto(bruto * 12)

        infra = (
            hosting(int(usuarios))
            + usuarios * GB_POR_USUARIO * PRECIO_GB_MES
            + usuarios * GB_TRAFICO_POR_USUARIO_MES * PRECIO_GB_TRAFICO
            + CORREO_TRANSACCIONAL_MES
        )
        moderacion = (
            altas * FOTOS_POR_ALTA * COSTO_MODERACION_AUTOMATICA
            + (altas / ALTAS_POR_HORA_REVISION) * COSTO_HORA_HUMANA
            + (usuarios / USUARIOS_POR_HORA_SOPORTE) * COSTO_HORA_HUMANA
        )
        fijos = CONTADOR_MES + DOMINIO_ANUAL / 12
        if numero == 1:
            fijos += ALTA_GOOGLE_PLAY + CUOTA_APPLE_ANUAL + LEGAL_UNICO
        if numero == 13:
            fijos += CUOTA_APPLE_ANUAL

        costo = marketing + infra + moderacion + fijos
        resultado = neto - costo

        # IRAE, provisionado mes a mes.
        #
        # La primera versión cargaba el impuesto de todo el ejercicio en el mes
        # 12 y en el 24, y eso pintaba de rojo un mes que operativamente estaba
        # en verde: con eso, "¿desde qué mes es rentable?" daba "nunca" en un
        # escenario que ganaba plata todos los meses. El impuesto se devenga
        # con la ganancia, así que se provisiona sobre el incremento de la base
        # gravable — que recién existe cuando el acumulado fiscal se dio vuelta
        # y quedaron compensadas las pérdidas anteriores.
        gravable_antes = max(0.0, fiscal_acumulado)
        fiscal_acumulado += resultado
        impuesto = (max(0.0, fiscal_acumulado) - gravable_antes) * IRAE

        corrida.meses.append(
            Mes(
                numero=numero,
                instalaciones=instalaciones,
                altas=altas,
                usuarios=usuarios,
                suscriptores=suscriptores,
                nuevos_suscriptores=nuevos,
                ingreso_bruto=bruto,
                ingreso_neto=neto,
                marketing=marketing,
                infra=infra,
                moderacion=moderacion,
                fijos=fijos,
                costo_total=costo,
                resultado=resultado,
                impuesto=impuesto,
            )
        )

    return corrida


def suscriptores_para_equilibrio(e: Escenario, mes: Mes) -> float:
    """Cuántos suscriptores hacen falta para cubrir los costos de ESE mes."""
    arpu = e.arpu_neto()
    return mes.costo_total / arpu if arpu else float("inf")


def padron_para_equilibrio(e: Escenario, mes: Mes) -> float:
    """Cuánta gente activa hace falta para que salgan esos suscriptores."""
    objetivo = suscriptores_para_equilibrio(e, mes)
    if not e.conversion_efectiva:
        return float("inf")
    libres = objetivo * e.churn_suscriptor_efectivo / e.conversion_efectiva
    return libres + objetivo


def altas_para_equilibrio(e: Escenario, mes: Mes) -> float:
    """Cuántas altas nuevas por mes hacen falta para sostener ese padrón. En
    estado estable el padrón se mantiene si entra lo mismo que se va:
    altas = padrón × baja mensual del padrón."""
    return padron_para_equilibrio(e, mes) * e.churn_usuario


def ltv(e: Escenario) -> float:
    """Valor de un suscriptor a lo largo de su vida, neto de comisión."""
    if not e.churn_suscriptor_efectivo:
        return float("inf")
    return e.arpu_neto() / e.churn_suscriptor_efectivo


def cac_por_alta(e: Escenario) -> float:
    """Cuánto cuesta un usuario REGISTRADO comprado con pauta."""
    return e.cpi / e.alta_por_instalacion if e.alta_por_instalacion else float("inf")


def cac_por_pagador(e: Escenario) -> float:
    """Cuánto cuesta, con pauta, el usuario comprado que TERMINA pagando.
    No todos los registrados pagan: sólo la fracción de por vida."""
    conv = e.conversion_de_por_vida
    return cac_por_alta(e) / conv if conv else float("inf")


# ─────────────────────────────────────────────────────────────────────────────
# ¿Alcanza con subir el precio?
# ─────────────────────────────────────────────────────────────────────────────

TECHO_MULTIPLICADOR = 12.0
PASO_MULTIPLICADOR = 0.01


def rentable_desde(corrida: Corrida, mes: int) -> bool:
    """Verde en ese mes y en TODOS los que siguen. 'Rentable desde el mes 6'
    no puede significar un mes bueno suelto y después rojo de nuevo."""
    return all(m.resultado_neto >= 0 for m in corrida.meses[mes - 1 :])


def multiplicador_para_rentable_desde(
    e: Escenario, mes: int, techo: float = TECHO_MULTIPLICADOR
) -> float | None:
    """El precio más bajo que deja el negocio en verde a partir de ese mes.

    Se barre en vez de hacer búsqueda binaria a propósito: con elasticidad, la
    curva de resultado contra precio NO es monótona —a partir de cierto punto
    subir el precio espanta más gente de la que compensa— así que una binaria
    puede saltearse la ventana donde sí funciona, o peor, encontrar un punto
    del otro lado del máximo.
    """
    m = 1.0
    while m <= techo + 1e-9:
        if rentable_desde(correr(replace(e, multiplicador_precio=m)), mes):
            return round(m, 2)
        m += PASO_MULTIPLICADOR
    return None


def recorte_pauta_para_rentable_desde(
    e: Escenario, mes: int
) -> float | None:
    """La otra palanca: en vez de cobrar más, gastar menos en pauta. Devuelve
    qué fracción del presupuesto hay que dejar (0,4 = recortar el 60 %)."""
    fraccion = 1.0
    while fraccion >= -1e-9:
        alt = replace(e, presupuesto=[x * fraccion for x in e.presupuesto])
        if rentable_desde(correr(alt), mes):
            return round(fraccion, 2)
        fraccion -= 0.01
    return None


# ─────────────────────────────────────────────────────────────────────────────
# El documento
# ─────────────────────────────────────────────────────────────────────────────


def _u(x: float) -> str:
    """USD con separador de miles a la uruguaya."""
    signo = "-" if x < 0 else ""
    entero = f"{abs(x):,.0f}".replace(",", ".")
    return f"{signo}{entero}"


def _n(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


def _d(x: float, dec: int = 2) -> str:
    """Decimal a la uruguaya: 1.234,56. Mezclar 4.61 con 35,0 % en el mismo
    documento se lee como error de tipeo."""
    entero, _, decimales = f"{x:,.{dec}f}".partition(".")
    entero = entero.replace(",", ".")
    return f"{entero},{decimales}" if decimales else entero


def _pct(x: float) -> str:
    return f"{x * 100:.1f} %".replace(".", ",")


def generar(corridas: list[Corrida]) -> str:
    L: list[str] = []
    a = L.append

    a("# Plan de marketing, inversión y rentabilidad · Matcher")
    a("")
    a("> **Archivo generado.** Sale de `marketing/modelo_negocio.py`.")
    a("> No lo edites a mano: cambiá el supuesto y corré")
    a("> `python3 -m marketing.modelo_negocio`.")
    a("")
    a("---")
    a("")
    a("## Leelo con esto en la cabeza")
    a("")
    a("Esto es un **modelo**, no un pronóstico. Ninguno de los supuestos está")
    a("medido sobre Matcher, porque Matcher todavía no tuvo un usuario real: son")
    a("rangos razonables de mercado para una app de citas chica y sin marca. El")
    a("valor del ejercicio no es el número final, es ver **qué supuesto manda el")
    a("resultado** — y en los tres escenarios es el mismo: el churn del")
    a("suscriptor contra el costo de traer al usuario.")
    a("")
    a("Los precios de la competencia que aparecen en la app")
    a("(`planes.REFERENCIA_COMPETENCIA`) están marcados `verificado: False` y")
    a("acá se aplica el mismo criterio: **verificá antes de publicar una")
    a("campaña que use estos números.**")
    a("")

    # ── Qué se cobra ────────────────────────────────────────────────────────
    plus, gold = planes.PLANES["plus"], planes.PLANES["gold"]
    a("## 1. Qué se cobra, y qué queda")
    a("")
    a("Los precios salen de `matcher/planes.py` — la misma fuente que usa la app.")
    a("")
    a("| Plan | Mensual | Anual | Equivalente mensual del anual |")
    a("|---|---:|---:|---:|")
    for p in (plus, gold):
        a(
            f"| {p.nombre} | USD {_d(p.precio_mes)} | USD {_d(p.precio_anual)} "
            f"| USD {_d(p.precio_mes_en_anual)} |"
        )
    a("")
    a("### La comisión de las tiendas no es negociable")
    a("")
    a("Apple (guía 3.1.1) y Google exigen que una suscripción digital comprada")
    a("**dentro de la app** pase por su cobro. La pasarela propia")
    a("(MercadoPago / dLocal / PayPal) que ya está implementada sólo es válida en")
    a("**la web**. Con el Small Business Program de Apple y el tramo equivalente")
    a("de Google, la comisión es **15 %** mientras la facturación anual del")
    a(f"desarrollador no pase USD {_u(UMBRAL_COMISION_ALTA)}; arriba de eso, **30 %**.")
    a("")
    a("| Plan | Precio | Neto en tienda (15 %) | Neto en tienda (30 %) | Neto en web (5,4 %) |")
    a("|---|---:|---:|---:|---:|")
    for p in (plus, gold):
        a(
            f"| {p.nombre} | USD {_d(p.precio_mes)} "
            f"| USD {_d(p.precio_mes * (1 - COMISION_TIENDA))} "
            f"| USD {_d(p.precio_mes * (1 - COMISION_TIENDA_ALTA))} "
            f"| USD {_d(p.precio_mes * (1 - COMISION_WEB))} |"
        )
    a("")
    a("**Consecuencia comercial directa:** cada suscripción que se logra empujar")
    a("a la web en vez de la tienda deja ~10 puntos más. Por eso el modelo tiene")
    a("un supuesto explícito de qué parte de los pagos pasa por cada canal, y por")
    a("eso conviene que la web tenga su propio embudo de cobro.")
    a("")

    # ── Inversión ───────────────────────────────────────────────────────────
    a("## 2. Inversión: qué hay que pagar sí o sí")
    a("")
    a("### Único, antes de publicar")
    a("")
    a("| Concepto | USD | Nota |")
    a("|---|---:|---|")
    a(f"| Alta de desarrollador en Google Play | {ALTA_GOOGLE_PLAY:.0f} | pago único, de por vida |")
    a(f"| Política de privacidad y términos revisados | {LEGAL_UNICO:.0f} | obligatoria en ambas tiendas |")
    a("| Clave de firma (keystore) | 0 | se genera, pero **si se pierde no se puede volver a publicar la app** |")
    a("| Registro de base de datos ante la URCDP (Uruguay, Ley 18.331) | 0 | trámite, sin arancel |")
    a("| Mac para compilar iOS | 600–1.400 | de segunda mano sirve; **no hay forma de compilar iOS sin eso** |")
    a("")
    a("### Recurrente")
    a("")
    a("| Concepto | USD | Frecuencia |")
    a("|---|---:|---|")
    a(f"| Cuenta Apple Developer | {CUOTA_APPLE_ANUAL:.0f} | por año |")
    a(f"| Dominio | {DOMINIO_ANUAL:.0f} | por año |")
    a("| Backend con disco (Fly.io / Render) | 12 → 900 | por mes, según padrón |")
    a(f"| Correo transaccional | {CORREO_TRANSACCIONAL_MES:.0f} | por mes |")
    a(f"| Contador (unipersonal en Uruguay) | {CONTADOR_MES:.0f} | por mes |")
    a("| Almacenamiento y tráfico de fotos | variable | por mes, ver abajo |")
    a("| Moderación | variable | por mes, **no es opcional** |")
    a("")
    a("### El costo del que nadie habla: moderación")
    a("")
    a("Una app de citas sin moderación de fotos y de chat se llena de abuso en la")
    a("primera semana, y es causal de baja tanto en Play como en App Store. Hoy")
    a("Matcher tiene reportes pero **no tiene revisión** (ver `docs/PUBLICAR.md`).")
    a("El modelo lo cotiza así:")
    a("")
    a(f"- Análisis automático de imagen: USD {_d(COSTO_MODERACION_AUTOMATICA, 4)} por foto, "
      f"{FOTOS_POR_ALTA} fotos por alta.")
    a(f"- Revisión humana de altas y reportes: 1 hora cada {_n(ALTAS_POR_HORA_REVISION)} altas.")
    a(f"- Soporte y denuncias: 1 hora cada {_n(USUARIOS_POR_HORA_SOPORTE)} usuarios activos.")
    a(f"- Hora humana: USD {COSTO_HORA_HUMANA:.0f}.")
    a("")
    a("### Almacenamiento de fotos")
    a("")
    a("Hoy las fotos viajan como data-URI **dentro de la base**. Para usuarios")
    a("reales van a un bucket con URLs firmadas. El modelo cotiza")
    a(f"{_d(GB_POR_USUARIO * 1000, 1)} MB acumulados por usuario a "
      f"USD {_d(PRECIO_GB_MES, 3)}/GB-mes y {_n(GB_TRAFICO_POR_USUARIO_MES * 1000)} MB de "
      f"tráfico por usuario y mes a USD {_d(PRECIO_GB_TRAFICO, 2)}/GB.")
    a("")

    # ── Escenarios: supuestos ───────────────────────────────────────────────
    a("## 3. Los tres escenarios")
    a("")
    for c in corridas:
        a(f"**{c.escenario.nombre}.** {c.escenario.resumen}")
        a("")
    a("| Supuesto | " + " | ".join(c.escenario.nombre for c in corridas) + " |")
    a("|---|" + "---:|" * len(corridas))

    def fila(etiqueta: str, f) -> None:
        a(f"| {etiqueta} | " + " | ".join(f(c.escenario) for c in corridas) + " |")

    fila("Costo por instalación (CPI)", lambda e: f"USD {_d(e.cpi)}")
    fila("Instalaciones que se registran", lambda e: _pct(e.alta_por_instalacion))
    fila("Altas orgánicas base por mes", lambda e: _n(e.organicos_base))
    fila("Altas extra por usuario activo/mes (boca a boca)", lambda e: _d(e.factor_viral, 3))
    fila("Un gratis empieza a pagar (por mes)", lambda e: _pct(e.conversion_efectiva))
    fila("De cada 100 registrados, llegan a pagar", lambda e: _pct(e.conversion_de_por_vida))
    fila("Padrón activo que paga (estado estable)", lambda e: _pct(e.share_pagador))
    fila("Baja mensual del padrón", lambda e: _pct(e.churn_usuario))
    fila("Baja mensual del suscriptor", lambda e: _pct(e.churn_suscriptor_efectivo))
    fila(
        "Vida media del suscriptor",
        lambda e: f"{_d(1 / e.churn_suscriptor_efectivo, 1)} meses",
    )
    fila("Mezcla Gold", lambda e: _pct(e.mezcla_gold))
    fila("Pagan plan anual", lambda e: _pct(e.mezcla_anual))
    fila("Pagos por tienda (vs. web)", lambda e: _pct(e.share_tienda))
    fila("ARPU bruto por suscriptor/mes", lambda e: f"USD {_d(e.arpu_bruto())}")
    fila("ARPU **neto** de comisión", lambda e: f"USD {_d(e.arpu_neto())}")
    fila("LTV del suscriptor", lambda e: f"USD {_d(ltv(e))}")
    fila("CAC por usuario registrado", lambda e: f"USD {_d(cac_por_alta(e))}")
    fila("CAC por **pagador**", lambda e: f"USD {_u(cac_por_pagador(e))}")
    fila("LTV / CAC del pagador", lambda e: _d(ltv(e) / cac_por_pagador(e)))
    a("")
    a("### Lo primero que hay que mirar de esa tabla")
    a("")
    a("La fila **LTV / CAC del pagador**. Es la relación entre lo que deja un")
    a("suscriptor en toda su vida y lo que cuesta conseguirlo comprando pauta.")
    a("Un negocio de suscripción necesita **3 o más**. Acá:")
    a("")
    for c in corridas:
        e = c.escenario
        r = ltv(e) / cac_por_pagador(e)
        veredicto = (
            "la pauta paga sola" if r >= 3
            else "la pauta se banca apenas, sin margen" if r >= 1
            else "**cada usuario comprado pierde plata**"
        )
        a(f"- **{e.nombre}:** {_d(r)} → {veredicto}.")
    a("")
    a("Por eso el presupuesto de pauta de los tres escenarios arranca chico. La")
    a("plata en publicidad no compra un negocio: lo compra el crecimiento")
    a("orgánico, que en el modelo entra por `organicos_base` y `factor_viral`.")
    a("")

    # ── Presupuesto de marketing ────────────────────────────────────────────
    a("## 4. Plan de marketing: en qué se gasta")
    a("")
    a("### La restricción que define todo: la liquidez local")
    a("")
    a("Una app de citas no es un producto que se usa solo — necesita gente del")
    a("otro lado. 5.000 usuarios repartidos por el mundo no sirven; 800 en una")
    a("misma ciudad sí. Y hay un segundo problema conocido del rubro: el padrón")
    a("se inclina 65/35 o 70/30 hacia los hombres, y una app con esa proporción")
    a("deja de funcionar para todos. **La inversión de marketing no se reparte")
    a("por igual: se concentra en un radio chico y sesgada hacia el lado que")
    a("falta.**")
    a("")
    a("### Reparto sugerido del presupuesto mensual")
    a("")
    a("| Partida | % | Para qué |")
    a("|---|---:|---|")
    a("| Pauta geolocalizada (Instagram/TikTok, radio de pocos km) | 40 % | única pauta con sentido: densidad, no alcance |")
    a("| Micro-creadores locales (1k–30k seguidores) | 25 % | costo por instalación mucho menor que la pauta fría |")
    a("| Acciones presenciales (facultades, gimnasios, boliches, ferias) | 20 % | es lo que resuelve la liquidez y el sesgo de género |")
    a("| Prensa y contenido propio (el ángulo 'los filtros se respetan') | 10 % | orgánico, se compone con el tiempo |")
    a("| ASO: capturas, video, palabras clave, traducciones | 5 % | la instalación más barata es la que ya te estaba buscando |")
    a("")
    a("### El mensaje")
    a("")
    a("El producto tiene dos diferenciales reales y son los dos titulares:")
    a("")
    a("1. **Los filtros se respetan.** Es la queja más repetida de las reseñas de")
    a("   las apps grandes: pagar y sentir que el algoritmo igual te muestra")
    a("   cualquier cosa. En Matcher `filtros.py` descarta y `scoring.py` sólo")
    a("   ordena — es una diferencia demostrable, no un eslogan.")
    a("2. **Todos los filtros están en el plan gratis.** La competencia cobra el")
    a("   derecho a filtrar; acá se cobra volumen y visibilidad.")
    a("")
    a("A eso se suman los ganchos de producto: **Crush Time** (adivinar quién te")
    a("dio like entre 4), **cita a ciegas** (las fotos aparecen recién después de")
    a("hablar) y el **radar** con mapa.")
    a("")
    a("### Lo que NO hay que hacer")
    a("")
    a("- Pauta nacional o continental antes de tener una zona chica funcionando:")
    a("  es comprar usuarios que no van a tener con quién hablar.")
    a("- Comparar precios contra la competencia en la campaña sin verificar esos")
    a("  precios primero (`REFERENCIA_COMPETENCIA` está sin verificar a propósito).")
    a("- Prometer cantidad de usuarios o de matches. No se puede sostener.")
    a("")

    # ── Resultados ──────────────────────────────────────────────────────────
    a("## 5. Rentabilidad neta a 3, 6, 9, 12, 18 y 24 meses")
    a("")
    a("«Neto» acá significa: ingreso menos comisión de tienda o pasarela, menos")
    a(f"todos los costos, menos IRAE ({_pct(IRAE)} sobre el resultado del ejercicio,")
    a("compensando pérdidas anteriores como permite la ley uruguaya). **No")
    a("descuenta el trabajo propio** — eso va aparte, al final.")
    a("")
    a("| Escenario | " + " | ".join(f"Mes {m}" for m in CORTES) + " |")
    a("|---|" + "---:|" * len(CORTES))
    for c in corridas:
        celdas = " | ".join(f"USD {_u(c.acumulado(m))}" for m in CORTES)
        a(f"| **{c.escenario.nombre}** (acumulado) | {celdas} |")
    for c in corridas:
        celdas = " | ".join(f"USD {_u(c.mes(m).resultado_neto)}" for m in CORTES)
        a(f"| {c.escenario.nombre} (ese mes) | {celdas} |")
    a("")
    a("| Escenario | Primer mes en verde | Recupera todo lo invertido | Peor pozo |")
    a("|---|---:|---:|---:|")
    for c in corridas:
        pe = c.punto_de_equilibrio
        ea = c.equilibrio_acumulado
        pozo = min(c.acumulado(m.numero) for m in c.meses)
        a(
            f"| **{c.escenario.nombre}** | "
            f"{'mes ' + str(pe) if pe else 'no llega en 24 meses'} | "
            f"{'mes ' + str(ea) if ea else 'no llega en 24 meses'} | "
            f"USD {_u(pozo)} |"
        )
    a("")
    a("Si ves que el acumulado mejora y después vuelve a empeorar, no es un error")
    a("del cálculo: es el escalón de presupuesto del mes 13, cuando la pauta")
    a("aumenta. Cada vez que se sube el gasto de adquisición, el negocio vuelve a")
    a("perder plata hasta que la cohorte comprada madura. Es exactamente el")
    a("motivo por el que subir el presupuesto no es una palanca gratis.")
    a("")

    # ── Detalle por escenario ───────────────────────────────────────────────
    a("## 6. Desglose mes a mes")
    a("")
    for c in corridas:
        e = c.escenario
        a(f"### {e.nombre}")
        a("")
        a(
            "| Mes | Altas | Padrón activo | Suscriptores | Ingreso bruto | "
            "Ingreso neto | Marketing | Infra | Moderación | Fijos | IRAE | "
            "Resultado | Acumulado |"
        )
        a("|---:|" + "---:|" * 12)
        for m in c.meses:
            a(
                f"| {m.numero} | {_n(m.altas)} | {_n(m.usuarios)} | {_n(m.suscriptores)} "
                f"| {_u(m.ingreso_bruto)} | {_u(m.ingreso_neto)} | {_u(m.marketing)} "
                f"| {_u(m.infra)} | {_u(m.moderacion)} | {_u(m.fijos)} "
                f"| {_u(m.impuesto)} | {_u(m.resultado_neto)} | {_u(c.acumulado(m.numero))} |"
            )
        a("")

    # ── Cuántos clientes ────────────────────────────────────────────────────
    a("## 7. Cuántos clientes hacen falta")
    a("")
    a("Dos preguntas distintas, y conviene no mezclarlas:")
    a("")
    a("- **Suscriptores activos**: cuántos tienen que estar pagando ese mes para")
    a("  cubrir los costos de ese mes.")
    a("- **Padrón activo**: cuánta gente usando la app hace falta para que salgan")
    a("  esos suscriptores, dado que sólo una parte paga.")
    a("- **Altas nuevas por mes**: cuántos registros nuevos hacen falta para")
    a("  sostener ese padrón, dado que se va gente todos los meses. En estado")
    a("  estable: `altas = padrón × baja mensual del padrón`.")
    a("")
    for c in corridas:
        e = c.escenario
        a(f"### {e.nombre}")
        a("")
        a(f"ARPU neto: **USD {_d(e.arpu_neto())}** por suscriptor y mes · "
          f"paga el **{_pct(e.share_pagador)}** del padrón · "
          f"baja del suscriptor **{_pct(e.churn_suscriptor_efectivo)}**/mes · "
          f"baja del padrón **{_pct(e.churn_usuario)}**/mes.")
        a("")
        a("| Corte | Costo del mes | Suscriptores necesarios | Los que habría | "
          "Padrón necesario | El que habría | Altas/mes necesarias | Las que habría |")
        a("|---:|---:|---:|---:|---:|---:|---:|---:|")
        for numero in CORTES:
            m = c.mes(numero)
            a(
                f"| Mes {numero} | USD {_u(m.costo_total)} "
                f"| {_n(suscriptores_para_equilibrio(e, m))} | {_n(m.suscriptores)} "
                f"| {_n(padron_para_equilibrio(e, m))} | {_n(m.usuarios)} "
                f"| {_n(altas_para_equilibrio(e, m))} | {_n(m.altas)} |"
            )
        a("")
        a("Y el número que de verdad importa, porque no depende de cuánto se")
        a("gaste en pauta: **cuánto hace falta para cubrir sólo la estructura**,")
        a("si el crecimiento fuera 100 % orgánico.")
        a("")
        m12 = c.mes(12)
        estructura = m12.costo_total - m12.marketing
        s_estructura = estructura / e.arpu_neto()
        p_estructura = (
            s_estructura * e.churn_suscriptor_efectivo / e.conversion_efectiva
            + s_estructura
        )
        a(f"- Costo de estructura en el mes 12, sin un peso de marketing: **USD {_u(estructura)}**.")
        a(f"- Suscriptores necesarios: **{_n(s_estructura)}**.")
        a(f"- Padrón activo necesario: **{_n(p_estructura)}** personas usando la app.")
        a(f"- Altas nuevas por mes para sostenerlo: **{_n(p_estructura * e.churn_usuario)}**.")
        a("")

    # ── Sensibilidad ────────────────────────────────────────────────────────
    a("## 8. Qué mover cambia el resultado (y qué no)")
    a("")
    a("Sensibilidad sobre el escenario Base: se mueve **un solo** supuesto y se")
    a("mira el acumulado a 24 meses.")
    a("")
    base = next(c.escenario for c in corridas if c.escenario.codigo == "base")
    referencia = correr(base).acumulado(24)
    a(f"Acumulado a 24 meses del escenario Base tal cual: **USD {_u(referencia)}**.")
    a("")
    a("| Cambio | Acumulado a 24 meses | Diferencia |")
    a("|---|---:|---:|")
    variaciones = [
        ("Churn del suscriptor −25 % (dura más)", {"churn_suscriptor": base.churn_suscriptor * 0.75}),
        ("Churn del suscriptor +25 % (dura menos)", {"churn_suscriptor": base.churn_suscriptor * 1.25}),
        ("Conversión a pago +50 %", {"conversion_mensual": base.conversion_mensual * 1.5}),
        ("Conversión a pago −50 %", {"conversion_mensual": base.conversion_mensual * 0.5}),
        ("Boca a boca × 2", {"factor_viral": base.factor_viral * 2}),
        ("CPI +50 % (la pauta se encarece)", {"cpi": base.cpi * 1.5}),
        ("Doble presupuesto de pauta", {"presupuesto": [x * 2 for x in base.presupuesto]}),
        ("Cero pauta (sólo orgánico)", {"presupuesto": [0.0] * MESES}),
        ("Todos los pagos por la web (sin comisión de tienda)", {"share_tienda": 0.0}),
        ("Precio × 2 (con su efecto en conversión y churn)", {"multiplicador_precio": 2.0}),
        ("Precio × 4", {"multiplicador_precio": 4.0}),
    ]
    for etiqueta, cambio in variaciones:
        alt = correr(replace(base, **cambio)).acumulado(24)
        a(f"| {etiqueta} | USD {_u(alt)} | {'+' if alt >= referencia else ''}{_u(alt - referencia)} |")
    a("")
    a("### La lectura")
    a("")
    sin_pauta = correr(replace(base, presupuesto=[0.0] * MESES)).acumulado(24)
    doble = correr(replace(base, presupuesto=[x * 2 for x in base.presupuesto])).acumulado(24)
    a("**La fila que hay que leer dos veces es la de cero pauta.** El mismo")
    a("escenario Base, sin gastar un peso en publicidad, termina en")
    a(f"**USD {_u(sin_pauta)}** a 24 meses contra **USD {_u(referencia)}** con la")
    a(f"pauta puesta, y **USD {_u(doble)}** si se duplica. No es una paradoja: a")
    a("este precio, cada usuario comprado cuesta más de lo que va a dejar, así")
    a("que la publicidad no acelera el negocio, lo desangra más rápido.")
    a("")
    a("Lo que sí mueve la aguja es el **churn** y el **boca a boca**: retener, y")
    a("que la gente traiga gente. Eso no se compra con plata — se compra con")
    a("densidad local y con que la app cumpla lo que promete. Que es,")
    a("literalmente, el diferencial del producto.")
    a("")
    a("Y mover los pagos de la tienda a la web es, en plata, equivalente a una")
    a("mejora de conversión: son 10 puntos de comisión sobre cada peso cobrado.")
    a("")

    # ── ¿Subir el precio? ───────────────────────────────────────────────────
    a("## 9. ¿Alcanza con subir el precio para estar en verde desde el mes 6?")
    a("")
    a("La pregunta es buena y el modelo la puede contestar en vez de opinar.")
    a("«Rentable desde el mes 6» se toma en serio: verde ese mes **y todos los")
    a("que siguen**, no un mes bueno suelto.")
    a("")
    a("### Cómo se modela una suba de precio sin hacer trampa")
    a("")
    a("Subir el precio no es gratis y el modelo tiene que decirlo. Cobrar más")
    a("espanta gente antes de que pague (elasticidad de conversión) y hace que el")
    a("que ya paga aguante menos (elasticidad de churn). Un modelo que sube el")
    a("precio dejando la conversión quieta siempre «demuestra» que hay que cobrar")
    a(f"más, y es mentira. Acá se asume elasticidad **{_d(base.elasticidad_conversion, 1)}**:")
    a("al doble de precio, la conversión cae a poco más de la mitad. Menos de 1")
    a("porque Matcher se compara contra una competencia mucho más cara, así que")
    a("aguanta algo de suba antes de que la gente se vaya.")
    a("")
    a("### La respuesta corta: no, y el precio no es el problema")
    a("")
    a("| Escenario | Precio mínimo para estar en verde desde el mes 6 (con la pauta del plan) |")
    a("|---|---|")
    for c in corridas:
        mult = multiplicador_para_rentable_desde(c.escenario, 6)
        if mult is None:
            texto = (
                f"**No se llega**, ni multiplicando el precio por "
                f"{_n(TECHO_MULTIPLICADOR)} (Plus a USD "
                f"{_d(planes.PLANES['plus'].precio_mes * TECHO_MULTIPLICADOR)})"
            )
        else:
            alt = replace(c.escenario, multiplicador_precio=mult)
            texto = f"× {_d(mult)} → Plus USD {_d(alt.precio('plus'))}"
        a(f"| {c.escenario.nombre} | {texto} |")
    a("")
    a("Por qué. En el mes 6 del escenario Base el costo se reparte así:")
    a("")
    m6 = next(c for c in corridas if c.escenario.codigo == "base").mes(6)
    a(f"- Marketing: **USD {_u(m6.marketing)}** de un costo total de USD {_u(m6.costo_total)}.")
    a(f"- Todo lo demás (infra, moderación, fijos): USD {_u(m6.costo_total - m6.marketing)}.")
    a(f"- Ingreso neto de ese mes: USD {_u(m6.ingreso_neto)}, de {_n(m6.suscriptores)} suscriptores.")
    a("")
    a("El agujero del mes 6 **es la pauta**, no el precio. Y subir el precio casi")
    a("no mueve el ingreso, porque lo que se gana por suscriptor se pierde en")
    a("suscriptores:")
    a("")
    a("| Precio Plus | Conversión efectiva | Suscriptores en el mes 6 | Ingreso neto del mes 6 |")
    a("|---:|---:|---:|---:|")
    for mult in (1.0, 1.5, 2.0, 4.0, 8.0, 12.0):
        alt = replace(base, multiplicador_precio=mult)
        mes6 = correr(alt).mes(6)
        a(
            f"| USD {_d(alt.precio('plus'))} | {_pct(alt.conversion_efectiva)} "
            f"| {_n(mes6.suscriptores)} | USD {_u(mes6.ingreso_neto)} |"
        )
    a("")
    a("De USD 3,99 a USD 47,88 el ingreso del mes 6 se mueve una miseria. **No")
    a("hay precio que arregle un mes en el que se gastan USD 600 en publicidad")
    a("para conseguir 60 suscriptores.**")
    a("")
    a("### La respuesta larga: el mes 6 en verde ya es alcanzable, y sin tocar el precio")
    a("")
    a("La palanca que sí funciona es la otra: gastar menos en pauta.")
    a("")
    a("| Escenario | Recorte de pauta para estar en verde desde el mes 6 | Sin pauta: primer mes en verde |")
    a("|---|---|---:|")
    for c in corridas:
        e = c.escenario
        fraccion = recorte_pauta_para_rentable_desde(e, 6)
        recorte = (
            f"recortar **{_pct(1 - fraccion)}**"
            if fraccion is not None
            else "no alcanza ni recortando todo"
        )
        sin = correr(replace(e, presupuesto=[0.0] * MESES))
        primero = next((m.numero for m in sin.meses if rentable_desde(sin, m.numero)), None)
        a(f"| {e.nombre} | {recorte} | {'mes ' + str(primero) if primero else 'nunca'} |")
    a("")
    sin_base = correr(replace(base, presupuesto=[0.0] * MESES))
    primero_base = next(
        (m.numero for m in sin_base.meses if rentable_desde(sin_base, m.numero)), None
    )
    a("**El escenario Base, sin gastar un peso en publicidad, queda en verde")
    a(f"desde el mes {primero_base} y no vuelve a rojo — con el precio de hoy, USD")
    a(f"{_d(planes.PLANES['plus'].precio_mes)}.** Lo que pedís ya se puede, y no")
    a("hace falta cobrar más para conseguirlo: hace falta no comprar usuarios que")
    a("cuestan más de lo que dejan.")
    a("")
    a("### Y si igual querés subir el precio, cuál es el óptimo")
    a("")
    a("Sobre el escenario Base sin pauta, barriendo el precio y quedándose con el")
    a("mejor acumulado a 24 meses:")
    a("")
    a("| Precio Plus | Precio Gold | Suscriptores mes 24 | Acumulado 24 meses |")
    a("|---:|---:|---:|---:|")
    sin = replace(base, presupuesto=[0.0] * MESES)
    for mult in (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 6.0):
        alt = replace(sin, multiplicador_precio=mult)
        c_alt = correr(alt)
        a(
            f"| USD {_d(alt.precio('plus'))} | USD {_d(alt.precio('gold'))} "
            f"| {_n(c_alt.mes(24).suscriptores)} | USD {_u(c_alt.acumulado(24))} |"
        )
    a("")
    mejor_mult, mejor_valor = 1.0, correr(sin).acumulado(24)
    paso = 0.05
    m = 1.0
    while m <= TECHO_MULTIPLICADOR + 1e-9:
        valor = correr(replace(sin, multiplicador_precio=m)).acumulado(24)
        if valor > mejor_valor:
            mejor_mult, mejor_valor = m, valor
        m += paso
    mejor_esc = replace(sin, multiplicador_precio=mejor_mult)
    a(f"El óptimo cae en **× {_d(mejor_mult)}** —Plus a USD")
    a(f"{_d(mejor_esc.precio('plus'))}, Gold a USD {_d(mejor_esc.precio('gold'))}— y")
    a(f"deja USD {_u(mejor_valor)} contra USD {_u(correr(sin).acumulado(24))} sin")
    a(f"tocar nada: **USD {_u(mejor_valor - correr(sin).acumulado(24))} de diferencia")
    a("en dos años.** Nada. La curva es tan chata que el precio, en este rango, es")
    a("casi indiferente para el resultado — y en cambio sí decide con qué")
    a("argumento salís a competir.")
    a("")
    a("### Dónde se da vuelta esta conclusión")
    a("")
    a("Todo esto depende de un número que **no está medido**: la elasticidad. Si")
    a("la gente fuera menos sensible al precio de lo que supone el modelo —cosa")
    a("posible, porque la competencia sale 4 veces más— subir convendría, y mucho:")
    a("")
    a("| Elasticidad supuesta | Precio Plus óptimo | Acumulado 24 meses | Contra USD "
      + _u(correr(sin).acumulado(24)) + " sin tocar |")
    a("|---:|---:|---:|---:|")
    referencia_sin = correr(sin).acumulado(24)
    for el in (0.3, 0.5, 0.8, 1.0, 1.3):
        s = replace(sin, elasticidad_conversion=el)
        mm, mv = 1.0, correr(s).acumulado(24)
        m = 1.0
        while m <= TECHO_MULTIPLICADOR + 1e-9:
            v = correr(replace(s, multiplicador_precio=m)).acumulado(24)
            if v > mv:
                mm, mv = m, v
            m += paso
        # Cuando el óptimo cae en el tope del barrido no es un óptimo, es el
        # borde: hay que decirlo o la tabla se lee como una recomendación de
        # cobrar USD 48 por Matcher Plus.
        tope = " *(tope del barrido)*" if mm >= TECHO_MULTIPLICADOR - paso else ""
        a(
            f"| {_d(el, 1)} | USD {_d(planes.PLANES['plus'].precio_mes * mm)}{tope} "
            f"| USD {_u(mv)} | {'+' if mv >= referencia_sin else ''}{_u(mv - referencia_sin)} |"
        )
    a("")
    a("Las filas marcadas *(tope del barrido)* no son un óptimo sino el borde de")
    a("la búsqueda: con esa elasticidad al modelo le conviene seguir subiendo más")
    a("allá de donde tiene sentido mirar. Léelas como «convendría subir bastante»,")
    a("no como «cobrá USD 48».")
    a("")
    a("O sea: **la respuesta a «¿subo el precio?» depende de un dato que hoy no")
    a("tenés, y que se puede medir.** Un test A/B de precio con usuarios reales")
    a("—mismo producto, dos precios, mirar conversión a 60 días— vale más que")
    a("cualquier cosa que diga esta tabla. Ese test cuesta cero: son dos precios")
    a("en la pantalla de planes.")
    a("")
    a("### Lo que sí conviene hacer con el precio, cueste lo que cueste medirlo")
    a("")
    comp = min(r["precio_mes_aprox"] for r in planes.REFERENCIA_COMPETENCIA)
    a("1. **Empujar el plan anual.** Ya está: cobra por adelantado, elimina el")
    a("   churn mensual y esquiva la comisión si se paga por la web. Es la suba de")
    a("   ingreso por suscriptor más barata que hay, porque no toca el precio de")
    a("   lista.")
    a("2. **Mover pagos de la tienda a la web.** Son 10 puntos de comisión, que a")
    a("   estos volúmenes valen más que cualquier ajuste de precio.")
    a("3. **Si subís, subí poco y de una vez.** Hasta USD 5,99–7,99 el Plus seguís")
    a(f"   abajo de la mitad del más barato de la competencia (USD {_d(comp)} de")
    a("   referencia, sin verificar), así que el argumento comercial se sostiene.")
    a("   Arriba de eso dejás de ser «lo mismo por una fracción» y pasás a competir")
    a("   de igual a igual con marcas que tienen mil veces tu presupuesto.")
    a("")

    # ── Trabajo propio ──────────────────────────────────────────────────────
    a("## 10. El costo que el modelo no cobra: tu tiempo")
    a("")
    a("Ninguno de los números de arriba descuenta el trabajo propio. Si se")
    a("valorizara a USD 15 la hora:")
    a("")
    a("| Escenario | Horas propias/mes | Costo a 24 meses | Acumulado 24m ya descontado |")
    a("|---|---:|---:|---:|")
    for c in corridas:
        e = c.escenario
        costo = e.horas_propias * COSTO_HORA_HUMANA * MESES
        a(
            f"| {e.nombre} | {_n(e.horas_propias)} | USD {_u(costo)} "
            f"| USD {_u(c.acumulado(24) - costo)} |"
        )
    a("")

    # ── Conclusión ──────────────────────────────────────────────────────────
    a("## 11. Conclusión honesta")
    a("")
    ltv_min = min(ltv(c.escenario) for c in corridas)
    ltv_max = max(ltv(c.escenario) for c in corridas)
    a("1. **Con pauta paga, a este precio, el modelo no cierra.** Un suscriptor")
    a(f"   de Matcher deja entre USD {_d(ltv_min)} y USD {_d(ltv_max)} en toda su")
    a("   vida; comprar al pagador que lo genera cuesta más que eso en dos de los")
    a("   tres escenarios. La decisión comercial de ser barato es buena para el")
    a("   usuario y es el diferencial del producto, pero tiene una contracara que")
    a("   conviene mirar de frente: **elimina la publicidad paga como motor de")
    a("   crecimiento**. Con USD 4 de suscripción no se compra un usuario a USD 2")
    a("   y se gana plata; con los USD 16 que cobra Tinder, sí.")
    a("2. **Subir el precio no arregla eso** (sección 9). Con la pauta puesta no")
    a("   hay precio —ni multiplicando por 12— que ponga el mes 6 en verde,")
    a("   porque el agujero de ese mes es la publicidad. Y sin pauta, el mes 6")
    a("   ya está en verde con el precio de hoy. El precio decide con qué")
    a("   argumento salís a competir; el resultado lo decide otra cosa.")
    a("3. **El único camino que cierra es la densidad orgánica.** Una zona chica,")
    a("   presencia real, boca a boca. Es más lento y menos glamoroso que")
    a("   apretar 'aumentar presupuesto', y en este modelo es la diferencia entre")
    a(f"   terminar en USD {_u(sin_pauta)} o en USD {_u(referencia)}.")
    a("4. **Antes de gastar un peso en pauta hay tres cosas sin resolver** y")
    a("   están todas en `docs/PUBLICAR.md`: el backend efímero (las cuentas y")
    a("   las fotos se pierden en cada arranque en frío), la moderación")
    a("   inexistente y las fotos guardadas dentro de la base. Publicitar una app")
    a("   con esos tres problemas quema el dinero y la reputación a la vez: el")
    a("   usuario que se va por una mala primera impresión no vuelve.")
    a("5. **El orden correcto es**: backend con disco → moderación → 200 usuarios")
    a("   reales en un radio de pocos kilómetros → medir conversión y churn de")
    a("   verdad → recién ahí volver a este archivo, reemplazar los supuestos por")
    a("   lo medido y correrlo de nuevo. Ese, y no el número de hoy, es el")
    a("   propósito de este modelo.")
    a("")

    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    destino = Path(argv[0]) if argv else Path("docs/PLAN_NEGOCIO.md")
    corridas = [correr(e) for e in ESCENARIOS]
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(generar(corridas), encoding="utf-8")
    print(f"Escrito {destino}")
    for c in corridas:
        a24 = c.acumulado(24)
        print(f"  {c.escenario.nombre:<11} acumulado 24m: USD {a24:>12,.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
