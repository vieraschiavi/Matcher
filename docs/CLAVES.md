# Todas las claves de Matcher, una por una

Qué variable, de dónde se saca, y qué pasa si falta. **Ninguna de estas se
escribe en el código ni se commitea**: van en el panel de variables de entorno
de donde esté desplegado (Vercel → Settings → Environment Variables; Railway →
servicio → Variables).

> **Lo que NO va acá y no va a ninguna parte del repo: el número de cuenta
> bancaria.** A qué cuenta llega la plata se configura en el panel de
> MercadoPago, no en la app. Matcher nunca ve ni guarda un número de cuenta.

---

## 1. Lo mínimo para que la app funcione

| Variable | Valor | Si falta |
|---|---|---|
| `MATCHER_SECRETO` | 48 caracteres al azar | las sesiones se caen al reiniciar |
| `MATCHER_URL_PUBLICA` | `https://tu-dominio` | fallan el login externo y los webhooks |
| `MATCHER_BD` | `/datos/matcher.db` (con disco) | la base va a un disco que se borra |
| `MATCHER_DEMO` | `1` mientras probás, `0` con gente real | siembra los 60 perfiles sintéticos |

Para el secreto:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

**Si cambiás `MATCHER_SECRETO`, se cierran todas las sesiones abiertas.** Es lo
que hay que hacer si sospechás que se filtró; no es algo para tocar por gusto.

---

## 2. Tu propia cuenta en Gold (la "licencia del dueño")

**Matcher no tiene licencias.** No es un programa que se compra una vez: es una
suscripción. No hay archivo de licencia, ni clave de activación, ni nada que
descargar — pagar levanta el **plan de tu cuenta** en el servidor, y ese plan te
sigue a la web, al APK y al programa de Windows con sólo iniciar sesión. La
descarga del APK y del `.exe` es libre y gratis para cualquiera; lo que se cobra
es el plan.

Para que TU cuenta tenga Gold sin pagarte a vos mismo:

| Variable | Valor |
|---|---|
| `MATCHER_CUENTAS_DUENIO` | `vieraschiavi@gmail.com,arcortito@gmail.com` |

Esas cuentas quedan en Gold al iniciar sesión, por 365 días, renovándose sola.
**No inventa un pago**: el historial de cobros sigue mostrando sólo lo que se
cobró de verdad. Sin la variable, la lista está vacía y no hay ninguna cuenta
privilegiada. No acepta comodines (`*@gmail.com` no funciona, a propósito).

---

## 2 bis. La demo bajo pedido (Resend)

La demo **no es pública ni descargable**: la landing muestra el video y un
formulario. Quien lo llena queda registrado y te llega el aviso.

### Sin configurar nada

Funciona igual: el pedido se guarda y lo ves en **Panel → Pedidos de demo**.
No se manda mail, y el panel te lo dice con todas las letras para que no te
enteres por un prospecto que reclama.

### Con Resend (recomendado, gratis)

Panel: <https://resend.com/api-keys>

1. Creá la cuenta con **vieraschiavi@gmail.com** (importante, ver abajo).
2. **API Keys → Create API Key**, permiso *Sending access*. Copiala: se ve
   una sola vez.
3. En Vercel → Settings → Environment Variables:

| Variable | Valor |
|---|---|
| `RESEND_API_KEY` | `re_...` |
| `MATCHER_EMAIL_DEMOS` | `vieraschiavi@gmail.com` (opcional, ya es el default) |

**El detalle que no está en el botón de "empezar":** sin dominio propio
verificado, Resend sólo deja mandar **desde** `onboarding@resend.dev` y **sólo
hacia la dirección de tu propia cuenta de Resend**. Para esto alcanza —el aviso
va a tu mail— pero por eso importa crear la cuenta con el mail donde querés
recibir. Cuando tengas dominio, lo verificás (unos registros DNS) y ponés
`MATCHER_EMAIL_REMITENTE=demos@tudominio.com`.

Plan gratis: 3.000 mails por mes, 100 por día. Para pedidos de demo sobra.

### Con tu propio SMTP (alternativa)

Si ya tenés servidor de correo y no querés sumar otro servicio:
`MATCHER_SMTP_HOST`, `MATCHER_SMTP_PUERTO` (587), `MATCHER_SMTP_USUARIO`,
`MATCHER_SMTP_CLAVE`. Resend tiene prioridad si están los dos.

### Volver a abrir la demo (si alguna vez querés)

| Variable | Valor |
|---|---|
| `MATCHER_DEMO_PUBLICA` | `1` para mostrar las cuentas de demo en la entrada |
| `VITE_CLAVE_DEMO` | la contraseña, al compilar el frontend |

Vienen apagadas. Y **cambiá `MATCHER_DEMO_CLAVE`**: la contraseña vieja
(`matcher2026`) estuvo publicada en la pantalla de entrada y en el repositorio,
así que hay que darla por conocida.

---

## 3. MercadoPago

Panel: <https://www.mercadopago.com.uy/developers/panel>

1. Entrá con tu cuenta de MercadoPago (la que recibe la plata).
2. **Tus integraciones → Crear aplicación**. Tipo: *Pagos online*, modelo
   *Checkout Pro*.
3. En la aplicación, sección **Credenciales**:
   - **Credenciales de prueba** para probar sin mover plata.
   - **Credenciales de producción** para cobrar de verdad.
4. Copiá el **Access Token** (empieza con `TEST-` o `APP_USR-`).

| Variable | De dónde sale | Obligatoria |
|---|---|---|
| `MATCHER_PASARELA` | poné `mercadopago` | sí, si no queda en `demo` |
| `MERCADOPAGO_ACCESS_TOKEN` | Credenciales → Access Token | sí |
| `MERCADOPAGO_WEBHOOK_SECRET` | ver abajo | **sí** |

### El webhook (esto es lo que hace que el plan se active solo)

En la misma aplicación: **Webhooks → Configurar notificaciones**.

- URL: `https://tu-dominio/api/pagos/webhook/mercadopago`
- Evento: **Pagos** (`payment`)
- Al guardar, MercadoPago muestra una **clave secreta**: ésa va en
  `MERCADOPAGO_WEBHOOK_SECRET`.

**Sin el secreto del webhook, Matcher rechaza todas las notificaciones** (una
notificación sin firmar es que cualquiera en internet te active planes gratis
mandando un POST). Y sin webhook, el plan sólo se activa si la persona vuelve a
la app después de pagar; si cierra el navegador, paga y no recibe nada.

### Probar sin gastar plata

Con las credenciales de prueba, MercadoPago da tarjetas de test:
<https://www.mercadopago.com.uy/developers/es/docs/checkout-pro/additional-content/test-cards>

---

## 4. PayPal (opcional)

Panel: <https://developer.paypal.com/dashboard/applications>

1. **Apps & Credentials** → *Create App* (tipo *Merchant*).
2. Copiá **Client ID** y **Secret**.
3. **Webhooks** → *Add Webhook*:
   URL `https://tu-dominio/api/pagos/webhook/paypal`, evento
   `CHECKOUT.ORDER.APPROVED` y `PAYMENT.CAPTURE.COMPLETED`. Copiá el
   **Webhook ID**.

| Variable | Valor |
|---|---|
| `PAYPAL_CLIENT_ID` | Client ID |
| `PAYPAL_CLIENT_SECRET` | Secret |
| `PAYPAL_WEBHOOK_ID` | el id del webhook |
| `PAYPAL_ENTORNO` | `sandbox` para probar, `live` para cobrar |

`PAYPAL_ENTORNO` viene en `sandbox` por defecto **a propósito**: para cobrar de
verdad hay que ponerlo explícitamente.

---

## 5. dLocal (opcional, tarjetas locales de Latinoamérica)

Panel: <https://merchants.dlocal.com> → *Integration → API Keys*

| Variable | Valor |
|---|---|
| `DLOCAL_X_LOGIN` | x_login |
| `DLOCAL_X_TRANS_KEY` | x_trans_key |
| `DLOCAL_SECRET_KEY` | secret key |

Webhook: `https://tu-dominio/api/pagos/webhook/dlocal`

---

## 6. Login con Google (opcional)

Panel: <https://console.cloud.google.com/apis/credentials>

1. **Pantalla de consentimiento de OAuth** → Externo. Ámbitos: `email`,
   `profile`, `openid` y nada más (cada ámbito extra suma revisión).
2. **Credenciales → Crear credenciales → ID de cliente de OAuth** → tipo
   **Aplicación web**.
3. **URI de redireccionamiento autorizado**, exacto:
   `https://tu-dominio/api/auth/google/callback`

| Variable | Valor |
|---|---|
| `GOOGLE_CLIENT_ID` | ID de cliente |
| `GOOGLE_CLIENT_SECRET` | Secreto de cliente |

Sin las dos, el botón "Continuar con Google" **no aparece**. No hay modo
simulado: un login de mentira es una puerta abierta si se despliega.

---

## 7. Facebook (opcional)

Panel: <https://developers.facebook.com/apps>

App tipo *Consumidor* → producto *Inicio de sesión con Facebook* → *Web*.
Redirección: `https://tu-dominio/api/auth/facebook/callback`

| Variable | Valor |
|---|---|
| `FACEBOOK_APP_ID` | Identificador de la app |
| `FACEBOOK_APP_SECRET` | Clave secreta |

---

## 8. Firmar la app (para publicar)

### Android — clave de firma

```bash
keytool -genkey -v -keystore matcher.keystore -alias matcher \
        -keyalg RSA -keysize 2048 -validity 10000
```

Te pide una contraseña: **guardala en un gestor de contraseñas y hacé copia del
archivo `.keystore`**. Si se pierde, no se puede volver a publicar
actualizaciones de la misma app en Play Store, nunca. No hay recuperación.

Para el CI, en GitHub → Settings → Secrets and variables → Actions:

| Secret | Valor |
|---|---|
| `ANDROID_KEYSTORE_BASE64` | `base64 -w0 matcher.keystore` |
| `ANDROID_KEYSTORE_PASS` | la contraseña del keystore |
| `ANDROID_KEY_ALIAS` | `matcher` |
| `ANDROID_KEY_PASS` | la contraseña de la clave |

### Windows — firma del `.exe` (opcional)

Sin certificado, SmartScreen dice "editor desconocido" la primera vez. No
bloquea la instalación. El certificado se compra aparte (USD 200–400/año) y su
clave **no va al repo**: una clave de firma filtrada no se rota, hay que
revocar el certificado y comprar otro.

---

## 9. Checklist antes de cobrarle a alguien de verdad

- [ ] `MATCHER_PASARELA=mercadopago` (con `demo` **no se cobra nada**)
- [ ] `MERCADOPAGO_ACCESS_TOKEN` de **producción**, no el `TEST-`
- [ ] `MERCADOPAGO_WEBHOOK_SECRET` puesto y webhook configurado
- [ ] `MATCHER_URL_PUBLICA` apuntando al dominio real (el webhook y el
      redirect de vuelta se arman con esto)
- [ ] `MATCHER_DEMO=0` — con `1` la base se llena de perfiles sintéticos
- [ ] `MATCHER_BD` sobre un disco que persista
- [ ] Probado el circuito completo con una tarjeta de prueba
- [ ] Política de privacidad publicada (la piden las dos tiendas)

Para ver cómo quedó, sin exponer ninguna credencial:

```bash
curl https://tu-dominio/api/pagos/planes-disponibles
# {"pasarela": "mercadopago", "configurada": true}
```

`configurada: false` quiere decir que falta alguna credencial de esa pasarela.
