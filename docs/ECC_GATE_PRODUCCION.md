# Matcher — Gate de producción ECC

> Puntaje bajo la rúbrica de `.claude/skills/ecc/SKILL.md` (ECC v2.2.0,
> skill `production-audit`). **Evidencia ejecutada o no cuenta.**

**Veredicto: 78/100 → 8/10. Sale con salvedades. El código está sano —527 tests
verdes y linter limpio— pero el repositorio tiene un problema de forma que
frena la nota: la rama por defecto no tiene commits.**

## Evidencia ejecutada

| Verificación | Comando | Resultado |
|---|---|---|
| Linter | `ruff check .` | ✅ `All checks passed!` |
| Suite Python | `python3 -m pytest -q tests/` | ✅ **527 tests, 0 fallas**, 2 skip |
| Secretos versionados | `git ls-files \| grep -E '\.env$\|\.pem\|\.keystore'` | ✅ ninguno |

## El tope: no hay rama por defecto con contenido

`master` —la rama por defecto del repositorio— **no tiene ni un commit**. Todo
el producto vive en `claude/dating-app-mvp-h38hie`, una rama de trabajo.

Eso rompe cosas concretas, no es cosmético:

- **No se puede abrir un PR contra la rama por defecto**, porque no hay base
  contra la cual comparar. Cualquier revisión de código queda sin lugar donde
  pasar.
- **Quien clona el repo se lleva un directorio vacío.** Un colaborador nuevo,
  un runner de CI apuntando a `main`, o un deploy que sigue la rama por
  defecto no encuentran nada.
- **No hay línea estable.** Si la rama de trabajo se renombra o se borra, el
  producto se va con ella.

Por eso la rúbrica no pasa de 8/10 acá: el producto anda, pero el repositorio
no está en condiciones de sostenerlo como algo que se vende y se mantiene.

Nota: este PR se abre contra `claude/dating-app-mvp-h38hie` justamente porque
no hay otra base posible.

## Arreglos de alto valor (en orden)

1. **Promover el contenido a la rama por defecto.** Mergear
   `claude/dating-app-mvp-h38hie` a `main` (o renombrarla a `main` y ponerla
   como default en la configuración del repositorio). Es el arreglo que
   desbloquea todo lo demás y son cinco minutos.
2. **Revisar los dos tests salteados.** Un skip permanente no cuida nada.
3. **Sumar E2E de navegador.** El producto tiene frontend (React + Capacitor
   + Electron) y nada recorre la pantalla del usuario.

## Evidencia faltante

- Los jobs `frontend` (build de Vite) y `demo` (humo: el servidor levanta y
  responde) de `ci.yml` no se corrieron acá. El job `motor` sí, y está verde.
- Ninguna corrida de CI en GitHub para esta rama.

## Próxima acción

Promover la rama a `main` y volver a puntuar: con eso solo, el repo pasa a
9/10 sin tocar una línea de código.
