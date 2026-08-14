"""Planes, precios y el flujo de pago."""

from datetime import datetime, timedelta

import pytest

from matcher import pagos, planes
from matcher.modelos import DatosInvalidos


def test_todos_los_filtros_estan_en_el_plan_gratis():
    """Es LA decisión de producto de Matcher: se cobra volumen y visibilidad,
    no el derecho a filtrar. Si alguien mueve esto, que sea a propósito."""
    assert planes.PLANES["gratis"].limites.filtros_avanzados is None


def test_el_plan_gratis_permite_las_10_fotos_y_2_videos():
    for codigo in planes.PLANES:
        assert planes.PLANES[codigo].limites.fotos == 10
        assert planes.PLANES[codigo].limites.videos == 2


def test_somos_mas_baratos_que_la_referencia_de_la_competencia():
    mas_barato_ajeno = min(c["precio_mes_aprox"] for c in planes.REFERENCIA_COMPETENCIA)
    assert planes.PLANES["gold"].precio_mes < mas_barato_ajeno
    assert planes.PLANES["plus"].precio_mes < mas_barato_ajeno


def test_la_referencia_de_precios_ajenos_esta_marcada_como_no_verificada():
    """Son precios de lista que cambian por país y promoción. Publicarlos como
    dato duro es una promesa que no podemos sostener."""
    assert all(c["verificado"] is False for c in planes.REFERENCIA_COMPETENCIA)
    assert "verificalos" in planes.catalogo()["aviso_referencia"].lower()


def test_el_anual_conviene_frente_al_mensual():
    for codigo in ("plus", "gold"):
        p = planes.PLANES[codigo]
        assert p.precio_mes_en_anual < p.precio_mes


def test_los_limites_crecen_con_el_plan():
    g, p, o = (planes.PLANES[c].limites for c in ("gratis", "plus", "gold"))
    assert g.likes_por_dia is not None and p.likes_por_dia is None and o.likes_por_dia is None
    assert g.superfans_por_semana < p.superfans_por_semana < o.superfans_por_semana
    assert g.automatch_por_dia < p.automatch_por_dia < o.automatch_por_dia
    assert not g.ver_quien_me_dio_like and p.ver_quien_me_dio_like and o.ver_quien_me_dio_like


def test_precio_rechaza_plan_y_periodo_invalidos():
    with pytest.raises(DatosInvalidos, match="periodo"):
        pagos.precio("plus", "semanal")
    with pytest.raises(DatosInvalidos, match="no comprable"):
        pagos.precio("gratis", "mensual")


def test_flujo_de_pago_completo(almacen, hacer_perfil):
    p = hacer_perfil()
    almacen.crear_perfil(p, "clave-larga-1")
    assert p.es_premium is False

    checkout = pagos.iniciar(almacen, p, "plus", "mensual")
    assert checkout.monto == planes.PLANES["plus"].precio_mes
    assert checkout.estado == "pendiente"
    assert almacen.pagos_de(p.id)[0]["estado"] == "pendiente"

    r = pagos.confirmar(almacen, p, checkout.id)
    assert r["ya_confirmado"] is False
    assert r["plan"] == "plus"
    guardado = almacen.perfil(p.id)
    assert guardado.plan == "plus"
    assert guardado.es_premium is True
    assert almacen.pagos_de(p.id)[0]["estado"] == "pagado"


def test_confirmar_dos_veces_no_duplica_el_plazo(almacen, hacer_perfil):
    """El reintento del webhook es la norma, no la excepción: sin idempotencia
    un mes pagado se convierte en tres."""
    p = hacer_perfil()
    almacen.crear_perfil(p, "clave-larga-1")
    checkout = pagos.iniciar(almacen, p, "plus", "mensual")
    pagos.confirmar(almacen, p, checkout.id)
    vence = p.plan_vence
    segunda = pagos.confirmar(almacen, p, checkout.id)
    assert segunda["ya_confirmado"] is True
    assert p.plan_vence == vence


def test_renovar_suma_al_vencimiento_vigente(almacen, hacer_perfil):
    p = hacer_perfil(plan="plus", plan_vence=datetime.utcnow() + timedelta(days=20))
    almacen.crear_perfil(p, "clave-larga-1")
    antes = p.plan_vence
    checkout = pagos.iniciar(almacen, p, "plus", "mensual")
    pagos.confirmar(almacen, p, checkout.id)
    # No se pisa: quedan los 20 días que faltaban + 30 nuevos.
    assert p.plan_vence > antes + timedelta(days=25)


def test_confirmar_una_referencia_inexistente_falla(almacen, hacer_perfil):
    p = hacer_perfil()
    almacen.crear_perfil(p, "clave-larga-1")
    with pytest.raises(DatosInvalidos, match="no existe ese pago"):
        pagos.confirmar(almacen, p, "no-existe")


def test_cancelar_respeta_lo_ya_pagado(almacen, hacer_perfil):
    p = hacer_perfil()
    almacen.crear_perfil(p, "clave-larga-1")
    checkout = pagos.iniciar(almacen, p, "gold", "anual")
    pagos.confirmar(almacen, p, checkout.id)
    r = pagos.cancelar(almacen, p)
    assert r["cancelado"] is True
    assert r["acceso_hasta"] is not None
    # Sigue siendo premium hasta el vencimiento: cortar el acceso al instante
    # es la razón número uno de los contracargos.
    assert almacen.perfil(p.id).es_premium is True


def test_la_pasarela_demo_es_la_del_entorno_de_prueba():
    p = pagos.pasarela_activa()
    assert p.nombre == "demo"
