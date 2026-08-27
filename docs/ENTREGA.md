# Entrega verificada — Matcher

> Qué está probado, **con qué evidencia**, y qué NO lo está.
>
> Este documento no dice "está todo listo". Dice exactamente qué se ejecutó y
> qué resultado dio, y separa dos cosas que conviene no mezclar: **el código**,
> que se puede verificar acá, y **el producto en producción**, que depende de
> credenciales y servicios que no están puestos.

---

## Lo que NO está verificado

Va primero a propósito. Una entrega que empieza por la lista de logros y
esconde los pendientes al final es un informe de ventas, no una entrega.

| Qué falta | Por qué importa | Quién lo destraba |
|---|---|---|
| **Base de datos que persista** | Hoy `/api/salud` responde `almacenamiento_efimero: true`. En Vercel las cuentas y los pagos **se borran**. Con la base borrándose, un cobro de MercadoPago no tiene dónde quedar registrado | El dueño: desplegar en Railway con volumen (`docs/CLAVES.md` § 8 ter) |
| **Cobro real** | `MATCHER_PASARELA` viene en `demo`, que **no mueve plata** y lo dice en pantalla | El dueño: credenciales de producción de MercadoPago + secreto del webhook |
| **Que el instalador ARRANQUE en Windows** | Su script NSIS compila (verificado), pero compilar no es arrancar. Esto se prueba corriendo el `.exe` en una Windows de verdad | El dueño, o el workflow `paquetes.yml` con una etiqueta |
| **Login con Google** | Sin `GOOGLE_CLIENT_ID`/`SECRET` el botón no aparece — a propósito, no hay modo simulado | El dueño: credenciales en Google Cloud |
| **iOS** | El proyecto compila sin firmar en el CI; publicar necesita Mac + cuenta de Apple | El dueño |
| **Firma del `.exe`** | Sin certificado, Windows dice "editor desconocido" la primera vez | El dueño: certificado de firma de código |
| **La app con gente real** | Todo lo verificado usa perfiles sintéticos y la pasarela `demo`. Nadie usó Matcher todavía | — |

**La clave `matcher2026` estuvo publicada** en la pantalla de entrada y en el
repositorio público. Hay que darla por conocida y cambiar `MATCHER_DEMO_CLAVE`.

---

## Lo que SÍ está verificado, y con qué

Todo lo de esta tabla se ejecutó. Nada sale de leer el código y darlo por bueno.

| Verificación | Cómo se hizo | Resultado |
|---|---|---|
| Suite de tests | `python3 -m pytest tests/` | **verde**, 39 archivos de test |
| Linter | `ruff check .` | limpio |
| CI en GitHub | corrida real sobre el commit pusheado | los 3 jobs en verde |
| Acceso a datos ajenos | 11 pruebas por HTTP contra ids REALES de otra cuenta | ninguna filtración |
| Alertas de compra | 14 pruebas | verde |
| Script del instalador | compilado con `makensis -V4` | 0 errores, 0 avisos |
| Web pública | regenerada y comparada | idéntica (sin deriva) |
| Kit de marca | regenerado y comparado | idéntico |
| Panel del dueño | navegador real (Playwright) | 19/19, 0 errores de JS |
| Extremo a extremo | backend vivo + HTTP | 27/27 |

### El método: sabotear el arreglo

Un test que no falla cuando rompés lo que dice proteger no es un test, es un
comentario que tarda en correr. Por eso, para cada guarda importante: se
escribe el test, **se rompe el arreglo a propósito** para confirmar que el test
se pone en rojo, y recién ahí se restaura.

Ejemplo del día: sacando **una sola condición** de `almacen._match_de`
(la que compara si el match es tuyo), caen **7 de 11** pruebas de acceso ajeno.

Esto encontró dos cosas que la lectura no había encontrado:

1. `alertas.py` decía en su encabezado *"nunca levanta"* y **no lo cumplía**.
   Una consulta fallida se llevaba puesto el checkout — o sea que la
   herramienta hecha para no perder ventas las perdía, y sólo con el correo
   caído, que es el día que menos se lo mira.
2. Un test de dependencias que buscaba el nombre en el texto del archivo daba
   verde con la línea comentada. El sabotaje **no** lo puso en rojo, que es
   justamente la señal de que el test no servía.

---

## Errores encontrados y corregidos

Ninguno de éstos rompía la suite. Todos estaban en verde el día anterior.

### Seguridad

| Qué estaba mal | Consecuencia real |
|---|---|
| **Sin freno en el login** | Se podían probar contraseñas a la velocidad que fuera. Y como cada intento cuesta 260.000 iteraciones de PBKDF2 **que paga el servidor**, también era un DoS gratis |
| **El login delataba cuentas por el reloj** | El mensaje de error era el mismo para "no existe el mail" y "erraste la clave" —puesto así a propósito— pero el inexistente volvía sin hashear: ~0 ms contra ~200 ms |
| **Cualquier `data:` pasaba como foto** | `data:text/html,<script>…` entraba como imagen de perfil |
| **Planes regalados** | `/api/pagos/confirmar` daba el plan de alta con sólo recibir una referencia: cualquiera con cuenta pedía Gold y se lo quedaba sin pagar |
| **El webhook de MercadoPago no activaba nada** | Avisa `{"data": {"id": …}}` sin nuestra referencia; el `or` encadenado no encontraba el pago y el plan **no se activaba nunca** |
| **El link de videollamada se validaba por `contains`** | `meet.google.com.trucho.net` pasaba el filtro |

### Infraestructura

| Qué estaba mal | Consecuencia real |
|---|---|
| **El CI llevaba 8 días mudo** | Filtrado a `branches: [main]`, y esa rama había desaparecido. Cada push se salteaba el linter y los tests **en silencio**; la pestaña Actions sin corridas se lee como "no pasó nada malo" |
| **Cada APK del CI apuntaba a un dominio inexistente** | `api.matcher.app` nunca se registró: la app abría bien y moría con "Failed to fetch" en el login, sin una pista |
| **Faltaba Pillow en las dependencias** | En una máquina limpia pytest **no llegaba a recolectar**: exit code 2, cero tests corridos |
| **El contenedor no leía `PORT`** | Railway asigna el puerto y lo pasa ahí. El build habría salido verde, el contenedor habría arrancado, y el healthcheck habría fallado igual |
| **Tres barridos de tabla completa** | El pago por referencia —que corre en **cada webhook**— pasó de 1,637 ms a 0,003 ms |

### Honestidad de los números

| Qué estaba mal | Consecuencia real |
|---|---|
| **El panel contaba las cuentas del dueño como clientes que pagan** | Mostraba "Pagando: 2 · 66,67% de conversión" al lado de "Facturado: USD 0" — dos números que se contradicen en la misma pantalla, y el equivocado era el que uno mira para decidir si el negocio funciona |

---

## Sobre "todo al 100%"

No. Y el motivo es el mismo que hizo que valiera la pena arreglar el panel: un
número que parece exacto sin serlo es peor que uno que se declara aproximado.

Lo que hay es un **código verificado con evidencia ejecutada** y un **producto
que todavía no está en producción**. El primero está cerca de listo. El segundo
depende de tres cosas que no se resuelven escribiendo código:

1. Desplegar donde la base no se borre.
2. Conectar la pasarela de producción.
3. Rotar la clave de demo quemada.

Hasta que eso pase, cualquier "100%" sería una cifra inventada.
