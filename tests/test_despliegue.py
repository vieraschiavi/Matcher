"""Que el contenedor arranque donde lo van a desplegar.

POR QUÉ ESTE ARCHIVO

Un Dockerfile que compila no es un Dockerfile que sirve. La clase de error que
se atrapa acá no rompe el build ni los tests: rompe el DESPLIEGUE, y se ve como
"la app está rota" cuando en realidad arrancó bien y nadie le está hablando al
puerto donde escucha.

El caso concreto: Railway, Render y Heroku asignan el puerto y lo pasan en
`PORT`. El `CMD` leía sólo `MATCHER_PUERTO`, así que el contenedor escuchaba en
8080 fijo mientras el host ruteaba a otro lado. Build verde, healthcheck en
rojo, y a debuggear una hora.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
DOCKERFILE = RAIZ / "Dockerfile"
RAILWAY = RAIZ / "railway.json"


def test_el_contenedor_escucha_donde_le_dice_el_host():
    """`PORT` PRIMERO. Es lo que inyectan Railway, Render y Heroku."""
    cmd = [ln for ln in DOCKERFILE.read_text(encoding="utf-8").splitlines()
           if ln.startswith("CMD")]
    assert cmd, "el Dockerfile no tiene CMD"
    assert "${PORT:-" in cmd[0], (
        "el contenedor no lee $PORT: arranca bien y el host rutea a otro "
        f"puerto, así que el healthcheck falla igual.\n{cmd[0]}"
    )


def test_la_base_no_vive_en_un_disco_que_se_borra():
    """Todo el punto de mover el backend fuera de serverless. Si `MATCHER_BD`
    apunta a `/tmp`, se pierden las cuentas Y los pagos."""
    texto = DOCKERFILE.read_text(encoding="utf-8")
    assert "MATCHER_BD=/datos/matcher.db" in texto
    assert "MATCHER_BD=/tmp" not in texto
    assert "mkdir -p /datos" in texto, "no crea el punto de montaje del volumen"


def test_el_healthcheck_apunta_a_una_ruta_que_existe():
    """Un healthcheck contra una ruta inexistente deja el deploy reiniciándose
    para siempre, sin decir por qué."""
    cfg = json.loads(RAILWAY.read_text(encoding="utf-8"))
    ruta = cfg["deploy"]["healthcheckPath"]
    api = (RAIZ / "webapp" / "backend" / "api.py").read_text(encoding="utf-8")
    assert f'"{ruta}"' in api, f"{ruta} no está definida en la API"


def test_el_secreto_no_viaja_en_la_imagen():
    """Un secreto horneado en la imagen se filtra con la imagen. Va en el panel
    del host."""
    texto = DOCKERFILE.read_text(encoding="utf-8")
    for prohibida in ("MATCHER_SECRETO=", "RESEND_API_KEY=", "MERCADOPAGO_ACCESS_TOKEN="):
        for linea in texto.splitlines():
            if prohibida in linea and not linea.strip().startswith("#"):
                pytest.fail(f"el Dockerfile hornea un secreto: {linea.strip()}")


def test_railway_usa_el_dockerfile_y_no_adivina():
    """Sin `builder: DOCKERFILE`, Railway autodetecta — y este repo tiene
    package.json en la raíz (Capacitor), así que lo tomaría por proyecto Node y
    desplegaría cualquier cosa menos el backend."""
    cfg = json.loads(RAILWAY.read_text(encoding="utf-8"))
    assert cfg["build"]["builder"] == "DOCKERFILE"
    assert cfg["build"]["dockerfilePath"] == "Dockerfile"
