# Matcher en un host con disco de verdad.
#
# Existe por un problema medido, no por gusto: en Vercel la base vive en /tmp,
# que es efímero Y distinto en cada instancia. Con una cuenta recién creada, de
# 40 pedidos en paralelo 25 volvieron 401 — el perfil no estaba en la instancia
# que atendió. Las fotos subidas "desaparecen" por lo mismo.
#
# Acá el motor es el de siempre y la única diferencia es dónde apunta
# MATCHER_BD: a un volumen montado. No hay una segunda implementación del
# backend, es la misma imagen que corre local.

FROM python:3.11-slim AS frontend
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/*
COPY package.json package-lock.json ./
COPY webapp/frontend/package.json webapp/frontend/
# La URL de la API se compila adentro del bundle. Vacía = mismo origen, que es
# lo correcto acá: este contenedor sirve la web Y la API en un solo puerto.
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL
COPY webapp/frontend webapp/frontend
RUN cd webapp/frontend && npm install && npm run build

FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY requirements-dev.txt ./
# Sólo lo que hace falta para servir. El motor es biblioteca estándar; esto es
# el servidor HTTP y nada más.
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" pydantic

COPY matcher matcher
COPY webapp/backend webapp/backend
COPY assets assets
COPY --from=frontend /app/webapp/frontend/dist webapp/frontend/dist

# El volumen se monta acá. Si el host no monta nada, la base igual se crea —
# pero se pierde al recrear el contenedor, así que MONTALO.
RUN mkdir -p /datos
ENV MATCHER_BD=/datos/matcher.db \
    MATCHER_EFIMERO=0 \
    MATCHER_PUERTO=8080
EXPOSE 8080

# Sin MATCHER_SECRETO las sesiones se caen entre reinicios: se define en el
# panel del host, nunca en la imagen.
#
# EL PUERTO SE LEE DE `PORT` PRIMERO, y no es un detalle: Railway, Render y
# Heroku asignan el puerto por su cuenta y lo pasan en esa variable. Un
# contenedor que escucha en 8080 fijo mientras el host rutea a otro puerto pasa
# el build, arranca, y falla el healthcheck — o sea que se ve como "la app está
# rota" cuando en realidad nadie le está hablando al puerto donde escucha.
# `MATCHER_PUERTO` queda de respaldo para correr esto a mano.
CMD ["sh", "-c", "python3 -m uvicorn webapp.backend.api:app --host 0.0.0.0 --port ${PORT:-${MATCHER_PUERTO:-8080}}"]
