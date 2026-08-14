# Retratos de la demo

## Qué son

192 archivos: **96 personas × 2 tomas** (plano medio y primer plano), en
`mujer/` (57) y `hombre/` (39), 480×648 JPEG.

La proporción es la misma que la de la tarjeta del deck (4:5,4). No es un
detalle: con fotos más cuadradas, el `object-fit: cover` de la tarjeta recorta
arriba y abajo y les corta la cabeza.

**Ninguna de estas personas existe.** Son rostros sintéticos generados por una
red generativa (StyleGAN), obtenidos de `thispersondoesnotexist.com`. No hay
fotografías de personas reales en este repositorio y no debe haberlas: un
perfil de citas con la cara de alguien que no dio su consentimiento es una
identidad falsa, y eso vale también para el stock con licencia comercial — esa
licencia cubre publicidad, no hacer aparecer a esa persona como usuaria de una
app de citas.

## Criterio de selección

Se descargaron 112 rostros y se descartaron 16 manualmente por leerse como
menores de edad. Matcher es una app 18+ y ningún perfil, ni siquiera uno
sintético de demostración, puede mostrar a alguien que parezca menor.

Si volvés a generar el pack, **revisá las caras una por una** antes de
commitearlas. Es un paso manual a propósito: no hay clasificador acá y
automatizarlo sin verificar es exactamente cómo se cuela una.

## Antes de usarlo comercialmente

Verificá los términos vigentes de la fuente. El modelo StyleGAN de NVIDIA se
publicó bajo una licencia **no comercial**, y aunque las imágenes generadas no
representan a nadie real (con lo cual no hay derechos de imagen que pedir), la
situación de la salida del modelo no es la misma en todas las jurisdicciones.
Para una campaña o un lanzamiento pago, lo prolijo es un proveedor de rostros
sintéticos con licencia comercial explícita (Generated Photos y similares), o
una producción propia con gente que firmó.

Cambiar el pack no requiere tocar código: es una carpeta.

## Cómo se usan

`matcher/fotos.py` toma esta carpeta por defecto. Para apuntar a otra:

    MATCHER_FOTOS=/ruta/a/mis/fotos python3 -m matcher.demo datos/matcher.db

La carpeta puede tener subcarpetas `mujer/`, `hombre/`, `no_binario/`, o
imágenes sueltas (que se usan para cualquier género). Formatos: `.jpg`,
`.jpeg`, `.png`, `.webp`.

Para volver a los retratos ilustrados generados por código (sin ningún
archivo), usá `MATCHER_FOTOS=ninguna`.
