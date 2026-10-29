import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { FilaCumplimiento, PuntoHorario } from "../api/types";
import { mensajeError } from "./hooks";

const aLocal = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);

export function useReportesViewModel() {
  const [desde, setDesde] = useState(() => aLocal(new Date(Date.now() - 24 * 3600 * 1000)));
  const [hasta, setHasta] = useState(() => aLocal(new Date()));
  const [filas, setFilas] = useState<FilaCumplimiento[]>([]);
  const [limite, setLimite] = useState<number | null>(null);
  const [serie, setSerie] = useState<PuntoHorario[]>([]);
  const [concesionariaId, setConcesionariaId] = useState<number | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const rango = () => {
    if (!desde || !hasta || new Date(desde) >= new Date(hasta)) throw new Error("La fecha de inicio debe ser anterior a la de término.");
    return new URLSearchParams({ desde: new Date(desde).toISOString(), hasta: new Date(hasta).toISOString() });
  };

  const generar = useCallback(async () => {
    setCargando(true); setError(null);
    try {
      const q = rango();
      const r = await api.get<{ items: FilaCumplimiento[]; limite_kmh: number }>(`/reportes/cumplimiento?${q}`);
      setFilas(r.items); setLimite(r.limite_kmh);
      setConcesionariaId((id) => id ?? r.items[0]?.concesionaria_id ?? null);
    } catch (e) { setError(mensajeError(e)); } finally { setCargando(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [desde, hasta]);

  useEffect(() => { generar(); /* primera carga */ // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (concesionariaId === null) return;
    (async () => {
      try {
        const q = rango(); q.set("concesionaria_id", String(concesionariaId));
        setSerie((await api.get<{ items: PuntoHorario[] }>(`/reportes/serie-horaria?${q}`)).items);
      } catch { setSerie([]); }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [concesionariaId, filas]);

  return {
    desde, hasta, setDesde, setHasta, filas, limite, serie, concesionariaId, setConcesionariaId, cargando, error, generar,
    exportar: async () => {
      try { await api.descargar(`/reportes/cumplimiento.csv?${rango()}`, "cumplimiento.csv"); }
      catch (e) { setError(mensajeError(e)); }
    },
  };
}
