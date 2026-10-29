import { Mensaje } from "../components/Etiquetas";
import type { PuntoHorario } from "../api/types";
import { permisos } from "../viewmodels/format";
import { useAppSelector } from "../viewmodels/hooks";
import { useReportesViewModel } from "../viewmodels/useReportesViewModel";

function GraficoHorario({ serie, limite }: { serie: PuntoHorario[]; limite: number | null }) {
  if (!serie.length) return <p className="vacio">Sin telemetría en el rango para esta concesionaria.</p>;
  const W = 640, H = 200, P = 34, maxV = Math.max(limite ?? 0, ...serie.map((s) => s.vel_max), 20) * 1.1;
  const bw = (W - P * 2) / serie.length, y = (v: number) => H - P - (v / maxV) * (H - P * 2);
  return (
    <figure>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Velocidad promedio y máxima por hora">
        <line x1={P} y1={H - P} x2={W - P} y2={H - P} stroke="var(--linea)" />
        {serie.map((s, i) => {
          const x = P + i * bw;
          return (
            <g key={s.hora}>
              <rect x={x + 3} y={y(s.vel_prom)} width={Math.max(bw - 6, 2)} height={H - P - y(s.vel_prom)} fill="var(--tinta-2)" />
              <line x1={x + bw / 2} x2={x + bw / 2} y1={y(s.vel_max)} y2={y(s.vel_prom)} stroke="var(--critica)" strokeWidth="2" />
              {(serie.length <= 12 || i % 2 === 0) && <text x={x + bw / 2} y={H - 14} textAnchor="middle" fontSize="11" fill="var(--suave)">{new Date(s.hora).getHours()}h</text>}
            </g>
          );
        })}
        {limite !== null && <>
          <line x1={P} x2={W - P} y1={y(limite)} y2={y(limite)} stroke="var(--grave)" strokeDasharray="5 4" />
          <text x={W - P} y={y(limite) - 4} textAnchor="end" fontSize="11" fill="var(--grave)">límite {limite} km/h</text>
        </>}
      </svg>
      <figcaption>Barra: velocidad promedio por hora. Trazo rojo: hasta la velocidad máxima registrada.</figcaption>
    </figure>
  );
}

export default function ReportesView() {
  const rol = useAppSelector((s) => s.auth.usuario?.rol);
  const vm = useReportesViewModel();
  return (
    <>
      <header className="cabecera"><h1>Reportes de cumplimiento</h1></header>
      <form className="filtros" onSubmit={(e) => { e.preventDefault(); vm.generar(); }}>
        <label>Desde<input type="datetime-local" value={vm.desde} onChange={(e) => vm.setDesde(e.target.value)} /></label>
        <label>Hasta<input type="datetime-local" value={vm.hasta} onChange={(e) => vm.setHasta(e.target.value)} /></label>
        <button className="primario" disabled={vm.cargando}>{vm.cargando ? "Generando…" : "Generar reporte"}</button>
        {permisos.exportar(rol) && <button type="button" className="secundario" onClick={vm.exportar}>Exportar CSV</button>}
      </form>
      {vm.error && <Mensaje tipo="error">{vm.error}</Mensaje>}
      <div className="tabla-scroll">
        <table>
          <thead><tr><th>Concesionaria</th><th>Buses</th><th>Cumplimiento de velocidad</th><th>Vel. prom.</th><th>Vel. máx.</th><th>Infracciones</th><th>Cursadas</th></tr></thead>
          <tbody>
            {vm.filas.map((f) => (
              <tr key={f.concesionaria_id} className={f.concesionaria_id === vm.concesionariaId ? "fila-sel" : ""}>
                <td><button className="enlace" onClick={() => vm.setConcesionariaId(f.concesionaria_id)}>{f.nombre}</button></td>
                <td>{f.buses}</td>
                <td>{f.cumplimiento_velocidad_pct === null ? "Sin datos" : `${f.cumplimiento_velocidad_pct} %`}</td>
                <td>{f.vel_prom} km/h</td><td>{f.vel_max} km/h</td>
                <td>{f.infracciones} <span className="suave">({f.exceso_velocidad} vel. · {f.desvio_ruta} ruta · {f.perdida_senal} señal)</span></td>
                <td>{f.cursadas}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <section className="panel grafico"><h2>Velocidad por hora · {vm.filas.find((f) => f.concesionaria_id === vm.concesionariaId)?.nombre ?? "—"}</h2>
        <GraficoHorario serie={vm.serie} limite={vm.limite} />
      </section>
    </>
  );
}
