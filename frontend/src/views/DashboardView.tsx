import { Link } from "react-router-dom";
import { FleetMap } from "../components/FleetMap";
import { Severidad_ } from "../components/Etiquetas";
import { TIPOS, fechaHora, frase } from "../viewmodels/format";
import { useFlotaViewModel } from "../viewmodels/useFlotaViewModel";

export default function DashboardView() {
  const vm = useFlotaViewModel();
  const r = vm.resumen;
  const nueva = vm.alertas.filter((a) => a.estado === "DETECTADA" || a.estado === "EN_REVISION");

  return (
    <>
      <header className="cabecera">
        <h1>Flota en vivo</h1>
        <span className={`estado-red ${vm.conectado && !vm.obsoleto ? "on" : "off"}`} role="status">{vm.estadoTexto}</span>
      </header>
      {vm.obsoleto && r.total > 0 && (
        <p className="mensaje mensaje-aviso" role="status">Mostrando el último estado conocido; los datos pueden no estar al día.</p>
      )}

      <section className="flota-resumen" aria-label="Resumen de la flota">
        <div className="cifra"><b>{r.total.toLocaleString("es-CL")}</b> buses reportando</div>
        <div className="cifra ok"><b>{r.activos.toLocaleString("es-CL")}</b> con señal</div>
        <div className="cifra sin"><b>{r.sin_senal.toLocaleString("es-CL")}</b> sin señal</div>
        <div className="barra" role="img" aria-label={`${Math.round(vm.pctSinSenal)} % de la flota sin señal`}>
          <span style={{ width: `${100 - vm.pctSinSenal}%` }} />
        </div>
      </section>

      <div className="tablero">
        <section className="panel" aria-label="Posición de los buses">
          <div className="panel-cab">
            <h2>Posición de los buses</h2>
            <div className="conmutador" role="group" aria-label="Tipo de vista">
              <button aria-pressed={vm.vista === "mapa"} onClick={() => vm.setVista("mapa")}>Mapa</button>
              <button aria-pressed={vm.vista === "lista"} onClick={() => vm.setVista("lista")}>Lista</button>
            </div>
          </div>
          {vm.vista === "mapa" ? <FleetMap buses={vm.buses} alertas={vm.alertas} /> : (
            <div className="tabla-scroll">
              <table>
                <caption className="solo-lector">Buses ordenados: primero los que no tienen señal</caption>
                <thead><tr><th>Bus</th><th>Estado</th><th>Velocidad</th><th>Último reporte</th></tr></thead>
                <tbody>
                  {vm.buses.map((b) => (
                    <tr key={b.bus_id}>
                      <td>{b.bus_id}</td>
                      <td>{b.estado === "SIN_SENAL" ? "Sin señal" : "En ruta"}</td>
                      <td>{b.speed_kmh} km/h</td>
                      <td>hace {Math.round(b.edad_s)} s</td>
                    </tr>
                  ))}
                  {vm.buses.length === 0 && <tr><td colSpan={4} className="vacio">Aún no llegan reportes de buses.</td></tr>}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="panel alertas" aria-label="Alertas en vivo">
          <div className="panel-cab"><h2>Alertas en vivo</h2><Link to="/infracciones">Ver todas</Link></div>
          {/* Región aria-live: el lector de pantalla anuncia cada alerta nueva sin mover el foco. */}
          <ul aria-live="polite" aria-relevant="additions">
            {nueva.slice(0, 12).map((a) => (
              <li key={a.id}>
                <Severidad_ valor={a.severidad} />
                <span className="alerta-texto"><span className="solo-lector">{frase(a)}. </span><span aria-hidden="true"><b>{a.bus_id}</b> · {TIPOS[a.tipo]}</span></span>
                <time dateTime={a.detectada_en}>{fechaHora(a.detectada_en)}</time>
              </li>
            ))}
            {nueva.length === 0 && <li className="vacio">Sin alertas abiertas. Las nuevas infracciones aparecerán aquí al detectarse.</li>}
          </ul>
        </section>
      </div>
    </>
  );
}
