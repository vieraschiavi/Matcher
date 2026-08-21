# CLAUDE.md — Matcher

> Contexto persistente para Claude Code. Leelo al iniciar cada sesión.

## Qué es
**Matcher** es una app de citas (web + Android + iOS) que toma lo que funciona
de Tinder/Bumble/Happn y ataca sus dos quejas más repetidas: **los filtros no
se respetan** y **el plan pago es caro**. Acá los filtros —edad, altura,
postura política, equipo de fútbol del país de localización, distancia— son
**duros**, funcionan **completos en el plan gratis**, y los planes pagos salen
una fracción de lo que cobra la competencia.

## Stack
- **Motor:** Python 3.11, sólo biblioteca estándar (`matcher/`)
- **Backend:** FastAPI + uvicorn (`webapp/backend/api.py`), SQLite
- **Frontend:** React 18 + Vite + react-router (HashRouter) (`webapp/frontend/`)
- **Android/iOS:** Capacitor · **Windows/PC:** Electron + electron-builder
  (`electron/`, `electron-builder.yml`) · **Tests:** pytest · **Lint:** ruff

## Comandos
| Acción | Comando |
|--------|---------|
| Instalar | `pip install -r requirements-dev.txt` |
| **Tests** | `python3 -m pytest -q tests/` |
| **Linter** | `ruff check .` |
| Backend | `python3 -m uvicorn webapp.backend.api:app --port 8820` |
| Build web | `npm run build:web` |
| Sembrar demo | `python3 -m matcher.demo datos/matcher.db` |
| APK debug | `npm run apk:debug` (necesita `ANDROID_HOME`) |
| iOS | `npm run ios:abrir` (necesita macOS + Xcode) |
| Programa de PC | `npm run pc` (abre la ventana sin empaquetar) |
| Instalador Windows | `npm run pc:windows` (correr EN Windows) |
| Kit de marca e íconos | `python3 -m marketing.generar_kit` |
| Capturas para la web | `node marketing/capturar.mjs` (con el backend arriba) |
| Videos demo (es/pt/en) | `python3 -m marketing.generar_video` |
| **Web pública** | `python3 -m marketing.generar_landing` |
| Informe ejecutivo (Excel) | `python3 -m marketing.generar_informe` |

## Reglas que no se rompen

1. **El filtro es DURO, no un peso más del score.** Si alguien pide sólo
   hinchas de Peñarol, no aparece nadie más. Nunca "compensar" un filtro con
   otra afinidad: es exactamente la queja que hace que la gente abandone la
   competencia. `filtros.py` descarta, `scoring.py` sólo ordena. La separación
   es el diseño, no una casualidad — hay tests en `test_filtros.py` que existen
   sólo para impedir que se mezclen.

2. **El equipo de fútbol es RELATIVO al país del usuario.** El catálogo sale de
   `geo.equipos_de(pais)`: un uruguayo elige entre equipos uruguayos, un
   mexicano entre mexicanos. **Nunca cablees un país.** Lo mismo con las olas
   geográficas (ciudad → país → región → mundo) y sus pesos en `geo.PESO_OLA`.
   Si tocás eso, corré `tests/test_geo.py` y `tests/test_scoring.py`: hay tests
   que verifican que la regla se dé vuelta al cambiar el país base.

3. **La ola manda antes que el puntaje.** Alguien de tu ciudad con 60 de score
   aparece antes que alguien de otro continente con 95.
   `scoring.ordenar_deck(priorizar_cercania=True)` es el default y hay un test
   dedicado.

4. **Todos los filtros están en el plan gratis.** Es LA decisión comercial del
   producto: se cobra volumen (likes, superfans), visibilidad y ver quién te
   dio like — **nunca el derecho a filtrar**. `planes.PLANES["gratis"]
   .limites.filtros_avanzados is None` y hay un test que lo fija.

5. **Los perfiles de la demo se declaran sintéticos.** `sintetico=True` viaja
   en el registro, la tarjeta muestra el cartel y el ranking también. Las caras
   del pack (`assets/personas/`) son **rostros generados, de personas que no
   existen**. Nunca poblar con fotos de personas reales: un perfil de citas con
   la cara de alguien que no dio su consentimiento es una identidad falsa, y la
   licencia comercial de un banco de imágenes no cubre ese uso. Ver
   `assets/personas/LEEME.md`.

6. **18+.** Ningún perfil, ni siquiera uno sintético de demostración, puede
   mostrar a alguien que parezca menor de edad. Al regenerar el pack de caras,
   la revisión es **manual, una por una**. Ya se descartaron 16 de 112 por eso.

7. **Determinismo del seed.** Todo sale de `random.Random(demo.SEMILLA)` y del
   reparto ordenado de `fotos.Fuente`. Si dejás de ser determinista, se caen
   los tests de deck, de ranking y de demo.

8. **El perfil se guarda como un JSON a mano en `almacen._a_json`.** Si agregás
   un campo a `Perfil`, agregalo también ahí Y en `_desde_json`, o se pierde en
   cada guardado, en silencio y sin error. Ya pasó con `intenciones` y
   `disponible_hasta`: "qué buscás" no sobrevivía a editar el perfil y
   "disponible hoy" no funcionó nunca — se marcaba, respondía 200, y a la
   lectura siguiente estaba apagado. Lo fija
   `test_ningun_campo_del_perfil_se_pierde_al_guardar`, que recorre los campos
   del dataclass en vez de listarlos: un test que los enumere a mano se va a
   olvidar del próximo igual que se olvidó la serialización.

9. **Lo que decide el servidor no lo esconde el cliente.** "Quién me dio like"
   en el plan gratis devuelve `perfiles: []`, no los perfiles con un blur
   encima. Mandar los datos y taparlos con CSS es la fuga clásica de este
   feature; hay un test.

10. **Nada de promesas que no se pueden sostener.** Los precios de la
   competencia en `planes.REFERENCIA_COMPETENCIA` van marcados
   `verificado: False` y la UI muestra el aviso. La pasarela `demo` dice en
   pantalla que no mueve plata.

11. **El login externo no se simula.** Sin `GOOGLE_CLIENT_ID` y
    `GOOGLE_CLIENT_SECRET`, `oauth.disponibles()` devuelve vacío y el botón no
    aparece — nunca agregues un modo "demo" que finja un login, porque es una
    puerta abierta si se despliega. Tres cosas que no se tocan en `oauth.py`:
    el `state` es obligatorio, de un solo uso y con vencimiento; se exige
    `email_verified`; y el `id_token` **no se lee sin verificar la firma** (por
    eso los datos se piden al endpoint `userinfo`, no se parsea el JWT). El
    alta a medio hacer vive en `altas_pendientes`, no como perfil incompleto:
    un perfil a medias se cuela en consultas que no lo esperan.

12. **La videollamada la habilitan LOS DOS.** Una llamada muestra tu cara, tu
    casa y tu voz: el link no existe para nadie —ni para quien la propuso—
    hasta que la otra persona acepta. El servidor manda `enlace: null`
    (`videollamada._a_dict`); no se manda tapado, no se manda. En una cita a
    ciegas sin revelar está bloqueada, porque sería entregar por cámara la cara
    que `aciegas.py` se cuida de no mandar. Y el link pegado se valida contra
    el dominio del proveedor comparando el **host parseado**, anclado al final:
    `meet.google.com.trucho.net` contiene el dominio bueno y no es el dominio
    bueno. Sin eso, "proponer una videollamada" es un canal bendecido por la
    app para mandar cualquier URL.
    Y regla 10 otra vez: **Jitsi** la sala la crea Matcher (no hace falta cuenta
    de nadie); **Meet, Zoom y Webex NO se pueden crear** sin las APIs de Google,
    Zoom y Cisco con cuenta de organización — para esos la app pide el link que
    la persona ya generó. No prometas una sala de Meet que la app no puede
    crear.

13. **El escritorio NO es una tienda.** Apple y Google exigen su pasarela; un
    `.exe` que se baja de nuestra web no le paga comisión a nadie, así que en
    Windows **sí se vende**. El programa carga con `file:`, igual que el APK, y
    el respaldo por protocolo de `api.js` lo tomaría por app de tienda: con eso
    el instalador de Windows queda sin botón de comprar, que es lo mismo que no
    tener producto. Lo separa `window.matcherEscritorio`, que inyecta
    `electron/preload.js`. Y la ventana no le da Node a la página
    (`contextIsolation: true`): esta app pinta bios y links de desconocidos, y
    con Node expuesto un XSS en una bio pasa a ser código en la máquina de la
    persona. Todo esto lo fija `tests/test_escritorio.py`.

14. **Un plan no se activa sin que la pasarela diga que la plata entró.**
    `pagos.confirmar` le pregunta a la pasarela (`esta_pagado`) ANTES de dar de
    alta nada. Sin ese chequeo —y así estuvo— cualquiera con una cuenta pedía
    un checkout de Gold, llamaba a `/api/pagos/confirmar` a mano y se quedaba
    con el plan sin pagar un peso. Ojo con la trampa que me comí: una auditoría
    que hace checkout→confirmar y ve el plan activo **no prueba que los pagos
    funcionen**, prueba que el agujero está abierto. Lo fija
    `tests/test_pagos_verificados.py`.
    Y cada pasarela lee su propia notificación (`referencia_de_notificacion`):
    MercadoPago avisa `{"data": {"id": …}}` SIN mandar nuestra referencia, así
    que hay que ir a buscar el pago a su API. Con el `or` encadenado que había
    antes, el webhook no encontraba nada y **el plan no se activaba nunca**.

15. **Matcher no vende licencias, vende suscripción.** No hay archivo de
    licencia ni clave de activación: pagar levanta el PLAN de la cuenta en el
    servidor, y ese plan te sigue a la web, al APK y al `.exe` con sólo entrar.
    Las descargas son libres. Si alguien pide "la licencia del cliente", la
    respuesta es su cuenta. Las cuentas del dueño se listan en
    `MATCHER_CUENTAS_DUENIO` (ver `matcher/duenio.py`): vacía por defecto, sin
    comodines, y **no inventa un pago** — la contabilidad sigue mostrando sólo
    lo que se cobró de verdad.

16. **El panel del dueño no es para todos.** `/api/panel` devuelve la
    facturación y la cantidad de clientes: responde **404** —no 403— a
    cualquiera que no esté en `MATCHER_CUENTAS_DUENIO`, porque un 403 le
    confirma al que prueba que hay algo que atacar. Y el neto que muestra va
    marcado `estimado: true` con la comisión a la vista: la comisión real la
    descuenta la pasarela y varía, y un número que parece exacto sin serlo es
    peor que uno que se declara aproximado. Los impuestos NO están
    descontados ahí. Lo fija `tests/test_panel.py`.

## Convenciones
- Español rioplatense en el dominio y en los nombres de módulo, igual que
  MV Kobra AI y MV Cliente IA.
- **La web pública (`landing/`) se GENERA**, no se edita a mano:
  `python3 -m marketing.generar_landing`. Los precios salen de `matcher.planes`
  —la misma fuente que cobra— y los colores de `theme.css`. Editar los tres
  HTML a mano es perder el cambio en la próxima corrida, y a la semana el
  precio del inglés deja de ser el del español. Lo fija `tests/test_landing.py`,
  que además impide anunciar una función cuyo módulo no exista.
- **Los íconos y el kit de marca se generan**, no se editan a mano:
  `python3 -m marketing.generar_kit` los saca de la misma paleta que
  `theme.css`. Estaban commiteados a mano y quedaron rosa y violeta cuando el
  tema cambió a carbón y fuego: el ícono del escritorio era de otro producto
  que la app que abría. Lo fija `tests/test_kit_marca.py`.
- Comentarios que expliquen **por qué**, no qué. Los que están dicen qué falló
  antes — no los borres al refactorizar.
- Un solo CSS para web, Android e iOS: `webapp/frontend/src/theme.css`. El modo
  móvil es un `@media (max-width: 860px)` del mismo archivo, no una hoja
  aparte — dos hojas se desincronizan a la semana.
- Paleta "carbón y fuego": base grafito neutra (sin tinte violeta — decisión
  del dueño: la base violácea no le hablaba al público que quiere captar) y
  acentos de fuego (`--coral` encendido y `--brasa`). No inventar colores
  nuevos fuera de `:root`.

## Flujo de trabajo
1. Cambio acotado.
2. `ruff check .` y `python3 -m pytest -q tests/`. Nunca declarar algo listo
   sin tests verdes.
3. Si tocaste el frontend: `npm run build:web` y probalo **de verdad** en el
   navegador (Playwright + captura; hay ejemplo en el README).
4. Si tocaste el pack de caras: revisá las imágenes una por una antes de
   commitear (regla 6).

## Do / Don't
- ✅ Tests antes de commitear · ✅ Perfiles sintéticos marcados · ✅ Semilla fija.
- ❌ `rm -rf` ni `git push --force` · ❌ Leer o loguear secretos · ❌ Fotos de
  personas reales en el seed · ❌ Cablear un país · ❌ Mover un filtro al muro
  de pago.
