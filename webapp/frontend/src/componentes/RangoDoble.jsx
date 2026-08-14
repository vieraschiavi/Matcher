// Slider de rango con dos manijas, sin librería: dos <input type="range">
// superpuestos, cada uno maneja un extremo. Es el patrón liviano estándar
// para esto — una librería de terceros para dos sliders es media app de
// dependencias.
export default function RangoDoble({ min, max, paso = 1, valorMin, valorMax, unidad, onCambiar }) {
  const rango = max - min || 1;
  const pctMin = ((valorMin - min) / rango) * 100;
  const pctMax = ((valorMax - min) / rango) * 100;

  const cambiarMin = (e) => {
    const v = Math.min(Number(e.target.value), valorMax - paso);
    onCambiar(v, valorMax);
  };
  const cambiarMax = (e) => {
    const v = Math.max(Number(e.target.value), valorMin + paso);
    onCambiar(valorMin, v);
  };

  return (
    <div className="rango-doble">
      <div className="rango-doble-valores">
        <span>
          {valorMin}
          {unidad}
        </span>
        <span>
          {valorMax}
          {unidad}
        </span>
      </div>
      <div className="rango-doble-pista">
        <div className="rango-doble-relleno" style={{ left: `${pctMin}%`, right: `${100 - pctMax}%` }} />
        <input
          type="range"
          min={min}
          max={max}
          step={paso}
          value={valorMin}
          onChange={cambiarMin}
          aria-label="Mínimo"
        />
        <input
          type="range"
          min={min}
          max={max}
          step={paso}
          value={valorMax}
          onChange={cambiarMax}
          aria-label="Máximo"
        />
      </div>
    </div>
  );
}
