import { FormEvent, useState } from "react";
import { Estado_, Mensaje, Severidad_ } from "../components/Etiquetas";
import type { Infraccion } from "../api/types";
import { ESTADOS, TIPOS, fechaHora, permisos } from "../viewmodels/format";
import { useAppSelector } from "../viewmodels/hooks";
import { DatosResolucion, useInfraccionesViewModel, validarResolucion } from "../viewmodels/useInfraccionesViewModel";

const medida = (i: Infraccion) =>
  i.tipo === "EXCESO_VELOCIDAD" ? `${i.valor_medido} km/h (máx. ${i.umbral})`
  : i.tipo === "DESVIO_RUTA" ? `${i.valor_medido} m del trazado (máx. ${i.umbral})`
  : `${Math.round(i.valor_medido / 60)} min sin reportar`;

function FormularioResolucion({ inf, vm }: { inf: Infraccion; vm: ReturnType<typeof useInfraccionesViewModel> }) {
  const [d, setD] = useState<DatosResolucion>({ resolucion: "CURSAR", observaciones: "", sancion: { tipo: "MULTA", monto_uf: null } });
  const [error, setError] = useState<string | null>(null);
  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    const msg = validarResolucion(d, inf.severidad);
    setError(msg);
    if (!msg) await vm.resolver(inf.id, d);
  };
  return (
    <form onSubmit={enviar} className="resolucion" noValidate>
      <h3>Resolver infracción</h3>
      <fieldset>
        <legend>Resolución</legend>
        <label className="opcion"><input type="radio" checked={d.resolucion === "CURSAR"} onChange={() => setD({ ...d, resolucion: "CURSAR", sancion: { tipo: "MULTA", monto_uf: null } })} /> Cursar</label>
        <label className="opcion"><input type="radio" checked={d.resolucion === "DESCARTAR"} onChange={() => setD({ ...d, resolucion: "DESCARTAR", sancion: null })} /> Descartar</label>
      </fieldset>
      {d.resolucion === "CURSAR" && (
        <div className="fila">
          <label>Sanción
            <select value={d.sancion?.tipo} onChange={(e) => setD({ ...d, sancion: { tipo: e.target.value as "MULTA" | "AMONESTACION", monto_uf: null } })}>
              <option value="MULTA">Multa</option><option value="AMONESTACION">Amonestación</option>
            </select>
          </label>
          {d.sancion?.tipo === "MULTA" && (
            <label>Monto (UF)
              <input type="number" min="0" step="0.5" value={d.sancion.monto_uf ?? ""}
                     onChange={(e) => setD({ ...d, sancion: { tipo: "MULTA", monto_uf: e.target.value === "" ? null : Number(e.target.value) } })} />
            </label>
          )}
        </div>
      )}
      <label>{d.resolucion === "CURSAR" ? "Fundamento" : "Motivo del descarte"}
        <textarea rows={4} value={d.observaciones} maxLength={2000} onChange={(e) => setD({ ...d, observaciones: e.target.value })} />
        <small>{d.observaciones.trim().length} caracteres · mínimo {d.resolucion === "CURSAR" ? 20 : 10}</small>
      </label>
      {(error || vm.accionError) && <Mensaje tipo="error">{error ?? vm.accionError}</Mensaje>}
      <button className="primario" disabled={vm.trabajando}>{vm.trabajando ? "Guardando…" : d.resolucion === "CURSAR" ? "Cursar y generar acta" : "Descartar y generar acta"}</button>
    </form>
  );
}

export default function InfraccionesView() {
  const vm = useInfraccionesViewModel();
  const rol = useAppSelector((s) => s.auth.usuario?.rol);
  const sel = vm.seleccionada;
  const abierta = sel && (sel.estado === "DETECTADA" || sel.estado === "EN_REVISION");

  return (
    <>
      <header className="cabecera"><h1>Infracciones</h1><span className="suave">{vm.total} en total</span></header>
      <form className="filtros" onSubmit={(e) => e.preventDefault()} aria-label="Filtros">
        <label>Estado
          <select value={vm.filtros.estado} onChange={(e) => vm.setFiltros({ ...vm.filtros, estado: e.target.value as never })}>
            <option value="">Todos</option>
            {Object.entries(ESTADOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label>Tipo
          <select value={vm.filtros.tipo} onChange={(e) => vm.setFiltros({ ...vm.filtros, tipo: e.target.value as never })}>
            <option value="">Todos</option>
            {Object.entries(TIPOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label>Bus
          <input placeholder="BUS-001" value={vm.filtros.bus_id} onChange={(e) => vm.setFiltros({ ...vm.filtros, bus_id: e.target.value.toUpperCase() })} />
        </label>
      </form>
      {vm.error && <Mensaje tipo="error">{vm.error}</Mensaje>}

      <div className={`maestro ${sel ? "con-detalle" : ""}`}>
        <div className="tabla-scroll">
          <table>
            <thead><tr><th>Detectada</th><th>Bus</th><th>Concesionaria</th><th>Tipo</th><th>Severidad</th><th>Estado</th></tr></thead>
            <tbody>
              {vm.items.map((i) => (
                <tr key={i.id} className={i.id === sel?.id ? "fila-sel" : ""}>
                  <td>{fechaHora(i.detectada_en)}</td>
                  <td><button className="enlace" onClick={() => vm.seleccionar(i.id)} aria-label={`Abrir infracción de ${i.bus_id}, ${TIPOS[i.tipo]}`}>{i.bus_id}</button></td>
                  <td>{i.concesionaria}</td><td>{TIPOS[i.tipo]}</td>
                  <td><Severidad_ valor={i.severidad} /></td><td><Estado_ valor={i.estado} /></td>
                </tr>
              ))}
              {!vm.cargando && vm.items.length === 0 && <tr><td colSpan={6} className="vacio">No hay infracciones con estos filtros.</td></tr>}
            </tbody>
          </table>
        </div>

        {sel && (
          <aside className="detalle" aria-label="Detalle de la infracción">
            <button className="enlace cerrar" onClick={() => vm.seleccionar(null)}>Cerrar</button>
            <h2>{TIPOS[sel.tipo]}</h2>
            <p><Severidad_ valor={sel.severidad} /> <Estado_ valor={sel.estado} /></p>
            <dl>
              <dt>Bus</dt><dd>{sel.bus_id} · patente {sel.patente} · ruta {sel.ruta_id}</dd>
              <dt>Concesionaria</dt><dd>{sel.concesionaria}</dd>
              <dt>Medición</dt><dd>{medida(sel)}</dd>
              <dt>Detectada</dt><dd>{fechaHora(sel.detectada_en)}{sel.detalle.es_backfill ? " (reenviada tras perder cobertura)" : ""}</dd>
              {sel.lat !== null && <><dt>Posición</dt><dd>{sel.lat?.toFixed(5)}, {sel.lon?.toFixed(5)}</dd></>}
            </dl>
            {vm.aviso && <Mensaje tipo="ok">{vm.aviso}</Mensaje>}
            {abierta && permisos.tomarEnRevision(rol) && sel.estado === "DETECTADA" && (
              <button className="secundario" disabled={vm.trabajando} onClick={() => vm.tomarEnRevision(sel.id)}>Tomar en revisión</button>
            )}
            {abierta && permisos.resolver(rol) && <FormularioResolucion key={sel.id} inf={sel} vm={vm} />}
            {abierta && !permisos.resolver(rol) && <p className="suave">Solo un fiscalizador puede cursar o descartar infracciones.</p>}
            {!abierta && <p className="suave">Esta infracción ya fue resuelta. El acta y su evidencia están en la auditoría.</p>}
            {vm.accionError && !abierta && <Mensaje tipo="error">{vm.accionError}</Mensaje>}
          </aside>
        )}
      </div>
    </>
  );
}
