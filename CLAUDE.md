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
- **Android/iOS:** Capacitor · **Tests:** pytest · **Lint:** ruff

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

8. **Lo que decide el servidor no lo esconde el cliente.** "Quién me dio like"
   en el plan gratis devuelve `perfiles: []`, no los perfiles con un blur
   encima. Mandar los datos y taparlos con CSS es la fuga clásica de este
   feature; hay un test.

9. **Nada de promesas que no se pueden sostener.** Los precios de la
   competencia en `planes.REFERENCIA_COMPETENCIA` van marcados
   `verificado: False` y la UI muestra el aviso. La pasarela `demo` dice en
   pantalla que no mueve plata.

10. **El login externo no se simula.** Sin `GOOGLE_CLIENT_ID` y
    `GOOGLE_CLIENT_SECRET`, `oauth.disponibles()` devuelve vacío y el botón no
    aparece — nunca agregues un modo "demo" que finja un login, porque es una
    puerta abierta si se despliega. Tres cosas que no se tocan en `oauth.py`:
    el `state` es obligatorio, de un solo uso y con vencimiento; se exige
    `email_verified`; y el `id_token` **no se lee sin verificar la firma** (por
    eso los datos se piden al endpoint `userinfo`, no se parsea el JWT). El
    alta a medio hacer vive en `altas_pendientes`, no como perfil incompleto:
    un perfil a medias se cuela en consultas que no lo esperan.

## Convenciones
- Español rioplatense en el dominio y en los nombres de módulo, igual que
  MV Kobra AI y MV Cliente IA.
- Comentarios que expliquen **por qué**, no qué. Los que están dicen qué falló
  antes — no los borres al refactorizar.
- Un solo CSS para web, Android e iOS: `webapp/frontend/src/theme.css`. El modo
  móvil es un `@media (max-width: 860px)` del mismo archivo, no una hoja
  aparte — dos hojas se desincronizan a la semana.
- Los tokens de color base son los de Kobra (navy); el acento coral/violeta es
  propio de Matcher. No inventar colores nuevos fuera de `:root`.

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
