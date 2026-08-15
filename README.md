# Matcher

App de citas para web, Android e iOS. Toma lo que funciona de Tinder, Bumble y
Happn, y ataca las dos quejas que más se repiten en sus reseñas:

1. **"Pongo filtros y no los respeta."** Acá el filtro es duro. Si pedís sólo
   hinchas de un equipo, no aparece nadie más — el algoritmo no lo compensa con
   otra afinidad.
2. **"Pago y sigo sin ver a quién quiero ver."** Todos los filtros —edad,
   altura, postura política, equipo de fútbol, distancia— están **completos en
   el plan gratis**. Lo que se paga es volumen y visibilidad.

Plus sale **USD 3,99/mes** y Gold **USD 7,99/mes**, contra los USD 16–30 de los
planes equivalentes de la competencia.

---

## Arrancar en un minuto

```bash
pip install -r requirements-dev.txt
npm run build:web
python3 -m uvicorn webapp.backend.api:app --port 8820
```

Abrí <http://127.0.0.1:8820>. La base de la demo se siembra sola en el primer
arranque (60 perfiles).

### Entrar con Google

Como en el resto de las apps de la categoría, se puede entrar con un proveedor
externo (OAuth 2.0 / OpenID Connect, *authorization code*). El botón aparece
**sólo si está configurado**:

```bash
export GOOGLE_CLIENT_ID=...
export GOOGLE_CLIENT_SECRET=...
export MATCHER_URL_PUBLICA=https://tu-dominio        # detrás de proxy o en el APK
```

En la consola de Google Cloud, la *Authorized redirect URI* tiene que ser
exactamente `https://tu-dominio/api/auth/google/callback`.

La primera vez, después de que Google confirma el email, la app pide lo que
falta (nacimiento, género, ciudad, altura, equipo) en una pantalla aparte: no
se crea un perfil a medias en la base. Si el email ya tiene cuenta, entra
directo a esa cuenta — no se duplica.

Detalles que importan y están implementados: el `state` es obligatorio, de un
solo uso y con vencimiento (CSRF sobre el callback); se exige `email_verified`;
y el `id_token` **no** se lee sin verificar — los datos se piden al endpoint
`userinfo` del proveedor por HTTPS. No hay modo "simulado": sin credenciales,
el botón no existe.

> Si vas a publicar en la App Store con login social, Apple exige ofrecer
> también *Sign in with Apple*. La estructura de `matcher/oauth.py` está hecha
> para sumar proveedores (es un `dataclass` por proveedor), pero hoy sólo está
> Google.

### Cuentas de prueba

Dos cuentas con **Gold vigente, verificadas y sin límites**, para probar todo:

| Email | Contraseña |
|---|---|
| `vieraschiavi@gmail.com` | `matcher2026` |
| `arcortito@gmail.com` | `matcher2026` |

En la pantalla de entrada hay un botón por cada una. La contraseña se cambia
con `MATCHER_DEMO_CLAVE`.

---

## Qué hace

**Descubrir.** Deck de tarjetas a pantalla completa. Deslizás (o usás los
botones): derecha es like, izquierda es pasar, **arriba es superfan**. Cada
tarjeta muestra el carrusel de fotos y videos, el % de compatibilidad y **por
qué** apareció esa persona ("los dos de Peñarol", "en común: cine, mate").

**Filtros.** Género, rango de edad, **rango de altura**, **postura política**
(izquierda / derecha / neutro), **equipo de fútbol del país donde estás**,
radio en km, sólo mi país, sólo verificados, intereses. Cuando el deck queda
vacío, la app dice **qué filtro** lo vació y cuántos perfiles descartó cada uno,
en vez de mostrar una pantalla en blanco.

**Match automático.** Empareja sólo cuando los dos se pasan *todos* los filtros
del otro y la compatibilidad supera el 72%. Si nadie califica, no propone nada
— bajar el umbral para llenar la bandeja es mentir sobre el porcentaje. Los
matches automáticos se muestran marcados: nadie deslizó, y se dice.

**Más votados.** Ranking por tasa de likes suavizada (no por total): un perfil
con 3 likes en 4 vistas no le gana a uno con 300 en 1.200. El superfan vale por
tres likes.

**Perfil.** Hasta **10 fotos y 2 videos** de 30 segundos. La primera foto es la
portada y se cambia tocándola.

**Chat.** Conversación por match, con no leídos, y deshacer match.

**Planes y pagos.** Free / Plus / Gold, mensual o anual, con checkout,
confirmación idempotente, historial y cancelación que respeta lo ya pagado.

---

## Cómo está armado

```
matcher/            motor, sólo biblioteca estándar
  geo.py            países, ciudades, distancia y equipos de fútbol por país
  modelos.py        Perfil, Preferencias, Media, Match, Mensaje
  filtros.py        filtros duros + diagnóstico de deck vacío
  scoring.py        compatibilidad, popularidad y orden del deck
  automatch.py      match automático
  planes.py         planes, límites y precios
  pagos.py          checkout, confirmación, cancelación
  medios.py         reglas de 10 fotos / 2 videos
  almacen.py        SQLite + interacciones, matches y chat
  oauth.py          login con proveedor externo (Google)
  fotos.py          de dónde salen las fotos de la demo
  avatares.py       retratos ilustrados generados (fallback sin archivos)
  demo.py           semilla determinista
webapp/backend/     API FastAPI
webapp/frontend/    React + Vite (misma app para web, Android e iOS)
assets/personas/    pack de rostros sintéticos de la demo
tests/              142 tests
```

El motor no depende del backend: el algoritmo completo corre desde un test o
desde un script sin levantar servidor.

---

## Las fotos de la demo

El pack incluido son **96 rostros sintéticos** generados con StyleGAN. **No son
personas que existan.** Se descargaron 112 y se descartaron 16 a mano por
leerse como menores de edad — la app es 18+ y eso vale también para un perfil
de demostración.

No hay ni debe haber fotografías de personas reales en el seed: un perfil de
citas con la cara de alguien que no dio su consentimiento es una identidad
falsa, y la licencia comercial de un banco de imágenes cubre publicidad, no
eso. Detalles y procedencia en [`assets/personas/LEEME.md`](assets/personas/LEEME.md).

Para usar otras fotos —las tuyas, las de un pack con licencia, las de usuarios
reales— no hace falta tocar código:

```bash
MATCHER_FOTOS=/ruta/a/mis/fotos python3 -m matcher.demo datos/matcher.db
```

La carpeta acepta subcarpetas `mujer/`, `hombre/`, `no_binario/` o imágenes
sueltas. Con `MATCHER_FOTOS=ninguna` la demo usa retratos ilustrados generados
por código, sin ningún archivo.

---

## Android e iOS

La misma app React se empaqueta con Capacitor. El CSS es uno solo: por debajo
de 860 px la barra lateral pasa a barra inferior.

```bash
npm install
npm run init:android      # una sola vez
npm run apk:debug         # necesita ANDROID_HOME

npm run init:ios          # una sola vez, en macOS
npm run ios:abrir         # abre Xcode
```

Los proyectos nativos (`android/`, `ios/`) están en `.gitignore` a propósito:
commitearlos ata el repo a una versión del SDK.

---

## Pagos

`matcher/pagos.py` trae el flujo completo (catálogo → checkout → confirmación →
alta del plan → historial) con una pasarela `demo` que confirma en el acto,
para poder probar la app de punta a punta sin cuentas de comercio. **No mueve
plata y la UI lo dice.**

Para enchufar una pasarela real, implementá `Pasarela` y devolvé la URL de
checkout del proveedor; el resto del sistema no cambia:

```bash
MATCHER_PASARELA=stripe STRIPE_API_KEY=... python3 -m uvicorn webapp.backend.api:app
```

Antes de cobrarle a alguien de verdad falta: verificar la firma del webhook,
usar el id de la transacción como clave de idempotencia, y facturación e
impuestos por país. Está anotado en el módulo.

---

## Desarrollo

```bash
python3 -m pytest -q tests/     # 142 tests
ruff check .
```

Para probar el frontend de verdad (no sólo los tests), con el backend
levantado:

```js
const { chromium } = require("playwright");
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 390, height: 844 } });
await p.goto("http://127.0.0.1:8820");
await p.getByRole("button", { name: /vieraschiavi/ }).click();
await p.waitForSelector(".carta");
await p.screenshot({ path: "deck.png" });
```

### Variables de entorno

| Variable | Default | Para qué |
|---|---|---|
| `MATCHER_BD` | `datos/matcher.db` | Ruta de la base |
| `MATCHER_SECRETO` | — | Clave para firmar las sesiones. **Obligatoria en serverless** (ver abajo) |
| `MATCHER_DEMO` | `1` | Sembrar la demo al arrancar |
| `MATCHER_DEMO_CLAVE` | `matcher2026` | Contraseña de las cuentas de prueba |
| `MATCHER_FOTOS` | pack incluido | Carpeta de fotos, o `ninguna` |
| `MATCHER_PASARELA` | `demo` | `demo` o `stripe` |
| `MATCHER_PUERTO` | `8820` | Puerto del backend |
| `MATCHER_URL_PUBLICA` | la del request | URL pública, para el `redirect_uri` de OAuth |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | — | Habilitan "Continuar con Google" |
| `FACEBOOK_APP_ID` / `FACEBOOK_APP_SECRET` | — | Habilitan "Continuar con Facebook" |

#### `MATCHER_SECRETO`: por qué no es opcional en Vercel

Cada instancia serverless tiene su propio disco efímero y, por lo tanto, su
propia base. Con la sesión guardada sólo en la tabla `sesiones`, el token que
emite una instancia no existe en la de al lado: medimos **10 de 24 pedidos en
paralelo devolviendo 401**, y a los 90 segundos la sesión moría del todo. En
la app no se veía un error, se veía "Cargando…" para siempre.

La sesión va firmada con HMAC-SHA256 sobre `MATCHER_SECRETO`, así que
cualquier instancia la valida sin compartir estado. **Sin la variable cada
proceso firma con una clave al azar** y vuelve el problema — no hay un valor
por defecto fijo a propósito: un secreto cableado en un repo público deja que
cualquiera se firme una sesión ajena.

Para verificar que quedó puesta, `GET /api/salud` devuelve
`"sesiones_compartidas": true`.

Ojo con lo que **no** arregla: la sesión sobrevive, los DATOS no. Ver abajo.

### Vercel no sirve para usuarios reales (medido)

En serverless la base vive en `/tmp`, que es efímero **y distinto en cada
instancia**. Con una cuenta recién creada y su foto subida:

```
40 pedidos en paralelo → 25 × 401 "sesión inválida", 15 × 200
```

La firma del token era válida; lo que faltaba era el **perfil**. Cada instancia
resiembra la demo desde cero, y una cuenta real no está en la semilla. Por eso
las cuentas demo funcionan (salen del seed determinista) y una cuenta propia
se cae, y por eso las fotos subidas "desaparecen".

Esto **no se arregla del lado de la sesión**: necesita disco compartido. El
backend lo detecta (`almacenamiento_efimero()`), lo reporta en `/api/salud` y
la pantalla de alta avisa antes de dejar crear una cuenta que se va a perder.

Para usuarios de verdad hay un `Dockerfile` con `fly.toml` y `render.yaml`
listos: el motor es el mismo, sólo cambia dónde apunta `MATCHER_BD`. En Fly:

```
fly launch --no-deploy --copy-config --name matcher
fly volumes create datos --size 1 --region gru
fly secrets set MATCHER_SECRETO=$(python3 -c "import secrets;print(secrets.token_urlsafe(48))")
fly deploy
```

Lo que no puede faltar en ningún host es el **volumen montado**: sin eso se
repite el problema de Vercel con otro nombre.

---

## Estado

Es un **MVP funcional y testeado**, no un producto en producción. Lo que falta
antes de abrirlo a usuarios reales:

- Verificación de identidad real (hoy `verificado` es un flag).
- Moderación de fotos y de chat (hay reportes, no hay revisión).
- Storage de objetos para las fotos: hoy viajan como data-URI dentro de la base,
  que alcanza para la demo y no para escalar.
- Notificaciones push y chat en tiempo real (hoy el chat es por request).
- Migrar el hash de contraseñas a argon2id (hoy PBKDF2, 260k iteraciones).
- Pasarela de pago real, con webhooks verificados.
