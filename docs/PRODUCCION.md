# Matcher en producción · guía definitiva

Los tres trámites que dependen de vos, en el orden en que hay que hacerlos.
El orden importa: el dominio de Railway define las URLs que hay que registrar
en Google y Facebook, así que hacerlo al revés obliga a rehacer las
credenciales.

> Lo que ya está resuelto en el repo tiene ✅. Lo que necesita una cuenta tuya
> tiene ❌ y está explicado paso a paso.

---

## 1. Railway · el backend con disco

### Por qué

Hoy el backend corre en Vercel, donde la base vive en `/tmp`: **efímero y
distinto en cada instancia**. Medido: con una cuenta recién creada, de 40
pedidos en paralelo 25 devolvieron 401 porque el perfil no estaba en la
instancia que atendió. Por eso las cuentas y las fotos "desaparecen".

Railway monta un volumen de verdad. Verificado localmente con las mismas
variables: se crea una cuenta con foto, se reinicia el servidor entero, y la
cuenta, la foto **y la sesión abierta** siguen ahí.

### Pasos

1. Entrá a [railway.com](https://railway.com) con la cuenta de GitHub.
2. **New Project → Deploy from GitHub repo → `vieraschiavi/Matcher`**, rama
   `claude/dating-app-mvp-h38hie`. Railway lee `railway.json` y usa el
   `Dockerfile` que ya está en el repo.
3. **Volumen** (este es EL paso, sin esto no sirve de nada):
   servicio → pestaña **Variables** → **+ New Volume** → punto de montaje
   `/datos`, 1 GB alcanza para arrancar.
4. **Variables** del servicio:

   | Variable | Valor | Para qué |
   |---|---|---|
   | `MATCHER_BD` | `/datos/matcher.db` | la base va al volumen, no al contenedor |
   | `MATCHER_EFIMERO` | `0` | apaga el cartel de "se borran los datos" |
   | `MATCHER_SECRETO` | 48 caracteres al azar | firma las sesiones; si cambia, se cierran todas |
   | `MATCHER_DEMO` | `1` mientras probás, `0` con gente real | siembra los 60 perfiles sintéticos |
   | `MATCHER_URL_PUBLICA` | la URL del paso 5 | sin esto el login externo falla |
   | `PORT` | lo pone Railway solo | — |

   Para el secreto:

   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

5. **Dominio**: Settings → Networking → **Generate Domain**. Queda algo como
   `matcher-production-xxxx.up.railway.app`. Copialo y ponelo en
   `MATCHER_URL_PUBLICA` (paso 4). Redesplegá.
6. **Verificá**, no lo des por hecho:

   ```bash
   curl -s https://TU-DOMINIO/api/salud
   ```

   Tiene que decir `"almacenamiento_efimero": false` y
   `"sesiones_compartidas": true`. Si dice `true` en el primero, el volumen no
   está montado y estás igual que en Vercel.

### Costo

Railway no tiene plan gratis permanente: son **USD 5/mes** de plan Hobby, que
incluyen USD 5 de consumo. Para el tamaño de Matcher con pocos usuarios, el
consumo entra dentro de esos USD 5.

---

## 2. Google y Facebook · el login sin llenar formularios

### Lo que había que arreglar antes, y ya está ✅

El botón existía pero en el APK **no podía funcionar**, por dos motivos
apilados:

1. **Google rechaza el WebView.** Cuando detecta un navegador embebido devuelve
   `disallowed_useragent` y ni muestra la pantalla de login. Es política suya
   para todas las apps nativas.
2. **El token caía en el origen equivocado.** El callback devolvía el navegador
   a la web del backend; la app vive en `https://localhost`, así que el
   `localStorage` donde llegaba el token no era el de la app.

Ahora la app abre el navegador **del sistema** (Chrome Custom Tab / Safari) y
el backend vuelve por un enlace profundo `com.matcher.app://auth/...` que el
sistema operativo enruta a la app. Está en `webapp/frontend/src/loginNativo.js`,
`matcher/oauth.py`, el `intent-filter` del `AndroidManifest.xml` y el
`CFBundleURLTypes` del `Info.plist`. Hay tests, incluido uno que verifica que
el destino no se pueda usar como open redirect.

### Google ❌

1. [console.cloud.google.com](https://console.cloud.google.com) → crear un
   proyecto (o usar uno existente).
2. **APIs y servicios → Pantalla de consentimiento de OAuth**:
   - Tipo: **Externo**.
   - Nombre de la app, tu email de soporte, tu email de contacto.
   - **Dominios autorizados**: `up.railway.app` (o tu dominio propio).
   - Ámbitos: alcanza con `email`, `profile`, `openid` — no pidas más, cada
     ámbito extra suma revisión.
   - Mientras esté en "Testing" sólo entran los emails que agregues como
     usuarios de prueba. Para abrirlo a cualquiera hay que **publicar** la app,
     y con estos tres ámbitos básicos **no requiere verificación de Google**.
3. **Credenciales → Crear credenciales → ID de cliente de OAuth**:
   - Tipo: **Aplicación web** (sí, web: el `client_secret` vive en el backend,
     no en el teléfono — es lo correcto y lo más seguro).
   - **URI de redireccionamiento autorizados**, exactamente:
     ```
     https://TU-DOMINIO/api/auth/google/callback
     ```
   - Copiá el **ID de cliente** y el **secreto**.
4. En Railway → Variables:
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
5. Redesplegá. El botón "Continuar con Google" aparece solo: la app pregunta
   `/api/auth/proveedores` y sólo muestra los que están configurados de verdad.

### Facebook ❌

1. [developers.facebook.com](https://developers.facebook.com) → **Mis apps →
   Crear app** → tipo **Consumidor**.
2. Agregá el producto **Inicio de sesión con Facebook** → **Web**.
3. En su configuración, **URI de redireccionamiento de OAuth válidos**:
   ```
   https://TU-DOMINIO/api/auth/facebook/callback
   ```
4. **Configuración → Básica**: copiá el **Identificador de la app** y la
   **Clave secreta**.
5. En Railway: `FACEBOOK_APP_ID` y `FACEBOOK_APP_SECRET`.
6. Para que entre gente que no sea vos, la app tiene que pasar a **Modo activo**
   y pedir el permiso `email` en **Revisión de la app**. Facebook pide política
   de privacidad publicada y un video mostrando el flujo.

### Costo

Los dos son **gratis**. Lo que cuesta es tiempo: la revisión de Facebook
demora días y es más quisquillosa que la de Google.

---

## 3. Play Store y App Store

### Los links, en el orden en que se usan

**Android — Google Play**

| Qué | Link |
|---|---|
| Crear la cuenta de desarrollador (USD 25) | https://play.google.com/console/signup |
| Consola, para subir el AAB y las capturas | https://play.google.com/console |
| Requisitos de la ficha (íconos, capturas, textos) | https://support.google.com/googleplay/android-developer/answer/9866151 |
| Formulario de Data Safety (obligatorio) | https://support.google.com/googleplay/android-developer/answer/10787469 |
| Clasificación de contenido | https://support.google.com/googleplay/android-developer/answer/9859655 |
| Política de apps de citas | https://support.google.com/googleplay/android-developer/answer/9877032 |
| Política de pagos (por qué la app no vende) | https://support.google.com/googleplay/android-developer/answer/10281818 |
| Firmar la app (Play App Signing) | https://support.google.com/googleplay/android-developer/answer/9842756 |

**iOS — App Store**

| Qué | Link |
|---|---|
| Inscribirse en Apple Developer (USD 99/año) | https://developer.apple.com/programs/enroll/ |
| App Store Connect, para subir la build | https://appstoreconnect.apple.com |
| Guías de revisión (la 3.1.1 es la del cobro) | https://developer.apple.com/app-store/review/guidelines/ |
| Sign in with Apple: cuándo es obligatorio | https://developer.apple.com/app-store/review/guidelines/#sign-in-with-apple |
| Privacidad de la ficha (nutrition labels) | https://developer.apple.com/app-store/app-privacy-details/ |
| Medidas de las capturas | https://developer.apple.com/help/app-store-connect/reference/screenshot-specifications |
| Small Business Program (comisión 15 % en vez de 30 %) | https://developer.apple.com/app-store/small-business-program/ |

**Windows** — no hace falta ninguna tienda: el `.exe` se baja de tu propia web
(ver la sección 5). Si algún día lo querés también en la Microsoft Store, la
cuenta de desarrollador individual sale **USD 19, una sola vez**:
https://partner.microsoft.com/dashboard/registration

### Costos, sin vueltas

| Concepto | Costo | Frecuencia |
|---|---|---|
| Cuenta de desarrollador de Google Play | **USD 25** | una vez, de por vida |
| Cuenta de Apple Developer | **USD 99** | por año |
| Mac para compilar iOS | USD 600–1.400 | una vez (sirve una usada) |
| Railway | USD 5 | por mes |
| Dominio propio (opcional) | USD 10–15 | por año |
| **Windows (.exe desde tu web)** | **USD 0** | — |
| Certificado para firmar el .exe (opcional) | USD 200–400 | por año |
| Microsoft Store (opcional, no hace falta) | USD 19 | una vez |

**Total para salir en Android: USD 25 + USD 5/mes.**
**Para salir también en iOS: + USD 99/año + una Mac.**
**Windows no cuesta nada**: el instalador se publica en tu propia web. Sin
certificado de firma, Windows muestra "editor desconocido" la primera vez —
no bloquea la instalación, pero conviene saberlo antes de repartir el link.

No hay forma de compilar ni firmar iOS sin una Mac. No es una limitación del
proyecto, es de Apple.

### Android ✅ / ❌

Ya resuelto: `targetSdk` 35, formato AAB, R8, sin tráfico en claro, sin backup
de datos sensibles, borrar la cuenta desde la app, permisos justificados, y la
clave de firma leída de variables de entorno (nunca del repo).

Falta de tu lado:

1. **Generar la clave de firma. Una sola vez, y guardala con respaldo: si se
   pierde, no se puede volver a publicar la misma app nunca más.**

   ```bash
   keytool -genkey -v -keystore matcher.keystore -alias matcher \
           -keyalg RSA -keysize 2048 -validity 10000
   ```

2. Compilar el AAB firmado:

   ```bash
   export MATCHER_KEYSTORE=/ruta/matcher.keystore
   export MATCHER_KEYSTORE_PASS=... MATCHER_KEY_ALIAS=matcher MATCHER_KEY_PASS=...
   export MATCHER_VERSION_CODE=1 MATCHER_VERSION_NAME=1.0.0
   export VITE_API_URL=https://TU-DOMINIO-DE-RAILWAY
   npm run build:web && npx cap sync android
   cd android && ./gradlew bundleRelease
   ```

3. **Política de privacidad en una URL pública.** Obligatoria. Tiene que decir
   qué se recolecta (email, ubicación aproximada, fotos, mensajes), para qué,
   cuánto se guarda y cómo se borra.
4. **Formulario de Data Safety** en Play Console.
5. **Clasificación de contenido**: 18+.

### iOS ✅ / ❌

Ya resuelto: textos de permiso, `PrivacyInfo.xcprivacy`,
`ITSAppUsesNonExemptEncryption`, borrar la cuenta desde la app, deployment
target iOS 13, y ahora el `CFBundleURLTypes` del login.

Falta: la Mac, la cuenta de Apple Developer, los certificados, la misma
política de privacidad, y clasificación 17+.

⚠️ **Si activás el login con Google o Facebook, Apple exige ofrecer también
Sign in with Apple.** `matcher/oauth.py` está hecho para sumar proveedores (uno
por `dataclass`), pero Apple todavía no está implementado.

---

## 4. El pago dentro de la app · leelo antes de publicar

**Apple (guía 3.1.1) y Google Play exigen que una suscripción digital comprada
dentro de la app pase por SU sistema de cobro.** Una app de citas que abre
MercadoPago, PayPal o Stripe adentro es rechazo en la revisión.

Las pasarelas implementadas en `matcher/pagos.py` están bien y sirven — **pero
sólo en la web**, donde además la comisión es del 5 % en vez del 15 %.

Por eso la app instalada **no vende** (`webapp/frontend/src/cobroEnApp.js`):
muestra los planes para que se entienda qué ofrece cada uno, y si la persona ya
se suscribió en la web su plan funciona igual adentro de la app. Eso pasa
revisión en cualquier tienda y en cualquier país.

Las dos formas de vender desde la app, cuando llegue el momento:

1. **Google Play Billing / StoreKit.** Es lo que las tiendas quieren. Cuesta
   15 % hasta USD 1M/año facturados, y 30 % arriba. Hay que implementar el
   plugin nativo y validar el recibo del lado del servidor: es trabajo real y
   no se puede ni probar sin la cuenta de desarrollador paga.
2. **Enlace de salida al cobro web.** Depende del país: la Unión Europea (DMA),
   Estados Unidos y —para apps de citas específicamente— Países Bajos lo
   permiten con condiciones; en el resto sigue siendo causal de rechazo. Está
   detrás de una bandera apagada (`VITE_PAGOS_EN_APP=1`) porque encenderla es
   una decisión con riesgo y tiene que ser explícita.

**La recomendación:** salir a las tiendas con la app gratis, monetizar en la
web, y sumar Play Billing cuando haya facturación que justifique el trabajo.

---

## 5. Windows · el programa de escritorio

La misma app React, en una ventana de escritorio. **No es un segundo
producto**: carga exactamente el mismo `webapp/frontend/dist` que sirve la web
y que empaqueta el APK, y habla con el mismo backend. La cuenta, los matches y
los chats son los mismos abriendo el `.exe`, el teléfono o el navegador.

### Cómo se genera el instalador

Lo arma **GitHub Actions en una Windows de verdad**, gratis, con el workflow
`.github/workflows/paquetes.yml`:

1. Pestaña **Actions** → **Instalador de Windows** → **Run workflow**.
2. Cuando termina, el `.exe` queda como artefacto descargable de esa corrida.
3. Para una URL estable (la que va en el botón de la web), etiquetá una versión:

   ```bash
   git tag v1.0.0 && git push origin v1.0.0
   ```

   Eso publica una Release con el instalador adjunto. Esa URL es la que se le
   pasa a la web:

   ```bash
   MATCHER_URL_EXE=https://github.com/vieraschiavi/Matcher/releases/download/v1.0.0/Matcher-1.0.0-instalador.exe \
   MATCHER_URL_APP=https://TU-DOMINIO \
   python3 -m marketing.generar_landing
   ```

El **APK y el AAB** los arma el otro workflow, `apps.yml`, en cada push (y el
AAB va firmado si cargaste el keystore en los secrets).

También se puede armar a mano en una máquina con Windows:

```bat
npm install
set VITE_API_URL=https://TU-DOMINIO-DE-RAILWAY
npm run pc:windows
```

Sale en `dist-escritorio\Matcher-1.0.0-instalador.exe`.
`npm run pc` abre el programa sin empaquetar, para probarlo.

**Desde Linux también sale**, emulando con Wine (`wine`, `wine64` y
`wine32:i386`), y así se generó y se verificó el primero. El ejecutable queda
bien —ícono y textos de versión embebidos— pero el propio instalador no se
puede *correr* completo bajo Wine: NSIS exige Windows de 64 bits y la
emulación WOW64 no la satisface. Para probar la instalación de punta a punta
hace falta una Windows.

### Lo que hace el instalador

| Pedido | Cómo queda |
|---|---|
| Instalador `.exe` | Instalador con pantallas, en español (NSIS) |
| Elegir dónde instalar | Pantalla de carpeta de destino, editable |
| Ícono en el escritorio | Acceso directo "Matcher" |
| Barra de programas | Entrada en el menú Inicio |
| Desinstalador | En "Agregar o quitar programas", con el ícono de la app |

No pide permisos de administrador: se instala para el usuario actual. En una
máquina del trabajo, pedir administrador significa que la mitad de la gente no
lo pueda instalar.

Al desinstalar se borran los datos locales. Lo único que el programa guarda en
la máquina es el token de sesión, y dejarlo después de desinstalar —en una
computadora compartida— es dejarle la cuenta abierta al que venga después.

### En Windows SÍ se vende

Apple y Google exigen su pasarela; Microsoft no cobra nada por un `.exe` que se
baja de tu web. Por eso el programa de escritorio **muestra el botón de comprar
y cobra por las pasarelas de `matcher/pagos.py`**, con la comisión del ~5 % de
la web en vez del 15 % de las tiendas.

Esto costó un detalle fino: el programa carga con `file:`, y la detección de
"app instalada" de `api.js` lo habría tomado por una app de tienda, dejándolo
sin botón de comprar. Lo separa la bandera `matcherEscritorio` que inyecta
`electron/preload.js`, y hay un test que lo fija
(`tests/test_escritorio.py::test_el_escritorio_no_se_confunde_con_una_app_de_tienda`).

### Seguridad de la ventana

Una app de citas pinta bios, fotos y links escritos por desconocidos. La
ventana corre con `contextIsolation: true` y `nodeIntegration: false`, la página
no ve ningún módulo de Node, todo lo que puede tocar del sistema pasa por
`electron/preload.js`, y cualquier link externo se abre en el navegador del
sistema en vez de adentro de la ventana — si no, Matcher sería un navegador sin
barra de direcciones, que es el escenario ideal para una pantalla de login
falsa. Hay una CSP sin `unsafe-eval` en `webapp/frontend/index.html`.

### Firma (opcional, pero conviene)

Sin certificado, SmartScreen muestra "editor desconocido" la primera vez. No
rompe nada, pero espanta a parte de los que lo bajan. El certificado se compra
aparte y **la clave no va al repo**: una clave de firma filtrada no se rota, hay
que revocar el certificado y comprar otro.

---

## 6. La web pública

`landing/` es un sitio estático en tres idiomas (es/pt/en) con el video de
demostración, todas las funciones, las capturas, los planes y los botones de
descarga. **Se genera**: `python3 -m marketing.generar_landing`.

Los precios salen de `matcher/planes.py` —la misma fuente que cobra el
checkout— así que la web no puede anunciar un plan que no existe. Los colores
salen de `theme.css`. Los videos y las capturas salen de la app corriendo:

```bash
python3 -m uvicorn webapp.backend.api:app --port 8899   # en otra terminal
node marketing/capturar.mjs                              # capturas reales
python3 -m marketing.generar_video                       # 6 videos, es/pt/en
python3 -m marketing.generar_landing                     # el sitio
```

Los botones de descarga se configuran por variables de entorno
(`MATCHER_URL_APP`, `MATCHER_URL_EXE`, `MATCHER_URL_APK`). **Si falta una, el
botón sale apagado y dice "en preparación"** en vez de linkear a un 404.

Es estático: se sube a cualquier hosting (Netlify, Vercel, Cloudflare Pages,
GitHub Pages) o se sirve desde el mismo Railway.

Los videos **no tienen voz en off**. Se pidieron con voz femenina y no hay acá
ninguna voz sintética que no suene a robot; poner ésa es peor que no poner
ninguna. Están armados para leerse sin audio —que es como se mira la mayoría
del video en redes— con el tiempo en pantalla calculado por largo de texto.
Cuando haya una locutora o un TTS decente, se suma la pista sin rehacer la
imagen. Tampoco llevan música: una pista con licencia dudosa es un reclamo de
derechos en el primer video que ande bien.

---

## 7. Lo que sigue sin resolverse, y es honesto decirlo

1. **No hay moderación.** Hay reportes, no hay revisión. Una app de citas sin
   moderación de fotos y de chat se llena de abuso en la primera semana, y es
   causal de baja tanto en Play como en App Store. Es el punto más caro y el
   menos opcional (ver el desglose de costos en `PLAN_NEGOCIO.md`).
2. **Las fotos viajan como data-URI dentro de la base.** Funciona, pero con
   usuarios reales van a un bucket de objetos con URLs firmadas.
3. **Verificación de identidad**: hoy `verificado` es un flag, no un proceso.
4. **Registro de base de datos ante la URCDP** (Uruguay, Ley 18.331): trámite
   sin arancel, pero obligatorio si tratás datos personales.

---

## Evidencia de la última auditoría

Corrida contra un servidor levantado con las mismas variables que usaría
Railway (disco real, `MATCHER_EFIMERO=0`, secreto puesto):

```
PASOS: 71   FALLOS: 0
```

Cubre: salud y catálogos, alta, login, perfil, "qué buscás", disponible hoy,
fotos, los diez listados de gente con el filtro duro puesto, interacciones y
muro de pago, automatch, Crush Time, cita a ciegas, boost, matches y chat,
pago completo (checkout → confirmación → plan activo → cancelación),
reportes, logout con revocación y borrado de cuenta.

Además, la prueba que justifica todo esto: se crea una cuenta con foto, se
**reinicia el servidor entero**, y la cuenta, la foto y la sesión siguen ahí.

Y en el repo: **358 tests** verdes, `ruff` limpio.
