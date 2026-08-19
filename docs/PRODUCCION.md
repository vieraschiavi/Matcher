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

### Costos, sin vueltas

| Concepto | Costo | Frecuencia |
|---|---|---|
| Cuenta de desarrollador de Google Play | **USD 25** | una vez, de por vida |
| Cuenta de Apple Developer | **USD 99** | por año |
| Mac para compilar iOS | USD 600–1.400 | una vez (sirve una usada) |
| Railway | USD 5 | por mes |
| Dominio propio (opcional) | USD 10–15 | por año |

**Total para salir en Android: USD 25 + USD 5/mes.**
**Para salir también en iOS: + USD 99/año + una Mac.**

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

## 5. Lo que sigue sin resolverse, y es honesto decirlo

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

Y en el repo: **288 tests** verdes, `ruff` limpio.
