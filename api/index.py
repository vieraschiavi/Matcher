"""Matcher · punto de entrada serverless (Vercel).

Mismo patrón que MV Cliente IA: Vercel publica cualquier archivo de `api/`
como función y detecta el objeto ASGI `app`, así que se reexporta el MISMO
FastAPI que usan la web y el APK. No hay una segunda implementación del
backend que se pueda desincronizar.

La base va a `/tmp` (único directorio escribible en serverless) y es
**efímera**: cada instancia fría arranca de cero y se resiembra la demo. Para
una demo alcanza; para usuarios reales el backend se lleva a un servidor con
disco (Railway, Fly, un VPS) cambiando MATCHER_BD, sin tocar código.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# Antes de importar el backend: en Vercel el repo es de sólo lectura y el
# default (datos/matcher.db) reventaría al crear la carpeta.
os.environ.setdefault("MATCHER_BD", "/tmp/matcher.db")

from webapp.backend.api import app  # noqa: E402

__all__ = ["app"]
