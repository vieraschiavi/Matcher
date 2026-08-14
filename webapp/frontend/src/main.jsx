import React from "react";
import { createRoot } from "react-dom/client";
import { HashRouter } from "react-router-dom";
import App from "./App";
import { Proveedor } from "./estado";
import "./theme.css";

// HashRouter y no BrowserRouter: dentro del WebView de Capacitor no hay
// servidor que resuelva rutas profundas, así que /matches devolvería 404 y la
// app arrancaría en blanco en el APK.
createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <HashRouter>
      <Proveedor>
        <App />
      </Proveedor>
    </HashRouter>
  </React.StrictMode>
);
