"""Las consultas de la ruta caliente no pueden barrer la tabla entera.

POR QUÉ ESTE ARCHIVO

`matches` y `pagos` crecen con el uso y no paran. Tres consultas hacían SCAN de
la tabla completa, medido con 40.000 filas:

    pago por referencia (lo hace CADA webhook)   1,637 ms -> 0,003 ms   565x
    mis matches (se abre al entrar a la app)     2,405 ms -> 0,157 ms    15x
    mis pagos                                    1,564 ms -> 0,117 ms    13x

Un test que mida MILISEGUNDOS es un test que falla solo el día que la máquina
del CI está ocupada. Por eso acá se mira el PLAN de ejecución, que es
determinista: si SQLite dice SCAN sobre estas tablas, el índice se perdió.

Nota sobre `matches`: la tabla ya tenía `UNIQUE(a_id, b_id)`, que cubre el lado
`a_id`. El que faltaba era el lado `b_id` del `OR` — y "mis matches" pregunta
por los dos.
"""

from __future__ import annotations

import pytest


def plan(almacen, sql, args) -> str:
    return " ".join(r[-1] for r in almacen.con.execute("EXPLAIN QUERY PLAN " + sql, args))


@pytest.mark.parametrize(
    "nombre,sql,args",
    [
        (
            "mis matches",
            "SELECT * FROM matches WHERE a_id = ? OR b_id = ?",
            ("u1", "u1"),
        ),
        (
            "pago por referencia (webhook)",
            "SELECT * FROM pagos WHERE referencia = ?",
            ("ref1",),
        ),
        (
            "mis pagos",
            "SELECT * FROM pagos WHERE usuario_id = ? ORDER BY momento DESC",
            ("u1",),
        ),
    ],
)
def test_no_barre_la_tabla_entera(almacen, nombre, sql, args):
    p = plan(almacen, sql, args)
    assert "SCAN" not in p, f"{nombre} lee la tabla entera: {p}"
    assert "USING INDEX" in p or "USING COVERING INDEX" in p, p


def test_estan_los_indices_que_faltaban(almacen):
    """Por nombre, para que borrar uno se note acá y no en producción."""
    nombres = {
        f[1]
        for tabla in ("matches", "pagos")
        for f in almacen.con.execute(f"PRAGMA index_list({tabla})")
    }
    for ix in ("ix_match_b", "ix_pago_ref", "ix_pago_usuario"):
        assert ix in nombres, f"falta el índice {ix}"
