import { useMemo, useState } from "react";
import { useAhora, useAppSelector } from "./hooks";
import { hace } from "./format";

const UMBRAL_OBSOLETO_MS = 8000;

export function useFlotaViewModel() {
  const { buses, resumen, actualizadoEn, conectado } = useAppSelector((s) => s.flota);
  const alertas = useAppSelector((s) => s.alertas.items);
  const ahora = useAhora();
  const [vista, setVista] = useState<"mapa" | "lista">("mapa");

  const obsoleto = !conectado || actualizadoEn === null || ahora - actualizadoEn > UMBRAL_OBSOLETO_MS;
  const ordenados = useMemo(
    () => [...buses].sort((a, b) => (a.estado === b.estado ? a.bus_id.localeCompare(b.bus_id) : a.estado === "SIN_SENAL" ? -1 : 1)),
    [buses]);

  return {
    buses: ordenados, resumen, alertas, vista, setVista, conectado, obsoleto,
    pctSinSenal: resumen.total ? (100 * resumen.sin_senal) / resumen.total : 0,
    estadoTexto: conectado
      ? (obsoleto ? "Conectado, esperando datos" : "En vivo")
      : actualizadoEn ? `Sin conexión · último dato hace ${hace(ahora - actualizadoEn)}` : "Sin conexión",
  };
}
