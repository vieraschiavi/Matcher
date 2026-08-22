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

17. **La demo NO es pública.** Decisión comercial del dueño: una demo abierta
    le regala el producto a la competencia — quien entra se lleva las pantallas
    y los flujos sin dejar rastro y sin que nadie le venda nada. El video de la
    landing muestra el RESULTADO y sí es público; la app andando se pide
    (`/api/demo/solicitar`) y se muestra acompañada. Nunca vuelvas a poner un
    botón de descarga en la landing ni a publicar las cuentas de demo: lo
    fijan `tests/test_solicitudes.py::test_la_landing_no_ofrece_descargas` y
    `test_la_demo_no_es_publica_por_defecto`.
    Dos cosas del formulario que parecen detalles y no lo son: **el pedido se
    guarda ANTES de intentar el mail** (si no, un SMTP caído pierde al
    prospecto en silencio), y sin proveedor de mail configurado igual funciona
    — el panel avisa que los pedidos sólo se ven ahí, en vez de prometer un
    aviso que nadie manda.

18. **El login tiene freno y se consulta ANTES de hashear.** Sin freno,
    `/api/login` acepta contraseñas a la velocidad que las mande quien sea —y
    adentro de una cuenta hay conversaciones, fotos y ubicación. El segundo
    efecto es el que se pasa por alto: verificar una contraseña cuesta 260.000
    iteraciones de PBKDF2 **que paga el servidor**, así que un puñado de
    pedidos por segundo deja la app sin responder para todos. Por eso
    `freno.espera()` se llama antes de `almacen.login`, y hay un test que
    rompe si el pedido frenado llega a hashear.
    Tres detalles de `matcher/freno.py`: se cuenta el intento **exista o no la
    cuenta** (si no, el 429 contesta lo que el 401 se calla); el acierto limpia
    los fallos **de ese email** (si no, quien te sabe el mail te traba la
    cuenta gritando contraseñas al aire); y el freno por IP es **secundario y
    best-effort**, porque `X-Forwarded-For` se puede mentir — el que sostiene
    la seguridad es el de email.
    Y en el mismo camino: cuando el email no existe se hashea igual contra
    `seguridad.HASH_DE_DESCARTE`. El mensaje de error ya era el mismo para los
    dos casos a propósito, pero volver sin hashear los distinguía por RELOJ
    (~200 ms contra ~0), que enumera cuentas igual.

19. **El instalador de Windows no propone el disco C.** Pedido del dueño.
    `assets/marca/instalador.nsh` (enganchado con `nsis.include`) busca un
    disco de datos y lo propone. Tres guardas que no se sacan: **sólo discos
    fijos** (`GetDrives "HDD"` — instalar en un pendrive que mañana no está
    deja un acceso directo roto y un desinstalador que no desinstala);
    **prueba de escritura real** antes de elegirlo (no hay administrador:
    `perMachine: false`); y **no pisa una instalación existente** (en una
    actualización movería el programa de lugar y dejaría la copia vieja
    ocupando disco). Si la máquina tiene un solo disco **cae en C:**, y tiene
    que ser así: un instalador que se planta porque no encontró un `D:` no
    instala en la mayoría de las computadoras. Un `.nsh` tampoco se prueba
    leyéndolo: `tests/test_escritorio.py` lo COMPILA con `makensis`.

20. **El archivo que se baja es el mismo para todos; lo que cambia es la
    cuenta.** Corolario de la regla 15, escrito porque el pedido vuelve: no
    hay un `.exe` de Gold y otro de gratis, y no puede haberlo — un binario no
    hace cumplir un plan (se lo parchea, o se pasa el link por WhatsApp), y
    sostener el plan en el cliente es el mismo agujero que ya se tapó en los
    pagos (regla 14). Lo que SÍ se hace: la descarga **exige sesión** y queda
    atribuida a la cuenta con el plan **congelado en ese momento**
    (`panel.registrar_descarga`), y el dueño lo ve en Panel → *Cliente por
    cliente*. Congelarlo importa: leyendo el plan actual, quien hoy es Gold
    parecería haberlo sido siempre y se pierde el dato que sirve — que bajó
    siendo gratis y pagó después. Lo fija
    `tests/test_descargas_por_cliente.py`.

21. **Las cuentas del dueño no cuentan como clientes que pagan.** Están en Gold
    porque `duenio.py` se las pone. Contándolas, el panel mostraba
    "Pagando: 2 · 66,67% de conversión" al lado de "Facturado: USD 0" — dos
    números que se contradicen en la misma pantalla, y el equivocado era el
    que uno mira para decidir si el negocio funciona. `panel._planes` las saca
    del numerador Y del denominador, y devuelve `del_duenio` para que la UI
    diga cuántas sacó en vez de esconderlas.

22. **Un CI que no corre es peor que no tener CI.** `ci.yml` estuvo filtrado a
    `branches: [main]`. Hubo una rama `main` —los PR #1 y #2 se mergearon ahí
    el 14 de agosto y el CI corrió— pero después **desapareció**: hoy la única
    rama es la de trabajo, que además es la rama por defecto. Desde entonces,
    cada push se salteó el linter y los 400+ tests **en silencio**, y la
    pestaña Actions sin corridas nuevas se leía como "no pasó nada malo".
    Un filtro por nombre de rama es una bomba de tiempo: la rama se renombra o
    se borra y el CI se apaga sin avisar. Por eso ahora es `["**"]`. Ahora es `branches: ["**"]`, igual
    que `apps.yml`, y el CI instala NSIS para que el test del instalador
    compile de verdad en vez de saltearse. Lo fija `tests/test_ci.py`, que
    también prohíbe que vuelva `api.matcher.app` — un dominio de ejemplo que
    nunca se registró y que seguía como respaldo del `VITE_API_URL` de
    `apps.yml`, o sea que **cada APK que salió del CI se compiló contra un
    servidor inexistente** y moría con "Failed to fetch" en el login.

23. **Las consultas de la ruta caliente no barren la tabla.** `matches` y
    `pagos` crecen con el uso y no paran. Tres consultas hacían SCAN completo,
    medido con 40.000 filas: el pago por referencia —que corre en **cada
    webhook**— pasó de 1,637 ms a 0,003 ms (565x); "mis matches", que se abre
    al entrar a la app, de 2,405 ms a 0,157 ms (15x); "mis pagos", 13x.
    `matches` ya tenía `UNIQUE(a_id, b_id)`, que cubre el lado `a_id`; el que
    faltaba era el lado `b_id` del `OR`, y "mis matches" pregunta por los dos.
    Lo fija `tests/test_indices.py`, que mira el **plan de ejecución** y no los
    milisegundos: un test que cronometra falla solo el día que el CI está
    ocupado, y entonces se lo ignora para siempre.

24. **El SVG entra sólo del lado de adentro.** Un SVG no es una imagen como
    las otras: es un documento XML que puede traer `<script>`. En un `<img>` no
    se ejecuta, pero basta abrir la URL en una pestaña —o que un cliente futuro
    la meta en un `<object>`— para que sea XSS con la cara de una foto de
    perfil. La app SÍ genera SVG (`avatares.py`, el avatar de respaldo cuando
    no hay pack de caras), y por eso `medios.agregar_foto` tiene
    `confiable=True`: lo pasa `demo.py`, **nunca un handler HTTP**. Hay un test
    que falla si aparece `confiable=True` en `api.py`.
    Ojo con el orden en que se descubre esto: apretar la validación de
    `data:` rompió la siembra de la demo, y la tentación es agregar
    `image/svg+xml` a la lista general. Eso reabre el agujero para lo que sube
    la gente, que es justo lo que se estaba cerrando.

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
