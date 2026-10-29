import { useState } from "react";
import { Mensaje } from "../components/Etiquetas";
import { permisos } from "../viewmodels/format";
import { useAppSelector } from "../viewmodels/hooks";
import { useUmbralesViewModel } from "../viewmodels/useUmbralesViewModel";

export default function UmbralesView() {
  const rol = useAppSelector((s) => s.auth.usuario?.rol);
  const vm = useUmbralesViewModel();
  const [edicion, setEdicion] = useState<Record<string, string>>({});
  const puedeEditar = permisos.editarUmbrales(rol);

  return (
    <>
      <header className="cabecera"><h1>Umbrales de fiscalización</h1></header>
      <p className="suave texto-corto">
        Definen cuándo se genera una infracción. Los cambios usan versionado optimista: si otra persona modificó el valor antes que tú, verás un aviso y no se pisa su cambio.
        {!puedeEditar && " Solo administración puede modificarlos."}
      </p>
      {vm.error && <Mensaje tipo="error">{vm.error}</Mensaje>}
      {vm.aviso && <Mensaje tipo="ok">{vm.aviso}</Mensaje>}
      <div className="tabla-scroll">
        <table>
          <thead><tr><th>Umbral</th><th>Valor</th><th>Versión</th>{puedeEditar && <th>Nuevo valor</th>}</tr></thead>
          <tbody>
            {vm.items.map((u) => (
              <tr key={u.clave}>
                <td><b>{u.clave}</b><br /><span className="suave">{u.descripcion}</span></td>
                <td>{u.valor} {u.unidad}</td><td>{u.version}</td>
                {puedeEditar && (
                  <td className="fila-edicion">
                    <input type="number" aria-label={`Nuevo valor de ${u.clave}`} value={edicion[u.clave] ?? ""} onChange={(e) => setEdicion({ ...edicion, [u.clave]: e.target.value })} />
                    <button className="secundario" disabled={!edicion[u.clave]} onClick={() => { vm.guardar(u, Number(edicion[u.clave])); setEdicion({ ...edicion, [u.clave]: "" }); }}>Guardar</button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
