import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base: "./" — obligatorio para el APK. Dentro del WebView de Capacitor los
// archivos se sirven desde capacitor://localhost y las rutas absolutas
// (/assets/...) quedan fuera del bundle: la app arranca en blanco.
// En dev, /api se proxya al backend FastAPI (8820). En producción el propio
// backend sirve dist/, así que /api es same-origin y no hay CORS.
export default defineConfig({
  base: "./",
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8820" } },
  build: { outDir: "dist", emptyOutDir: true },
});
