# Matcher — edición OWNER (versión completa, para probar)

Esta carpeta es el punto de entrada del instalador **del dueño**: el programa
entero, con el backend adentro, para probar Matcher al 100 % en una PC sin
depender de que haya un servidor arriba, sin credenciales de pasarela y sin
internet.

---

## 1. Dónde está el instalador

**No está commiteado en este repositorio, y es a propósito.** Pesa del orden de
80–90 MB (Electron + Python embebido + el motor). GitHub admite hasta 100 MB por
archivo, así que *entraría* — pero un binario de ese tamaño por versión infla el
`git clone` **para siempre**: el historial de git guarda cada versión completa y
no se saca sin reescribir el historial entero.

Se publica como **Release**, que es una URL estable y no pesa en el clon:

| Cómo obtenerlo | Pasos |
|---|---|
| **Release** (lo normal) | Pestaña **Releases** del repo → última etiqueta `owner-v*` → `Matcher-OWNER-<versión>-instalador.exe` |
| **Sin etiquetar** | Pestaña **Actions** → workflow **Instalador OWNER** → **Run workflow** → cuando termina, artefacto `Matcher-OWNER-windows` |
| **Compilarlo yo** | En una Windows con Node: `npm ci && npm run pc:owner:windows` (necesita el Python embebido en `dist-owner/python`; los pasos exactos están en `.github/workflows/owner.yml`) |

Para publicar una versión nueva: `git tag owner-v1.0.0 && git push origin owner-v1.0.0`.
El workflow la compila y crea la Release solo.

---

## 2. Qué instala, y dónde

- Instalador con pantallas (no instala solo): se elige la carpeta.
- **No propone el disco C:** — busca un disco de datos fijo y con permiso de
  escritura, y si la máquina tiene uno solo, cae en C: (regla 19).
- Acceso directo en el escritorio y en el menú Inicio, y desinstalador.
- Convive con la edición normal sin pisarla: `appId` y carpeta propios, base de
  datos propia.
- **Al desinstalar NO borra los datos**, al revés que la edición normal: acá la
  base entera está en la máquina, y borrarla se llevaría los perfiles y los
  chats de prueba. La edición normal sí borra, porque lo único que guarda es el
  token de sesión.

---

## 3. Primer arranque

1. Abrí Matcher (Owner). Levanta su propio backend en `127.0.0.1` con un puerto
   libre y la base sembrada con los perfiles sintéticos de la demo.
2. Registrate con tu mail.
3. Menú **Matcher → Cuenta de dueño (duenio.txt)…** — se abre un archivo de
   texto. Escribí ahí el mail con el que te registraste, guardá y **volvé a
   abrir Matcher**.
4. Esa cuenta queda en Gold y ve el **Panel** (facturación, cliente por cliente,
   pedidos de demo).

El archivo se crea vacío con las instrucciones adentro. Vacío = ninguna cuenta
de dueño; nunca hay una cuenta privilegiada de fábrica.

---

## 4. Qué NO es esto

**No es "el `.exe` que desbloquea la versión paga".** Vale la pena tenerlo
escrito porque el pedido vuelve:

- Matcher **no vende licencias, vende suscripción** (regla 15). No hay archivo
  de licencia ni clave de activación: pagar levanta el **plan de la cuenta** en
  el servidor, y ese plan te sigue a la web, al APK y al `.exe` con sólo entrar.
- **El archivo que baja un cliente es el mismo para todos** (regla 20). No hay
  un `.exe` de Gold y otro de gratis, y no puede haberlo: un binario no hace
  cumplir un plan — se lo parchea, o se pasa el link por WhatsApp. Sostener el
  plan en el cliente es el mismo agujero que ya se tapó en los pagos (regla 14).
- Por eso **este instalador no lleva ningún token adentro**. Un token válido
  publicado en un repositorio no es una licencia: es una credencial filtrada, y
  la firma impide inventar licencias nuevas, no impide copiar la que está
  publicada. Acá no hay nada que copiar: es una instancia propia con su propia
  base vacía, así que tenerlo no le da a nadie acceso a la cuenta de nadie.

Lo que la edición owner sí te da es lo que pediste: **probar el producto
completo**, con las mismas rutas de código que corren en producción — el mismo
motor, el mismo backend, la misma app React, el mismo camino de Gold del dueño
(`matcher/duenio.py`).

---

## 5. Diferencias con la edición de cliente, una por una

| | Cliente (`electron-builder.yml`) | Owner (`electron-builder-owner.yml`) |
|---|---|---|
| Backend | remoto, compartido | **adentro del `.exe`**, en `127.0.0.1` |
| Base de datos | del servidor | local, en la carpeta de datos del usuario |
| Pasarela de pago | la configurada en el servidor | `demo` (dice en pantalla que no mueve plata) |
| Perfiles | los reales | los sintéticos de la demo, marcados como tales |
| Internet | necesario | **no hace falta** |
| Al desinstalar | borra los datos locales | los conserva |
| Cuenta de dueño | `MATCHER_CUENTAS_DUENIO` en el panel de la plataforma | `duenio.txt` en la carpeta de datos |

El frontend es **el mismo build** en las dos: `webapp/frontend/dist`. No hay una
segunda interfaz que se pueda desincronizar.

---

## 6. Si el servidor local no arranca

La app **abre igual** y cae al backend remoto de siempre. Es deliberado: peor
que no tener servidor local es tener uno que no responde y una app que le habla
igual. Si eso pasa, casi siempre es que el Python embebido no quedó bien armado
—`.github/workflows/owner.yml` lo comprueba importando el backend antes de
empaquetar, justamente para que falle ahí y no en tu máquina después de instalar
90 MB.
