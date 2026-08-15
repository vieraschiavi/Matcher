"""El modelo de negocio también se testea.

No se testea que el resultado sea un número lindo —es un modelo, el número
depende de supuestos— sino que las cuentas cierren entre sí: que el equilibrio
calculado sea de verdad el equilibrio, que la comisión de tienda se descuente,
que los precios salgan de `matcher.planes` y no estén copiados, y que el
documento no se pueda generar con un supuesto absurdo sin que se note.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from marketing import modelo_negocio as mn
from matcher import planes


@pytest.fixture
def base() -> mn.Escenario:
    return next(e for e in mn.ESCENARIOS if e.codigo == "base")


def test_hay_tres_escenarios_y_uno_se_llama_base():
    codigos = [e.codigo for e in mn.ESCENARIOS]
    assert codigos == ["pesimista", "base", "optimista"]


def test_los_precios_salen_de_planes_y_no_estan_copiados(base):
    """Si alguien cambia el precio en la app, el plan de negocio tiene que
    cambiar solo. Un plan con precios tipeados a mano miente al día siguiente."""
    original = base.arpu_bruto()
    caro = replace(base, mezcla_gold=1.0, mezcla_anual=0.0)
    assert caro.arpu_bruto() == pytest.approx(planes.PLANES["gold"].precio_mes)
    assert original < caro.arpu_bruto()


def test_la_comision_de_tienda_se_descuenta(base):
    assert base.arpu_neto() < base.arpu_bruto()
    solo_web = replace(base, share_tienda=0.0)
    solo_tienda = replace(base, share_tienda=1.0)
    assert solo_web.arpu_neto() > solo_tienda.arpu_neto()
    assert solo_tienda.arpu_neto() == pytest.approx(
        solo_tienda.arpu_bruto() * (1 - mn.COMISION_TIENDA)
    )


def test_arriba_del_millon_la_comision_sube_al_30(base):
    """Apple y Google cobran 15 % hasta USD 1M/año y 30 % arriba. Si el modelo
    se olvida del escalón, un escenario exitoso queda sobrestimado."""
    chico = base.arpu_neto(facturacion_anualizada=100_000)
    grande = base.arpu_neto(facturacion_anualizada=5_000_000)
    assert grande < chico


def test_la_corrida_es_determinista(base):
    a = mn.correr(base)
    b = mn.correr(base)
    assert [m.resultado_neto for m in a.meses] == [m.resultado_neto for m in b.meses]


def test_la_corrida_cubre_los_24_meses_y_los_cortes_pedidos(base):
    corrida = mn.correr(base)
    assert len(corrida.meses) == mn.MESES
    for corte in mn.CORTES:
        assert corrida.mes(corte).numero == corte


def test_sin_marketing_no_hay_instalaciones_pagas(base):
    sin_pauta = replace(base, presupuesto=[0.0] * mn.MESES)
    corrida = mn.correr(sin_pauta)
    assert all(m.instalaciones == 0 for m in corrida.meses)
    # Pero sigue habiendo altas: las orgánicas y el boca a boca.
    assert corrida.mes(12).altas > 0


def test_los_suscriptores_nunca_superan_al_padron(base):
    """Una fuga clásica de estos modelos: la conversión aplicada sobre una base
    que ya está suscripta termina con más pagadores que usuarios."""
    for e in mn.ESCENARIOS:
        for m in mn.correr(e).meses:
            assert m.suscriptores <= m.usuarios + 1e-9


def test_el_equilibrio_calculado_es_de_verdad_el_equilibrio(base):
    """Si el modelo dice que hacen falta N suscriptores para cubrir el mes,
    con N suscriptores el resultado tiene que dar cero."""
    corrida = mn.correr(base)
    for numero in mn.CORTES:
        mes = corrida.mes(numero)
        n = mn.suscriptores_para_equilibrio(base, mes)
        assert n * base.arpu_neto() == pytest.approx(mes.costo_total)


def test_el_padron_de_equilibrio_produce_los_suscriptores_de_equilibrio(base):
    """padrón → suscriptores tiene que ser consistente con la conversión y el
    churn declarados, o la tabla de 'cuántos clientes preciso' miente."""
    corrida = mn.correr(base)
    for numero in mn.CORTES:
        mes = corrida.mes(numero)
        suscriptores = mn.suscriptores_para_equilibrio(base, mes)
        padron = mn.padron_para_equilibrio(base, mes)
        libres = padron - suscriptores
        # En estado estable entran tantos como se van.
        assert libres * base.conversion_mensual == pytest.approx(
            suscriptores * base.churn_suscriptor
        )


def test_las_altas_de_equilibrio_sostienen_el_padron_de_equilibrio(base):
    corrida = mn.correr(base)
    mes = corrida.mes(12)
    padron = mn.padron_para_equilibrio(base, mes)
    altas = mn.altas_para_equilibrio(base, mes)
    assert altas == pytest.approx(padron * base.churn_usuario)


def test_el_ltv_baja_cuando_el_suscriptor_dura_menos(base):
    corto = replace(base, churn_suscriptor=base.churn_suscriptor * 2)
    assert mn.ltv(corto) < mn.ltv(base)


def test_el_cac_del_pagador_es_mayor_que_el_del_registrado(base):
    """No todo el que se registra paga, así que el pagador comprado cuesta
    varias veces lo que cuesta el registro."""
    assert mn.cac_por_pagador(base) > mn.cac_por_alta(base)


def test_gastar_mas_en_pauta_no_arregla_un_ltv_cac_malo(base):
    """La conclusión central del documento, fijada como test: si el pagador
    cuesta más de lo que deja, duplicar el presupuesto empeora el acumulado.
    Si alguien cambia los supuestos y esto deja de valer, que se entere acá y
    no en la conclusión del informe."""
    assert mn.ltv(base) / mn.cac_por_pagador(base) < 1
    normal = mn.correr(base).acumulado(24)
    doble = mn.correr(replace(base, presupuesto=[x * 2 for x in base.presupuesto])).acumulado(24)
    assert doble < normal


def test_el_irae_solo_se_cobra_sobre_ganancia_y_compensa_perdidas(base):
    corrida = mn.correr(base)
    meses_con_impuesto = [m.numero for m in corrida.meses if m.impuesto > 0]
    # El escenario base pierde plata los 24 meses: no puede pagar IRAE.
    assert corrida.acumulado(24) < 0
    assert meses_con_impuesto == []
    # Y el impuesto sólo puede aparecer al cierre del ejercicio.
    for e in mn.ESCENARIOS:
        for m in mn.correr(e).meses:
            assert m.impuesto == 0 or m.numero in (12, 24)


def test_el_hosting_sube_por_escalones():
    assert mn.hosting(10) < mn.hosting(5_000) < mn.hosting(50_000) < mn.hosting(500_000)


def test_el_documento_se_genera_con_las_secciones_pedidas(tmp_path):
    destino = tmp_path / "PLAN.md"
    assert mn.main([str(destino)]) == 0
    texto = destino.read_text(encoding="utf-8")
    for e in mn.ESCENARIOS:
        assert e.nombre in texto
    for corte in mn.CORTES:
        assert f"Mes {corte}" in texto
    assert "Cuántos clientes hacen falta" in texto
    assert "generado" in texto.lower()          # avisa que no se edita a mano


def test_el_documento_avisa_que_son_supuestos_y_no_un_pronostico(tmp_path):
    """Regla 9 del proyecto: nada de promesas que no se pueden sostener. Un
    plan de negocio sin ese aviso se lee como si los números estuvieran
    medidos, y no hay un solo usuario real todavía."""
    destino = tmp_path / "PLAN.md"
    mn.main([str(destino)])
    texto = destino.read_text(encoding="utf-8").lower()
    assert "no un pronóstico" in texto
    assert "ninguno de los supuestos está" in texto


def test_el_documento_no_trae_datos_bancarios(tmp_path):
    """El repo es público. Ningún documento generado puede llevar una cuenta,
    un titular ni un número de cliente: queda indexado para siempre."""
    import re

    destino = tmp_path / "PLAN.md"
    mn.main([str(destino)])
    texto = destino.read_text(encoding="utf-8").lower()
    # Con borde de palabra: "oca" suelto es una cuenta, pero también vive
    # adentro de "dlocal", que sí puede nombrarse.
    for prohibido in ("oca", "iban", "swift", "titular", "cuenta bancaria", "cbu"):
        assert not re.search(rf"\b{re.escape(prohibido)}\b", texto), prohibido
    # Y ningún número largo sin formato, que es la forma de un número de
    # cuenta. Las cifras del informe van con separador de miles (1.000.000),
    # así que no dan falso positivo.
    assert not re.search(r"\b\d{7,}\b", texto)


def test_el_documento_generado_esta_al_dia():
    """Si alguien toca un supuesto y no regenera, el archivo del repo queda
    mintiendo. Este test lo agarra antes del commit."""
    from pathlib import Path

    guardado = Path(__file__).resolve().parent.parent / "docs" / "PLAN_NEGOCIO.md"
    esperado = mn.generar([mn.correr(e) for e in mn.ESCENARIOS])
    assert guardado.read_text(encoding="utf-8") == esperado, (
        "docs/PLAN_NEGOCIO.md quedó desactualizado: "
        "corré `python3 -m marketing.modelo_negocio`"
    )
