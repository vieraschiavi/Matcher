# Publicar Matcher · Play Store y App Store

Estado real de cada requisito, con lo que ya está hecho y lo que depende de una
cuenta tuya. Nada de esto es opcional: cada punto marcado ❌ es un rechazo.

---

## Android · Play Store

### Ya resuelto en el repo

| Requisito | Estado | Dónde |
|---|---|---|
| `targetSdk` 35 (exigido para envíos nuevos) | ✅ | `android/variables.gradle` |
| Formato AAB (Play no acepta APK para apps nuevas) | ✅ | `./gradlew bundleRelease` |
| Build de release ofuscado y reducido (R8) | ✅ | `minifyEnabled true` · 1,29 MB vs 3,9 del debug |
| Sin `debuggable` | ✅ | es propio del buildType release |
| Sin tráfico en claro | ✅ | `res/xml/seguridad_red.xml` |
| Sin backup de datos sensibles | ✅ | `allowBackup=false` + `reglas_backup.xml` |
| Borrar la cuenta desde la app | ✅ | "Mi perfil" → Borrar mi cuenta |
| Permisos justificados, ninguno de más | ✅ | ver tabla abajo |
| La clave de firma NO está en el repo | ✅ | se lee de variables de entorno |

### Falta, y depende de vos

- ❌ **Generar la clave de firma.** Una sola vez, y guardala fuera del repo y
  con respaldo: si se pierde, no se puede volver a publicar la misma app.

  ```bash
  keytool -genkey -v -keystore matcher.keystore -alias matcher \
          -keyalg RSA -keysize 2048 -validity 10000
  ```

  Después, para compilar firmado:

  ```bash
  export MATCHER_KEYSTORE=/ruta/matcher.keystore
  export MATCHER_KEYSTORE_PASS=... MATCHER_KEY_ALIAS=matcher MATCHER_KEY_PASS=...
  export MATCHER_VERSION_CODE=1 MATCHER_VERSION_NAME=1.0.0
  npm run build:web && npx cap sync android
  cd android && ./gradlew bundleRelease
  # → android/app/build/outputs/bundle/release/app-release.aab
  ```

- ❌ **Política de privacidad en una URL pública.** Obligatoria para cualquier
  app que pida ubicación o cámara. Tiene que decir qué se recolecta (email,
  ubicación aproximada, fotos, mensajes), para qué, cuánto se guarda y cómo se
  borra.
- ❌ **Formulario de Data Safety** en Play Console. Declarar: email, ubicación
  aproximada, fotos/videos, mensajes. Marcar que **no** hay publicidad ni
  seguimiento de terceros (es cierto: la app no tiene SDK de analítica).
- ❌ **Clasificación de contenido**: la app es de citas → 18+.

### Permisos, y por qué está cada uno

| Permiso | Para qué | Si se saca |
|---|---|---|
| `INTERNET` | Hablar con la API | no funciona nada |
| `ACCESS_COARSE_LOCATION` / `FINE` | Radar y cruces | el radar cae al centro de la ciudad |
| `CAMERA` | Sacar foto / grabar video del perfil | sólo se pueden subir archivos |
| `RECORD_AUDIO` | Audio de esos videos | videos mudos |
| `READ_MEDIA_IMAGES` / `VIDEO` | Elegir de la galería | no se pueden subir archivos |
| `READ_EXTERNAL_STORAGE` (≤32) | Lo mismo en Android 12 y anteriores | ídem |

Todos van declarados con `required="false"` en `uses-feature`, así que la app
sigue instalable en un teléfono sin cámara o sin GPS.

---

## iOS · App Store

### Ya resuelto en el repo

| Requisito | Estado | Dónde |
|---|---|---|
| Textos de permiso (cámara, micrófono, fotos, ubicación) | ✅ | `Info.plist` |
| `PrivacyInfo.xcprivacy` (obligatorio desde mayo 2024) | ✅ | `ios/App/App/` |
| `ITSAppUsesNonExemptEncryption` | ✅ | `Info.plist` — evita la pregunta de exportación en cada envío |
| Borrar la cuenta desde la app | ✅ | requisito duro de Apple desde 2022 |
| Deployment target iOS 13 | ✅ | `project.pbxproj` |

### Falta, y depende de vos

- ❌ **Una Mac con Xcode.** No hay forma de compilar ni firmar iOS sin eso: no
  es una limitación del proyecto, es de Apple.
- ❌ **Cuenta de Apple Developer** (USD 99/año) y los certificados.
- ❌ **Misma política de privacidad** y el cuestionario de privacidad de App
  Store Connect.
- ❌ **Clasificación 17+** por contenido de citas.
- ⚠️ **Si agregás login con Google/Facebook, Apple exige ofrecer también Sign
  in with Apple.** `matcher/oauth.py` está hecho para sumar proveedores (uno
  por `dataclass`), pero hoy Apple no está implementado.

```bash
npm run ios:abrir     # en macOS: abre el proyecto en Xcode
```

---

## Lo que sigue sin estar listo para usuarios reales

Esto no es de empaquetado, es de arquitectura, y **es lo que hay que resolver
antes de publicar**:

1. **La base es efímera en Vercel.** Medido: de 30 lecturas en paralelo, 17
   devolvieron el perfil sin los filtros guardados, y de 202 tarjetas 45 eran
   del género que el usuario no pidió. La app ahora se defiende (el teléfono
   recuerda los filtros y se los vuelve a imponer al servidor), pero las fotos
   que sube un usuario y su cuenta siguen desapareciendo en cada arranque en
   frío. **Hay que mover el backend a un host con disco** — `Dockerfile`,
   `fly.toml` y `render.yaml` ya están, son cuatro comandos.
2. **Las fotos viajan como data-URI dentro de la base.** Para usuarios reales
   van a un bucket de objetos con URLs firmadas.
3. **No hay moderación.** Hay reportes, no hay revisión. Una app de citas sin
   moderación de fotos y chat se llena de abuso en la primera semana, y es
   causal de baja tanto en Play como en App Store.
4. **Verificación de identidad**: hoy `verificado` es un flag, no un proceso.
