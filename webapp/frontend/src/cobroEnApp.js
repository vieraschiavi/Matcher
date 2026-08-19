// ¿Se puede cobrar una suscripción DENTRO de la app instalada?
//
// La respuesta corta es NO, y no es un problema del código: es política de las
// tiendas. Apple (guía 3.1.1) y Google Play (Payments policy) exigen que una
// suscripción digital comprada dentro de la app pase por SU sistema de cobro.
// Una app de citas que abre MercadoPago, PayPal o Stripe adentro es un rechazo
// en la revisión — no un "puede que pase", es la causal que más rechazos junta.
//
// Las pasarelas que están implementadas en `matcher/pagos.py` son correctas y
// sirven, pero **sólo en la web**. Ahí no hay intermediario y la comisión es
// del 5 % en vez del 15 %.
//
// Entonces la app instalada, por defecto, NO vende: muestra los planes para
// que se entienda qué ofrece cada uno, y si la persona ya se suscribió en la
// web su plan funciona igual adentro de la app. Eso pasa revisión en cualquier
// tienda y en cualquier país.
//
// Las dos formas de vender desde la app, cuando llegue el momento:
//
// 1. **Google Play Billing / StoreKit.** Es el camino que las tiendas quieren.
//    Cuesta 15 % (hasta USD 1M/año) y hay que implementar el plugin nativo y
//    validar el recibo del lado del servidor. Es trabajo real, y no se puede
//    ni probar sin la cuenta de desarrollador paga.
// 2. **Enlace de salida al cobro web.** Depende del país: la UE (DMA), Estados
//    Unidos y —para apps de citas específicamente— Países Bajos lo permiten
//    con condiciones; en el resto sigue siendo causal de rechazo. Por eso está
//    detrás de una bandera apagada: encenderla es una decisión con riesgo, y
//    tiene que ser explícita.
//
// Se enciende compilando con VITE_PAGOS_EN_APP=1. En la web no cambia nada.

import { esNativo } from "./api";

const PERMITIDO_POR_BANDERA = import.meta.env.VITE_PAGOS_EN_APP === "1";

/** ¿Esta pantalla puede mostrar un botón de compra? */
export function sePuedeCobrarAca() {
  return !esNativo || PERMITIDO_POR_BANDERA;
}

/** ¿Hay que explicar por qué no se puede comprar acá? */
export function hayQueExplicarElCobro() {
  return esNativo && !PERMITIDO_POR_BANDERA;
}
