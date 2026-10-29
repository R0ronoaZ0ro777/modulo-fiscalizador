import { Navigate } from "react-router-dom";
import { Mensaje } from "../components/Etiquetas";
import { fechaHora, permisos } from "../viewmodels/format";
import { useAppSelector } from "../viewmodels/hooks";
import { useAuditoriaViewModel } from "../viewmodels/useAuditoriaViewModel";

const ACCIONES = ["INFRACCION_DETECTADA", "INFRACCION_EN_REVISION", "ACTA_CURSADA", "ACTA_DESCARTADA",
  "UMBRAL_MODIFICADO", "REPORTE_EXPORTADO", "LOGIN_OK", "LOGIN_FALLIDO", "MFA_FALLIDO"];

export default function AuditoriaView() {
  const rol = useAppSelector((s) => s.auth.usuario?.rol);
  const vm = useAuditoriaViewModel();
  if (!permisos.verAuditoria(rol)) return <Navigate to="/" replace />;

  return (
    <>
      <header className="cabecera"><h1>Auditoría</h1><span className="suave">{vm.total} entradas</span></header>
      <p className="suave texto-corto">Registro append-only con hash encadenado: cada entrada incluye el hash de la anterior, así que alterar o borrar una se detecta.</p>
      <div className="filtros">
        <label>Acción
          <select value={vm.accion} onChange={(e) => vm.setAccion(e.target.value)}>
            <option value="">Todas</option>{ACCIONES.map((a) => <option key={a}>{a}</option>)}
          </select>
        </label>
        <button className="secundario" onClick={vm.verificar} disabled={vm.verificando}>{vm.verificando ? "Verificando…" : "Verificar integridad"}</button>
        <button className="enlace" onClick={vm.recargar}>Actualizar</button>
      </div>
      {vm.verificacion && (vm.verificacion.valida
        ? <Mensaje tipo="ok">Cadena íntegra: {vm.verificacion.total} entradas verificadas. Último hash {vm.verificacion.ultimo_hash?.slice(0, 16)}…</Mensaje>
        : <Mensaje tipo="error">Integridad comprometida desde la entrada n.º {vm.verificacion.primer_invalido}. {vm.verificacion.motivo}</Mensaje>)}
      {vm.error && <Mensaje tipo="error">{vm.error}</Mensaje>}
      <div className="tabla-scroll">
        <table>
          <thead><tr><th>N.º</th><th>Fecha</th><th>Acción</th><th>Actor</th><th>Entidad</th><th>Hash</th></tr></thead>
          <tbody>
            {vm.items.map((e) => (
              <tr key={e.id}>
                <td>{e.id}</td><td>{fechaHora(e.ts)}</td><td>{e.accion}</td><td>{e.actor_rol}</td>
                <td>{e.entidad ? `${e.entidad} ${e.entidad_id?.slice(0, 8) ?? ""}` : "—"}</td>
                <td title={e.hash}><code>{e.hash.slice(0, 12)}…</code></td>
              </tr>
            ))}
            {vm.items.length === 0 && <tr><td colSpan={6} className="vacio">Sin entradas para este filtro.</td></tr>}
          </tbody>
        </table>
      </div>
      <nav className="paginacion" aria-label="Paginación">
        <button className="secundario" disabled={vm.pagina === 0} onClick={() => vm.setPagina(vm.pagina - 1)}>Anterior</button>
        <span>Página {vm.pagina + 1} de {vm.paginas}</span>
        <button className="secundario" disabled={vm.pagina + 1 >= vm.paginas} onClick={() => vm.setPagina(vm.pagina + 1)}>Siguiente</button>
      </nav>
    </>
  );
}
