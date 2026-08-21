import { useEffect, useState } from "react";

import { api } from "../api";
import { t } from "../i18n";

/**
 * El monitor del dueño: clientes, descargas y plata.
 *
 * Sólo existe para las cuentas de `MATCHER_CUENTAS_DUENIO`. El servidor
 * responde 404 a cualquier otro, así que esta pantalla no esconde nada: si la
 * abre quien no debe, no recibe los números (regla 9 del producto — lo que
 * decide el servidor no lo tapa el cliente).
 */

const fmt = (n) => new Intl.NumberFormat("es-UY").format(n ?? 0);
const plata = (n, moneda = "USD") =>
  `${moneda} ${new Intl.NumberFormat("es-UY", { minimumFractionDigits: 2 }).format(n ?? 0)}`;

function Kpi({ rotulo, valor, nota, destacado }) {
  return (
    <div className={`kpi ${destacado ? "kpi-destacado" : ""}`}>
      <div className="rotulo">{rotulo}</div>
      <div className="valor">{valor}</div>
      {nota && <div className="kpi-nota">{nota}</div>}
    </div>
  );
}

export default function Panel() {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");

  const cargar = () =>
    api
      .panel()
      .then((r) => {
        setDatos(r);
        setError("");
      })
      .catch((e) => setError(e.message));

  useEffect(() => {
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error) {
    return (
      <>
        <h1 className="page-title">{t("Panel")}</h1>
        <div className="aviso aviso-error">{error}</div>
        <p className="page-sub">
          {t("El panel es sólo para las cuentas del dueño (MATCHER_CUENTAS_DUENIO).")}
        </p>
      </>
    );
  }
  if (!datos) return <p className="page-sub">{t("Cargando…")}</p>;

  const { usuarios, planes, dinero, descargas, actividad } = datos;
  const meses = Object.entries(dinero.por_mes || {});
  const tope = Math.max(1, ...meses.map(([, v]) => v));

  return (
    <>
      <h1 className="page-title">{t("Panel")}</h1>
      <p className="page-sub">
        {t("Lo que pasó de verdad, contado de la base. Las proyecciones son otra cosa y viven en el plan de negocio.")}
      </p>

      <h3 className="panel-titulo">{t("Clientes")}</h3>
      <div className="grid grid-3">
        <Kpi rotulo={t("Cuentas reales")} valor={fmt(usuarios.total)} destacado
             nota={usuarios.sinteticos ? `+${fmt(usuarios.sinteticos)} ${t("sintéticos de demo")}` : null} />
        <Kpi rotulo={t("Activos 30 días")} valor={fmt(usuarios.activos_30d)} />
        <Kpi rotulo={t("Activos 7 días")} valor={fmt(usuarios.activos_7d)} />
        <Kpi rotulo={t("Pagando")} valor={fmt(datos.pagando)} destacado
             nota={`${datos.conversion_pct}% ${t("de conversión")}`} />
        <Kpi rotulo="Plus" valor={fmt(planes.plus)} />
        <Kpi rotulo="Gold" valor={fmt(planes.gold)} />
      </div>

      <h3 className="panel-titulo">{t("Dinero")}</h3>
      <div className="grid grid-3">
        <Kpi rotulo={t("Facturado (bruto)")} valor={plata(dinero.bruto, dinero.moneda)} destacado />
        <Kpi
          rotulo={t("Neto estimado")}
          valor={plata(dinero.neto_estimado, dinero.moneda)}
          nota={`${t("descontando")} ${dinero.comision_estimada_pct}% ${t("de comisión")}`}
        />
        <Kpi rotulo={t("Últimos 30 días")} valor={plata(dinero.bruto_30d, dinero.moneda)} />
        <Kpi rotulo={t("Cobros")} valor={fmt(dinero.cobros)}
             nota={dinero.pendientes ? `${fmt(dinero.pendientes)} ${t("sin pagar")}` : null} />
      </div>

      {/* El neto NO es un dato duro y la pantalla lo dice. La comisión real la
          descuenta la pasarela y cambia por medio de pago y por promoción; los
          impuestos dependen de cómo esté constituido el negocio. Un número que
          parece exacto sin serlo es peor que uno que se declara aproximado. */}
      <div className="aviso" style={{ marginTop: 12 }}>
        {t("El neto es una estimación: la comisión real la descuenta la pasarela y varía. Los impuestos no están descontados acá.")}
      </div>

      {meses.length > 0 && (
        <>
          <h3 className="panel-titulo">{t("Por mes")}</h3>
          <div className="panel-barras">
            {meses.map(([mes, valor]) => (
              <div key={mes} className="panel-barra">
                <span className="panel-barra-mes">{mes}</span>
                <span className="panel-barra-riel">
                  <span style={{ width: `${(valor / tope) * 100}%` }} />
                </span>
                <span className="panel-barra-valor">{plata(valor, dinero.moneda)}</span>
              </div>
            ))}
          </div>
        </>
      )}

      <h3 className="panel-titulo">{t("Descargas")}</h3>
      <div className="grid grid-3">
        <Kpi rotulo={t("Total")} valor={fmt(descargas.total)} destacado />
        <Kpi rotulo="Android (APK)" valor={fmt(descargas.por_plataforma.apk)} />
        <Kpi rotulo="Windows (.exe)" valor={fmt(descargas.por_plataforma.exe)} />
        <Kpi rotulo={t("Últimos 30 días")} valor={fmt(descargas.ultimos_30d)} />
      </div>

      <h3 className="panel-titulo">{t("Uso")}</h3>
      <div className="grid grid-3">
        <Kpi rotulo="Matches" valor={fmt(actividad.matches)} />
        <Kpi rotulo={t("Mensajes")} valor={fmt(actividad.mensajes)} />
        <Kpi rotulo={t("Videollamadas")} valor={fmt(actividad.videollamadas)} />
        <Kpi rotulo={t("Reportes")} valor={fmt(actividad.reportes)}
             nota={actividad.reportes ? t("revisalos") : null} />
      </div>

      <button className="btn" style={{ marginTop: 20 }} onClick={cargar}>
        {t("Actualizar")}
      </button>
    </>
  );
}
