# Plan de marketing, inversión y rentabilidad · Matcher

> **Archivo generado.** Sale de `marketing/modelo_negocio.py`.
> No lo edites a mano: cambiá el supuesto y corré
> `python3 -m marketing.modelo_negocio`.

---

## Leelo con esto en la cabeza

Esto es un **modelo**, no un pronóstico. Ninguno de los supuestos está
medido sobre Matcher, porque Matcher todavía no tuvo un usuario real: son
rangos razonables de mercado para una app de citas chica y sin marca. El
valor del ejercicio no es el número final, es ver **qué supuesto manda el
resultado** — y en los tres escenarios es el mismo: el churn del
suscriptor contra el costo de traer al usuario.

Los precios de la competencia que aparecen en la app
(`planes.REFERENCIA_COMPETENCIA`) están marcados `verificado: False` y
acá se aplica el mismo criterio: **verificá antes de publicar una
campaña que use estos números.**

## 1. Qué se cobra, y qué queda

Los precios salen de `matcher/planes.py` — la misma fuente que usa la app.

| Plan | Mensual | Anual | Equivalente mensual del anual |
|---|---:|---:|---:|
| Matcher Plus | USD 3,99 | USD 29,90 | USD 2,49 |
| Matcher Gold | USD 7,99 | USD 59,90 | USD 4,99 |

### La comisión de las tiendas no es negociable

Apple (guía 3.1.1) y Google exigen que una suscripción digital comprada
**dentro de la app** pase por su cobro. La pasarela propia
(MercadoPago / dLocal / PayPal) que ya está implementada sólo es válida en
**la web**. Con el Small Business Program de Apple y el tramo equivalente
de Google, la comisión es **15 %** mientras la facturación anual del
desarrollador no pase USD 1.000.000; arriba de eso, **30 %**.

| Plan | Precio | Neto en tienda (15 %) | Neto en tienda (30 %) | Neto en web (5,4 %) |
|---|---:|---:|---:|---:|
| Matcher Plus | USD 3,99 | USD 3,39 | USD 2,79 | USD 3,77 |
| Matcher Gold | USD 7,99 | USD 6,79 | USD 5,59 | USD 7,56 |

**Consecuencia comercial directa:** cada suscripción que se logra empujar
a la web en vez de la tienda deja ~10 puntos más. Por eso el modelo tiene
un supuesto explícito de qué parte de los pagos pasa por cada canal, y por
eso conviene que la web tenga su propio embudo de cobro.

## 2. Inversión: qué hay que pagar sí o sí

### Único, antes de publicar

| Concepto | USD | Nota |
|---|---:|---|
| Alta de desarrollador en Google Play | 25 | pago único, de por vida |
| Política de privacidad y términos revisados | 250 | obligatoria en ambas tiendas |
| Clave de firma (keystore) | 0 | se genera, pero **si se pierde no se puede volver a publicar la app** |
| Registro de base de datos ante la URCDP (Uruguay, Ley 18.331) | 0 | trámite, sin arancel |
| Mac para compilar iOS | 600–1.400 | de segunda mano sirve; **no hay forma de compilar iOS sin eso** |

### Recurrente

| Concepto | USD | Frecuencia |
|---|---:|---|
| Cuenta Apple Developer | 99 | por año |
| Dominio | 15 | por año |
| Backend con disco (Fly.io / Render) | 12 → 900 | por mes, según padrón |
| Correo transaccional | 10 | por mes |
| Contador (unipersonal en Uruguay) | 60 | por mes |
| Almacenamiento y tráfico de fotos | variable | por mes, ver abajo |
| Moderación | variable | por mes, **no es opcional** |

### El costo del que nadie habla: moderación

Una app de citas sin moderación de fotos y de chat se llena de abuso en la
primera semana, y es causal de baja tanto en Play como en App Store. Hoy
Matcher tiene reportes pero **no tiene revisión** (ver `docs/PUBLICAR.md`).
El modelo lo cotiza así:

- Análisis automático de imagen: USD 0,0015 por foto, 4 fotos por alta.
- Revisión humana de altas y reportes: 1 hora cada 300 altas.
- Soporte y denuncias: 1 hora cada 2.000 usuarios activos.
- Hora humana: USD 15.

### Almacenamiento de fotos

Hoy las fotos viajan como data-URI **dentro de la base**. Para usuarios
reales van a un bucket con URLs firmadas. El modelo cotiza
1,8 MB acumulados por usuario a USD 0,023/GB-mes y 60 MB de tráfico por usuario y mes a USD 0,09/GB.

## 3. Los tres escenarios

**Pesimista.** La app funciona pero no engancha: la conversión se queda en el piso del mercado, el boca a boca no arranca y hay que comprar cada usuario.

**Base.** El caso realista: se domina una zona chica (un barrio, una ciudad universitaria), la densidad alcanza para que haya matches y una parte del crecimiento se vuelve orgánica.

**Optimista.** El diferencial pega: 'los filtros se respetan y sale una fracción' se vuelve el argumento de prensa y de boca a boca. Conversión alta por precio bajo y churn contenido.

| Supuesto | Pesimista | Base | Optimista |
|---|---:|---:|---:|
| Costo por instalación (CPI) | USD 1,60 | USD 1,20 | USD 0,90 |
| Instalaciones que se registran | 35,0 % | 45,0 % | 55,0 % |
| Altas orgánicas base por mes | 120 | 300 | 700 |
| Altas extra por usuario activo/mes (boca a boca) | 0,010 | 0,025 | 0,055 |
| Un gratis empieza a pagar (por mes) | 0,6 % | 1,5 % | 2,2 % |
| De cada 100 registrados, llegan a pagar | 2,0 % | 6,4 % | 12,1 % |
| Padrón activo que paga (estado estable) | 1,3 % | 4,5 % | 9,1 % |
| Baja mensual del padrón | 30,0 % | 22,0 % | 16,0 % |
| Baja mensual del suscriptor | 45,0 % | 32,0 % | 22,0 % |
| Vida media del suscriptor | 2,2 meses | 3,1 meses | 4,5 meses |
| Mezcla Gold | 20,0 % | 28,0 % | 35,0 % |
| Pagan plan anual | 10,0 % | 18,0 % | 30,0 % |
| Pagos por tienda (vs. web) | 85,0 % | 80,0 % | 72,0 % |
| ARPU bruto por suscriptor/mes | USD 4,61 | USD 4,76 | USD 4,78 |
| ARPU **neto** de comisión | USD 3,98 | USD 4,14 | USD 4,19 |
| LTV del suscriptor | USD 8,86 | USD 12,94 | USD 19,06 |
| CAC por usuario registrado | USD 4,57 | USD 2,67 | USD 1,64 |
| CAC por **pagador** | USD 233 | USD 42 | USD 14 |
| LTV / CAC del pagador | 0,04 | 0,31 | 1,41 |

### Lo primero que hay que mirar de esa tabla

La fila **LTV / CAC del pagador**. Es la relación entre lo que deja un
suscriptor en toda su vida y lo que cuesta conseguirlo comprando pauta.
Un negocio de suscripción necesita **3 o más**. Acá:

- **Pesimista:** 0,04 → **cada usuario comprado pierde plata**.
- **Base:** 0,31 → **cada usuario comprado pierde plata**.
- **Optimista:** 1,41 → la pauta se banca apenas, sin margen.

Por eso el presupuesto de pauta de los tres escenarios arranca chico. La
plata en publicidad no compra un negocio: lo compra el crecimiento
orgánico, que en el modelo entra por `organicos_base` y `factor_viral`.

## 4. Plan de marketing: en qué se gasta

### La restricción que define todo: la liquidez local

Una app de citas no es un producto que se usa solo — necesita gente del
otro lado. 5.000 usuarios repartidos por el mundo no sirven; 800 en una
misma ciudad sí. Y hay un segundo problema conocido del rubro: el padrón
se inclina 65/35 o 70/30 hacia los hombres, y una app con esa proporción
deja de funcionar para todos. **La inversión de marketing no se reparte
por igual: se concentra en un radio chico y sesgada hacia el lado que
falta.**

### Reparto sugerido del presupuesto mensual

| Partida | % | Para qué |
|---|---:|---|
| Pauta geolocalizada (Instagram/TikTok, radio de pocos km) | 40 % | única pauta con sentido: densidad, no alcance |
| Micro-creadores locales (1k–30k seguidores) | 25 % | costo por instalación mucho menor que la pauta fría |
| Acciones presenciales (facultades, gimnasios, boliches, ferias) | 20 % | es lo que resuelve la liquidez y el sesgo de género |
| Prensa y contenido propio (el ángulo 'los filtros se respetan') | 10 % | orgánico, se compone con el tiempo |
| ASO: capturas, video, palabras clave, traducciones | 5 % | la instalación más barata es la que ya te estaba buscando |

### El mensaje

El producto tiene dos diferenciales reales y son los dos titulares:

1. **Los filtros se respetan.** Es la queja más repetida de las reseñas de
   las apps grandes: pagar y sentir que el algoritmo igual te muestra
   cualquier cosa. En Matcher `filtros.py` descarta y `scoring.py` sólo
   ordena — es una diferencia demostrable, no un eslogan.
2. **Todos los filtros están en el plan gratis.** La competencia cobra el
   derecho a filtrar; acá se cobra volumen y visibilidad.

A eso se suman los ganchos de producto: **Crush Time** (adivinar quién te
dio like entre 4), **cita a ciegas** (las fotos aparecen recién después de
hablar) y el **radar** con mapa.

### Lo que NO hay que hacer

- Pauta nacional o continental antes de tener una zona chica funcionando:
  es comprar usuarios que no van a tener con quién hablar.
- Comparar precios contra la competencia en la campaña sin verificar esos
  precios primero (`REFERENCIA_COMPETENCIA` está sin verificar a propósito).
- Prometer cantidad de usuarios o de matches. No se puede sostener.

## 5. Rentabilidad neta a 3, 6, 9, 12, 18 y 24 meses

«Neto» acá significa: ingreso menos comisión de tienda o pasarela, menos
todos los costos, menos IRAE (25,0 % sobre el resultado del ejercicio,
compensando pérdidas anteriores como permite la ley uruguaya). **No
descuenta el trabajo propio** — eso va aparte, al final.

| Escenario | Mes 3 | Mes 6 | Mes 9 | Mes 12 | Mes 18 | Mes 24 |
|---|---:|---:|---:|---:|---:|---:|
| **Pesimista** (acumulado) | USD -1.236 | USD -2.674 | USD -4.091 | USD -5.498 | USD -8.402 | USD -11.204 |
| **Base** (acumulado) | USD -1.429 | USD -3.033 | USD -6.114 | USD -8.795 | USD -17.989 | USD -25.992 |
| **Optimista** (acumulado) | USD -1.622 | USD -3.074 | USD -6.877 | USD -6.624 | USD -8.175 | USD 9.700 |
| Pesimista (ese mes) | USD -284 | USD -476 | USD -471 | USD -468 | USD -467 | USD -467 |
| Base (ese mes) | USD -316 | USD -492 | USD -977 | USD -857 | USD -1.414 | USD -1.295 |
| Optimista (ese mes) | USD -267 | USD -204 | USD -865 | USD 549 | USD 1.499 | USD 3.563 |

| Escenario | Primer mes en verde | Recupera todo lo invertido | Peor pozo |
|---|---:|---:|---:|
| **Pesimista** | no llega en 24 meses | no llega en 24 meses | USD -11.204 |
| **Base** | no llega en 24 meses | no llega en 24 meses | USD -25.992 |
| **Optimista** | mes 11 | mes 21 | USD -10.606 |

Si ves que el acumulado mejora y después vuelve a empeorar, no es un error
del cálculo: es el escalón de presupuesto del mes 13, cuando la pauta
aumenta. Cada vez que se sube el gasto de adquisición, el negocio vuelve a
perder plata hasta que la cohorte comprada madura. Es exactamente el
motivo por el que subir el presupuesto no es una palanca gratis.

## 6. Desglose mes a mes

### Pesimista

| Mes | Altas | Padrón activo | Suscriptores | Ingreso bruto | Ingreso neto | Marketing | Infra | Moderación | Fijos | IRAE | Resultado | Acumulado |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 164 | 164 | 1 | 5 | 4 | 200 | 23 | 10 | 435 | 0 | -665 | -665 |
| 2 | 165 | 280 | 2 | 10 | 9 | 200 | 24 | 11 | 61 | 0 | -287 | -952 |
| 3 | 167 | 363 | 3 | 16 | 13 | 200 | 24 | 12 | 61 | 0 | -284 | -1.236 |
| 4 | 211 | 465 | 5 | 21 | 18 | 400 | 25 | 15 | 61 | 0 | -483 | -1.718 |
| 5 | 212 | 538 | 6 | 26 | 23 | 400 | 25 | 16 | 61 | 0 | -479 | -2.198 |
| 6 | 213 | 589 | 7 | 31 | 27 | 400 | 25 | 16 | 61 | 0 | -476 | -2.674 |
| 7 | 213 | 626 | 7 | 34 | 29 | 400 | 25 | 17 | 61 | 0 | -474 | -3.148 |
| 8 | 214 | 652 | 8 | 37 | 32 | 400 | 26 | 17 | 61 | 0 | -472 | -3.620 |
| 9 | 214 | 670 | 8 | 38 | 33 | 400 | 26 | 17 | 61 | 0 | -471 | -4.091 |
| 10 | 214 | 683 | 9 | 40 | 34 | 400 | 26 | 17 | 61 | 0 | -470 | -4.560 |
| 11 | 214 | 693 | 9 | 41 | 35 | 400 | 26 | 17 | 61 | 0 | -469 | -5.029 |
| 12 | 214 | 699 | 9 | 42 | 36 | 400 | 26 | 17 | 61 | 0 | -468 | -5.498 |
| 13 | 214 | 704 | 9 | 42 | 36 | 400 | 26 | 17 | 160 | 0 | -567 | -6.065 |
| 14 | 215 | 707 | 9 | 42 | 37 | 400 | 26 | 17 | 61 | 0 | -468 | -6.532 |
| 15 | 215 | 710 | 9 | 43 | 37 | 400 | 26 | 17 | 61 | 0 | -468 | -7.000 |
| 16 | 215 | 711 | 9 | 43 | 37 | 400 | 26 | 17 | 61 | 0 | -467 | -7.467 |
| 17 | 215 | 713 | 9 | 43 | 37 | 400 | 26 | 17 | 61 | 0 | -467 | -7.934 |
| 18 | 215 | 713 | 9 | 43 | 37 | 400 | 26 | 17 | 61 | 0 | -467 | -8.402 |
| 19 | 215 | 714 | 9 | 43 | 37 | 400 | 26 | 17 | 61 | 0 | -467 | -8.869 |
| 20 | 215 | 714 | 9 | 43 | 37 | 400 | 26 | 17 | 61 | 0 | -467 | -9.336 |
| 21 | 215 | 715 | 9 | 43 | 37 | 400 | 26 | 17 | 61 | 0 | -467 | -9.803 |
| 22 | 215 | 715 | 9 | 43 | 37 | 400 | 26 | 17 | 61 | 0 | -467 | -10.270 |
| 23 | 215 | 715 | 9 | 43 | 37 | 400 | 26 | 17 | 61 | 0 | -467 | -10.737 |
| 24 | 215 | 715 | 9 | 43 | 37 | 400 | 26 | 17 | 61 | 0 | -467 | -11.204 |

### Base

| Mes | Altas | Padrón activo | Suscriptores | Ingreso bruto | Ingreso neto | Marketing | Infra | Moderación | Fijos | IRAE | Resultado | Acumulado |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 412 | 412 | 6 | 29 | 26 | 300 | 24 | 26 | 435 | 0 | -760 | -760 |
| 2 | 423 | 745 | 15 | 73 | 63 | 300 | 26 | 29 | 61 | 0 | -353 | -1.113 |
| 3 | 431 | 1.012 | 25 | 121 | 105 | 300 | 28 | 32 | 61 | 0 | -316 | -1.429 |
| 4 | 550 | 1.340 | 37 | 176 | 153 | 600 | 29 | 41 | 61 | 0 | -578 | -2.007 |
| 5 | 558 | 1.603 | 49 | 232 | 201 | 600 | 31 | 43 | 61 | 0 | -534 | -2.541 |
| 6 | 565 | 1.816 | 60 | 284 | 247 | 600 | 32 | 45 | 61 | 0 | -492 | -3.033 |
| 7 | 795 | 2.212 | 73 | 347 | 301 | 1.200 | 57 | 61 | 61 | 0 | -1.078 | -4.111 |
| 8 | 805 | 2.530 | 86 | 411 | 358 | 1.200 | 59 | 64 | 61 | 0 | -1.026 | -5.137 |
| 9 | 813 | 2.787 | 99 | 473 | 411 | 1.200 | 60 | 66 | 61 | 0 | -977 | -6.114 |
| 10 | 820 | 2.993 | 111 | 528 | 459 | 1.200 | 61 | 68 | 61 | 0 | -932 | -7.046 |
| 11 | 825 | 3.160 | 121 | 577 | 502 | 1.200 | 62 | 70 | 61 | 0 | -892 | -7.938 |
| 12 | 829 | 3.294 | 130 | 619 | 538 | 1.200 | 63 | 71 | 61 | 0 | -857 | -8.795 |
| 13 | 1.132 | 3.701 | 142 | 676 | 588 | 2.000 | 65 | 91 | 160 | 0 | -1.729 | -10.523 |
| 14 | 1.143 | 4.030 | 155 | 738 | 641 | 2.000 | 67 | 94 | 61 | 0 | -1.581 | -12.105 |
| 15 | 1.151 | 4.294 | 167 | 797 | 693 | 2.000 | 68 | 97 | 61 | 0 | -1.533 | -13.638 |
| 16 | 1.157 | 4.507 | 179 | 852 | 741 | 2.000 | 70 | 99 | 61 | 0 | -1.489 | -15.126 |
| 17 | 1.163 | 4.678 | 189 | 901 | 783 | 2.000 | 70 | 100 | 61 | 0 | -1.449 | -16.575 |
| 18 | 1.167 | 4.816 | 198 | 943 | 820 | 2.000 | 71 | 101 | 61 | 0 | -1.414 | -17.989 |
| 19 | 1.170 | 4.927 | 206 | 979 | 851 | 2.000 | 72 | 102 | 61 | 0 | -1.384 | -19.373 |
| 20 | 1.173 | 5.016 | 212 | 1.010 | 878 | 2.000 | 72 | 103 | 61 | 0 | -1.359 | -20.732 |
| 21 | 1.175 | 5.088 | 217 | 1.035 | 900 | 2.000 | 73 | 104 | 61 | 0 | -1.338 | -22.070 |
| 22 | 1.177 | 5.146 | 222 | 1.056 | 918 | 2.000 | 73 | 105 | 61 | 0 | -1.321 | -23.391 |
| 23 | 1.179 | 5.192 | 225 | 1.073 | 933 | 2.000 | 73 | 105 | 61 | 0 | -1.306 | -24.698 |
| 24 | 1.180 | 5.230 | 228 | 1.088 | 945 | 2.000 | 73 | 105 | 61 | 0 | -1.295 | -25.992 |

### Optimista

| Mes | Altas | Padrón activo | Suscriptores | Ingreso bruto | Ingreso neto | Marketing | Infra | Moderación | Fijos | IRAE | Resultado | Acumulado |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1.006 | 1.006 | 22 | 106 | 93 | 500 | 27 | 64 | 435 | 0 | -934 | -934 |
| 2 | 1.061 | 1.906 | 59 | 281 | 246 | 500 | 32 | 74 | 61 | 0 | -421 | -1.355 |
| 3 | 1.110 | 2.711 | 104 | 498 | 437 | 500 | 60 | 83 | 61 | 0 | -267 | -1.622 |
| 4 | 1.582 | 3.860 | 164 | 784 | 687 | 1.200 | 66 | 118 | 61 | 0 | -758 | -2.380 |
| 5 | 1.646 | 4.888 | 232 | 1.108 | 972 | 1.200 | 72 | 129 | 61 | 0 | -490 | -2.869 |
| 6 | 1.702 | 5.808 | 303 | 1.451 | 1.272 | 1.200 | 77 | 139 | 61 | 0 | -204 | -3.074 |
| 7 | 2.853 | 7.731 | 400 | 1.913 | 1.678 | 3.000 | 87 | 218 | 61 | 0 | -1.688 | -4.762 |
| 8 | 2.959 | 9.453 | 511 | 2.445 | 2.144 | 3.000 | 96 | 237 | 61 | 0 | -1.250 | -6.012 |
| 9 | 3.053 | 10.994 | 629 | 3.010 | 2.639 | 3.000 | 190 | 253 | 61 | 0 | -865 | -6.877 |
| 10 | 3.138 | 12.373 | 749 | 3.583 | 3.142 | 3.000 | 197 | 269 | 61 | 0 | -385 | -7.262 |
| 11 | 3.214 | 13.607 | 867 | 4.148 | 3.637 | 3.000 | 204 | 282 | 61 | 0 | 90 | -7.173 |
| 12 | 3.282 | 14.711 | 981 | 4.692 | 4.114 | 3.000 | 210 | 294 | 61 | 0 | 549 | -6.624 |
| 13 | 5.176 | 17.533 | 1.129 | 5.401 | 4.736 | 6.000 | 225 | 421 | 160 | 0 | -2.071 | -8.694 |
| 14 | 5.331 | 20.059 | 1.297 | 6.205 | 5.441 | 6.000 | 239 | 449 | 61 | 0 | -1.309 | -10.003 |
| 15 | 5.470 | 22.320 | 1.474 | 7.051 | 6.183 | 6.000 | 251 | 474 | 61 | 0 | -603 | -10.606 |
| 16 | 5.594 | 24.343 | 1.653 | 7.906 | 6.933 | 6.000 | 262 | 496 | 61 | 0 | 113 | -10.493 |
| 17 | 5.706 | 26.153 | 1.828 | 8.745 | 7.668 | 6.000 | 272 | 516 | 61 | 0 | 819 | -9.674 |
| 18 | 5.805 | 27.774 | 1.997 | 9.551 | 8.375 | 6.000 | 281 | 533 | 61 | 0 | 1.499 | -8.175 |
| 19 | 5.894 | 29.224 | 2.157 | 10.314 | 9.044 | 6.000 | 289 | 549 | 61 | 0 | 2.145 | -6.030 |
| 20 | 5.974 | 30.522 | 2.306 | 11.030 | 9.672 | 6.000 | 296 | 563 | 61 | 0 | 2.751 | -3.279 |
| 21 | 6.045 | 31.684 | 2.445 | 11.694 | 10.254 | 6.000 | 302 | 576 | 61 | 9 | 3.306 | 26 |
| 22 | 6.109 | 32.724 | 2.573 | 12.307 | 10.792 | 6.000 | 308 | 588 | 61 | 959 | 2.876 | 2.903 |
| 23 | 6.166 | 33.655 | 2.691 | 12.870 | 11.285 | 6.000 | 313 | 598 | 61 | 1.078 | 3.235 | 6.138 |
| 24 | 6.218 | 34.488 | 2.799 | 13.384 | 11.736 | 6.000 | 318 | 607 | 61 | 1.188 | 3.563 | 9.700 |

## 7. Cuántos clientes hacen falta

Dos preguntas distintas, y conviene no mezclarlas:

- **Suscriptores activos**: cuántos tienen que estar pagando ese mes para
  cubrir los costos de ese mes.
- **Padrón activo**: cuánta gente usando la app hace falta para que salgan
  esos suscriptores, dado que sólo una parte paga.
- **Altas nuevas por mes**: cuántos registros nuevos hacen falta para
  sostener ese padrón, dado que se va gente todos los meses. En estado
  estable: `altas = padrón × baja mensual del padrón`.

### Pesimista

ARPU neto: **USD 3,98** por suscriptor y mes · paga el **1,3 %** del padrón · baja del suscriptor **45,0 %**/mes · baja del padrón **30,0 %**/mes.

| Corte | Costo del mes | Suscriptores necesarios | Los que habría | Padrón necesario | El que habría | Altas/mes necesarias | Las que habría |
|---:|---:|---:|---:|---:|---:|---:|---:|
| Mes 3 | USD 297 | 75 | 3 | 5.670 | 363 | 1.701 | 167 |
| Mes 6 | USD 503 | 126 | 7 | 9.589 | 589 | 2.877 | 213 |
| Mes 9 | USD 504 | 126 | 8 | 9.611 | 670 | 2.883 | 214 |
| Mes 12 | USD 504 | 127 | 9 | 9.618 | 699 | 2.885 | 214 |
| Mes 18 | USD 505 | 127 | 9 | 9.622 | 713 | 2.887 | 215 |
| Mes 24 | USD 505 | 127 | 9 | 9.622 | 715 | 2.887 | 215 |

Y el número que de verdad importa, porque no depende de cuánto se
gaste en pauta: **cuánto hace falta para cubrir sólo la estructura**,
si el crecimiento fuera 100 % orgánico.

- Costo de estructura en el mes 12, sin un peso de marketing: **USD 104**.
- Suscriptores necesarios: **26**.
- Padrón activo necesario: **1.989** personas usando la app.
- Altas nuevas por mes para sostenerlo: **597**.

### Base

ARPU neto: **USD 4,14** por suscriptor y mes · paga el **4,5 %** del padrón · baja del suscriptor **32,0 %**/mes · baja del padrón **22,0 %**/mes.

| Corte | Costo del mes | Suscriptores necesarios | Los que habría | Padrón necesario | El que habría | Altas/mes necesarias | Las que habría |
|---:|---:|---:|---:|---:|---:|---:|---:|
| Mes 3 | USD 420 | 102 | 25 | 2.268 | 1.012 | 499 | 431 |
| Mes 6 | USD 738 | 178 | 60 | 3.982 | 1.816 | 876 | 565 |
| Mes 9 | USD 1.388 | 335 | 99 | 7.485 | 2.787 | 1.647 | 813 |
| Mes 12 | USD 1.395 | 337 | 130 | 7.525 | 3.294 | 1.655 | 829 |
| Mes 18 | USD 2.234 | 539 | 198 | 12.047 | 4.816 | 2.650 | 1.167 |
| Mes 24 | USD 2.240 | 541 | 228 | 12.080 | 5.230 | 2.658 | 1.180 |

Y el número que de verdad importa, porque no depende de cuánto se
gaste en pauta: **cuánto hace falta para cubrir sólo la estructura**,
si el crecimiento fuera 100 % orgánico.

- Costo de estructura en el mes 12, sin un peso de marketing: **USD 195**.
- Suscriptores necesarios: **47**.
- Padrón activo necesario: **1.053** personas usando la app.
- Altas nuevas por mes para sostenerlo: **232**.

### Optimista

ARPU neto: **USD 4,19** por suscriptor y mes · paga el **9,1 %** del padrón · baja del suscriptor **22,0 %**/mes · baja del padrón **16,0 %**/mes.

| Corte | Costo del mes | Suscriptores necesarios | Los que habría | Padrón necesario | El que habría | Altas/mes necesarias | Las que habría |
|---:|---:|---:|---:|---:|---:|---:|---:|
| Mes 3 | USD 704 | 168 | 104 | 1.845 | 2.711 | 295 | 1.110 |
| Mes 6 | USD 1.477 | 352 | 303 | 3.873 | 5.808 | 620 | 1.702 |
| Mes 9 | USD 3.505 | 836 | 629 | 9.192 | 10.994 | 1.471 | 3.053 |
| Mes 12 | USD 3.565 | 850 | 981 | 9.352 | 14.711 | 1.496 | 3.282 |
| Mes 18 | USD 6.876 | 1.640 | 1.997 | 18.035 | 27.774 | 2.886 | 5.805 |
| Mes 24 | USD 6.986 | 1.666 | 2.799 | 18.324 | 34.488 | 2.932 | 6.218 |

Y el número que de verdad importa, porque no depende de cuánto se
gaste en pauta: **cuánto hace falta para cubrir sólo la estructura**,
si el crecimiento fuera 100 % orgánico.

- Costo de estructura en el mes 12, sin un peso de marketing: **USD 565**.
- Suscriptores necesarios: **135**.
- Padrón activo necesario: **1.483** personas usando la app.
- Altas nuevas por mes para sostenerlo: **237**.

## 8. Qué mover cambia el resultado (y qué no)

Sensibilidad sobre el escenario Base: se mueve **un solo** supuesto y se
mira el acumulado a 24 meses.

Acumulado a 24 meses del escenario Base tal cual: **USD -25.992**.

| Cambio | Acumulado a 24 meses | Diferencia |
|---|---:|---:|
| Churn del suscriptor −25 % (dura más) | USD -22.979 | +3.013 |
| Churn del suscriptor +25 % (dura menos) | USD -28.081 | -2.089 |
| Conversión a pago +50 % | USD -19.806 | +6.186 |
| Conversión a pago −50 % | USD -32.402 | -6.410 |
| Boca a boca × 2 | USD -25.002 | +990 |
| CPI +50 % (la pauta se encarece) | USD -28.142 | -2.150 |
| Doble presupuesto de pauta | USD -53.421 | -27.428 |
| Cero pauta (sólo orgánico) | USD 1.353 | +27.345 |
| Todos los pagos por la web (sin comisión de tienda) | USD -24.839 | +1.154 |
| Precio × 2 (con su efecto en conversión y churn) | USD -25.761 | +231 |
| Precio × 4 | USD -25.718 | +274 |

### La lectura

**La fila que hay que leer dos veces es la de cero pauta.** El mismo
escenario Base, sin gastar un peso en publicidad, termina en
**USD 1.353** a 24 meses contra **USD -25.992** con la
pauta puesta, y **USD -53.421** si se duplica. No es una paradoja: a
este precio, cada usuario comprado cuesta más de lo que va a dejar, así
que la publicidad no acelera el negocio, lo desangra más rápido.

Lo que sí mueve la aguja es el **churn** y el **boca a boca**: retener, y
que la gente traiga gente. Eso no se compra con plata — se compra con
densidad local y con que la app cumpla lo que promete. Que es,
literalmente, el diferencial del producto.

Y mover los pagos de la tienda a la web es, en plata, equivalente a una
mejora de conversión: son 10 puntos de comisión sobre cada peso cobrado.

## 9. ¿Alcanza con subir el precio para estar en verde desde el mes 6?

La pregunta es buena y el modelo la puede contestar en vez de opinar.
«Rentable desde el mes 6» se toma en serio: verde ese mes **y todos los
que siguen**, no un mes bueno suelto.

### Cómo se modela una suba de precio sin hacer trampa

Subir el precio no es gratis y el modelo tiene que decirlo. Cobrar más
espanta gente antes de que pague (elasticidad de conversión) y hace que el
que ya paga aguante menos (elasticidad de churn). Un modelo que sube el
precio dejando la conversión quieta siempre «demuestra» que hay que cobrar
más, y es mentira. Acá se asume elasticidad **0,8**:
al doble de precio, la conversión cae a poco más de la mitad. Menos de 1
porque Matcher se compara contra una competencia mucho más cara, así que
aguanta algo de suba antes de que la gente se vaya.

### La respuesta corta: no, y el precio no es el problema

| Escenario | Precio mínimo para estar en verde desde el mes 6 (con la pauta del plan) |
|---|---|
| Pesimista | **No se llega**, ni multiplicando el precio por 12 (Plus a USD 47,88) |
| Base | **No se llega**, ni multiplicando el precio por 12 (Plus a USD 47,88) |
| Optimista | **No se llega**, ni multiplicando el precio por 12 (Plus a USD 47,88) |

Por qué. En el mes 6 del escenario Base el costo se reparte así:

- Marketing: **USD 600** de un costo total de USD 738.
- Todo lo demás (infra, moderación, fijos): USD 138.
- Ingreso neto de ese mes: USD 247, de 60 suscriptores.

El agujero del mes 6 **es la pauta**, no el precio. Y subir el precio casi
no mueve el ingreso, porque lo que se gana por suscriptor se pierde en
suscriptores:

| Precio Plus | Conversión efectiva | Suscriptores en el mes 6 | Ingreso neto del mes 6 |
|---:|---:|---:|---:|
| USD 3,99 | 1,5 % | 60 | USD 247 |
| USD 5,99 | 1,1 % | 41 | USD 256 |
| USD 7,98 | 0,9 % | 32 | USD 261 |
| USD 15,96 | 0,5 % | 16 | USD 273 |
| USD 31,92 | 0,3 % | 8 | USD 280 |
| USD 47,88 | 0,2 % | 6 | USD 283 |

De USD 3,99 a USD 47,88 el ingreso del mes 6 se mueve una miseria. **No
hay precio que arregle un mes en el que se gastan USD 600 en publicidad
para conseguir 60 suscriptores.**

### La respuesta larga: el mes 6 en verde ya es alcanzable, y sin tocar el precio

La palanca que sí funciona es la otra: gastar menos en pauta.

| Escenario | Recorte de pauta para estar en verde desde el mes 6 | Sin pauta: primer mes en verde |
|---|---|---:|
| Pesimista | no alcanza ni recortando todo | nunca |
| Base | recortar **99,0 %** | mes 5 |
| Optimista | recortar **71,0 %** | mes 2 |

**El escenario Base, sin gastar un peso en publicidad, queda en verde
desde el mes 5 y no vuelve a rojo — con el precio de hoy, USD
3,99.** Lo que pedís ya se puede, y no
hace falta cobrar más para conseguirlo: hace falta no comprar usuarios que
cuestan más de lo que dejan.

### Y si igual querés subir el precio, cuál es el óptimo

Sobre el escenario Base sin pauta, barriendo el precio y quedándose con el
mejor acumulado a 24 meses:

| Precio Plus | Precio Gold | Suscriptores mes 24 | Acumulado 24 meses |
|---:|---:|---:|---:|
| USD 3,99 | USD 7,99 | 68 | USD 1.353 |
| USD 5,99 | USD 11,98 | 45 | USD 1.387 |
| USD 7,98 | USD 15,98 | 34 | USD 1.397 |
| USD 9,98 | USD 19,98 | 27 | USD 1.398 |
| USD 11,97 | USD 23,97 | 22 | USD 1.395 |
| USD 15,96 | USD 31,96 | 17 | USD 1.386 |
| USD 23,94 | USD 47,94 | 11 | USD 1.364 |

El óptimo cae en **× 2,35** —Plus a USD
9,38, Gold a USD 18,78— y
deja USD 1.398 contra USD 1.353 sin
tocar nada: **USD 45 de diferencia
en dos años.** Nada. La curva es tan chata que el precio, en este rango, es
casi indiferente para el resultado — y en cambio sí decide con qué
argumento salís a competir.

### Dónde se da vuelta esta conclusión

Todo esto depende de un número que **no está medido**: la elasticidad. Si
la gente fuera menos sensible al precio de lo que supone el modelo —cosa
posible, porque la competencia sale 4 veces más— subir convendría, y mucho:

| Elasticidad supuesta | Precio Plus óptimo | Acumulado 24 meses | Contra USD 1.353 sin tocar |
|---:|---:|---:|---:|
| 0,3 | USD 47,88 *(tope del barrido)* | USD 10.545 | +9.192 |
| 0,5 | USD 47,88 *(tope del barrido)* | USD 5.476 | +4.123 |
| 0,8 | USD 9,38 | USD 1.398 | +45 |
| 1,0 | USD 3,99 | USD 1.353 | +0 |
| 1,3 | USD 3,99 | USD 1.353 | +0 |

Las filas marcadas *(tope del barrido)* no son un óptimo sino el borde de
la búsqueda: con esa elasticidad al modelo le conviene seguir subiendo más
allá de donde tiene sentido mirar. Léelas como «convendría subir bastante»,
no como «cobrá USD 48».

O sea: **la respuesta a «¿subo el precio?» depende de un dato que hoy no
tenés, y que se puede medir.** Un test A/B de precio con usuarios reales
—mismo producto, dos precios, mirar conversión a 60 días— vale más que
cualquier cosa que diga esta tabla. Ese test cuesta cero: son dos precios
en la pantalla de planes.

### Lo que sí conviene hacer con el precio, cueste lo que cueste medirlo

1. **Empujar el plan anual.** Ya está: cobra por adelantado, elimina el
   churn mensual y esquiva la comisión si se paga por la web. Es la suba de
   ingreso por suscriptor más barata que hay, porque no toca el precio de
   lista.
2. **Mover pagos de la tienda a la web.** Son 10 puntos de comisión, que a
   estos volúmenes valen más que cualquier ajuste de precio.
3. **Si subís, subí poco y de una vez.** Hasta USD 5,99–7,99 el Plus seguís
   abajo de la mitad del más barato de la competencia (USD 15,99 de
   referencia, sin verificar), así que el argumento comercial se sostiene.
   Arriba de eso dejás de ser «lo mismo por una fracción» y pasás a competir
   de igual a igual con marcas que tienen mil veces tu presupuesto.

## 10. El costo que el modelo no cobra: tu tiempo

Ninguno de los números de arriba descuenta el trabajo propio. Si se
valorizara a USD 15 la hora:

| Escenario | Horas propias/mes | Costo a 24 meses | Acumulado 24m ya descontado |
|---|---:|---:|---:|
| Pesimista | 60 | USD 21.600 | USD -32.804 |
| Base | 80 | USD 28.800 | USD -54.792 |
| Optimista | 120 | USD 43.200 | USD -33.500 |

## 11. Conclusión honesta

1. **Con pauta paga, a este precio, el modelo no cierra.** Un suscriptor
   de Matcher deja entre USD 8,86 y USD 19,06 en toda su
   vida; comprar al pagador que lo genera cuesta más que eso en dos de los
   tres escenarios. La decisión comercial de ser barato es buena para el
   usuario y es el diferencial del producto, pero tiene una contracara que
   conviene mirar de frente: **elimina la publicidad paga como motor de
   crecimiento**. Con USD 4 de suscripción no se compra un usuario a USD 2
   y se gana plata; con los USD 16 que cobra Tinder, sí.
2. **Subir el precio no arregla eso** (sección 9). Con la pauta puesta no
   hay precio —ni multiplicando por 12— que ponga el mes 6 en verde,
   porque el agujero de ese mes es la publicidad. Y sin pauta, el mes 6
   ya está en verde con el precio de hoy. El precio decide con qué
   argumento salís a competir; el resultado lo decide otra cosa.
3. **El único camino que cierra es la densidad orgánica.** Una zona chica,
   presencia real, boca a boca. Es más lento y menos glamoroso que
   apretar 'aumentar presupuesto', y en este modelo es la diferencia entre
   terminar en USD 1.353 o en USD -25.992.
4. **Antes de gastar un peso en pauta hay tres cosas sin resolver** y
   están todas en `docs/PUBLICAR.md`: el backend efímero (las cuentas y
   las fotos se pierden en cada arranque en frío), la moderación
   inexistente y las fotos guardadas dentro de la base. Publicitar una app
   con esos tres problemas quema el dinero y la reputación a la vez: el
   usuario que se va por una mala primera impresión no vuelve.
5. **El orden correcto es**: backend con disco → moderación → 200 usuarios
   reales en un radio de pocos kilómetros → medir conversión y churn de
   verdad → recién ahí volver a este archivo, reemplazar los supuestos por
   lo medido y correrlo de nuevo. Ese, y no el número de hoy, es el
   propósito de este modelo.

