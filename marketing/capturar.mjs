// Capturas reales de la app, para el video y la landing.
//
// POR QUÉ ESTÁ ACÁ Y NO SON PNG SUELTOS COMMITEADOS A MANO
//
// Un video de demo hecho con capturas viejas miente: muestra una pantalla que
// ya no existe, con la paleta anterior y sin las funciones nuevas. Acá las
// capturas salen de la app corriendo de verdad, así que regenerarlas es correr
// esto de nuevo. Es la misma regla que el kit de marca (`generar_kit.py`): la
// pieza se genera, no se dibuja.
//
//   1. Levantá el backend:  python3 -m uvicorn webapp.backend.api:app --port 8899
//   2. node marketing/capturar.mjs [http://127.0.0.1:8899]
//
// Sale en `marketing/capturas/`. Lo consume `marketing/generar_video.py`.

import { chromium } from "playwright";
import { mkdirSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const AQUI = dirname(fileURLToPath(import.meta.url));
const BASE = process.argv[2] || "http://127.0.0.1:8899";
const SALIDA = resolve(AQUI, "capturas");

// El navegador de Playwright no siempre está donde `playwright` lo busca en un
// contenedor; si está en otro lado, se pasa por variable de entorno.
const CHROME =
  process.env.PLAYWRIGHT_CHROMIUM ||
  "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

// Teléfono, no escritorio: el 90 % de una app de citas se usa en el teléfono y
// un video con capturas de escritorio se ve como el de otro producto.
const PANTALLA = { width: 412, height: 900 };

const ESCENAS = [
  { id: "01-descubrir", ruta: "/descubrir", espera: ".carta" },
  { id: "02-filtros", ruta: "/filtros", espera: ".chip" },
  { id: "03-radar", ruta: "/radar", espera: ".mapa, .panel", pausa: 4500 },
  { id: "04-cruces", ruta: "/cruces", espera: ".panel" },
  { id: "05-crush", ruta: "/crush", espera: ".panel" },
  { id: "06-vitrinas", ruta: "/ranking", espera: ".panel", pausa: 3000 },
  { id: "07-likes", ruta: "/likes", espera: ".panel" },
  { id: "08-matches", ruta: "/matches", espera: ".panel" },
  { id: "09-planes", ruta: "/planes", espera: ".panel" },
  { id: "10-perfil", ruta: "/perfil", espera: ".panel" },
];

const esperar = (p, ms) => p.waitForTimeout(ms);

(async () => {
  if (!existsSync(SALIDA)) mkdirSync(SALIDA, { recursive: true });
  const nav = await chromium.launch({
    executablePath: existsSync(CHROME) ? CHROME : undefined,
    args: ["--no-sandbox"],
  });
  const ctx = await nav.newContext({
    viewport: PANTALLA,
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
    locale: "es-UY",
  });
  const p = await ctx.newPage();
  const errores = [];
  p.on("pageerror", (e) => errores.push("PAGEERROR " + e.message));

  await p.goto(BASE, { waitUntil: "networkidle" });
  await p.screenshot({ path: `${SALIDA}/00-entrar.png` });

  await p.getByRole("button", { name: /vieraschiavi/ }).click();
  await p.waitForSelector(".carta", { timeout: 40000 });
  await esperar(p, 2000);

  for (const e of ESCENAS) {
    await p.goto(`${BASE}/#${e.ruta}`, { waitUntil: "networkidle" });
    try {
      await p.waitForSelector(e.espera, { timeout: 15000 });
    } catch {
      console.log(`  (sin "${e.espera}" en ${e.ruta}, se captura igual)`);
    }
    await esperar(p, e.pausa || 2200);
    await p.screenshot({ path: `${SALIDA}/${e.id}.png` });
    console.log(`  ${e.id}`);
  }

  // La videollamada necesita un match: se responde un like de "Te gustaron",
  // que produce match en el acto porque esa gente ya te dio like.
  await p.goto(`${BASE}/#/likes`, { waitUntil: "networkidle" });
  await esperar(p, 2200);
  for (let i = 0; i < 2; i++) {
    const b = await p.$(".grid-3 .btn-primario");
    if (!b) break;
    await b.click();
    await esperar(p, 1600);
    const cerrar = await p.$(".festejo button, .festejo-cerrar");
    if (cerrar) { await cerrar.click(); await esperar(p, 500); }
  }
  await p.goto(`${BASE}/#/matches`, { waitUntil: "networkidle" });
  await esperar(p, 2200);
  const fila = await p.$(".chat-fila");
  if (fila) {
    await fila.click();
    await esperar(p, 1800);
    const abrir = await p.$(".videollamada-abrir");
    if (abrir) {
      await abrir.click();
      await esperar(p, 900);
      await p.screenshot({ path: `${SALIDA}/11-videollamada.png` });
      console.log("  11-videollamada");
    }
  }

  console.log(errores.length ? errores.join("\n") : "sin errores de JS");
  await nav.close();
  process.exit(errores.length ? 1 : 0);
})();
