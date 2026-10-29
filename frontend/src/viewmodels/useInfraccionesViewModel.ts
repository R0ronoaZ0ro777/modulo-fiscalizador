import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { EstadoInfraccion, Infraccion, Sancion, TipoInfraccion } from "../api/types";
import { mensajeError, useAppSelector } from "./hooks";

export interface Filtros { estado: EstadoInfraccion | ""; tipo: TipoInfraccion | ""; bus_id: string }
export interface DatosResolucion { resolucion: "CURSAR" | "DESCARTAR"; observaciones: string; sancion: Sancion | null }

/** Mismas reglas que el backend, para dar retroalimentación inmediata (el servidor decide igualmente). */
export function validarResolucion(d: DatosResolucion, severidad: string): string | null {
  const obs = d.observaciones.trim();
  if (d.resolucion === "DESCARTAR") return obs.length < 10 ? "Indica el motivo del descarte (mínimo 10 caracteres)." : null;
  if (obs.length < 20) return "Fundamenta la infracción (mínimo 20 caracteres).";
  if (!d.sancion) return "Elige la sanción.";
  if (d.sancion.tipo === "MULTA" && !(d.sancion.monto_uf && d.sancion.monto_uf > 0 && d.sancion.monto_uf <= 500))
    return "El monto de la multa debe ser mayor que 0 y hasta 500 UF.";
  if (severidad === "CRITICA" && d.sancion.tipo === "AMONESTACION") return "Una infracción crítica no puede resolverse solo con amonestación.";
  return null;
}

export function useInfraccionesViewModel() {
  const contador = useAppSelector((s) => s.alertas.contador);
  const [filtros, setFiltros] = useState<Filtros>({ estado: "", tipo: "", bus_id: "" });
  const [items, setItems] = useState<Infraccion[]>([]);
  const [total, setTotal] = useState(0);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [seleccionadaId, setSeleccionadaId] = useState<string | null>(null);
  const [accionError, setAccionError] = useState<string | null>(null);
  const [trabajando, setTrabajando] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    const q = new URLSearchParams({ limit: "100" });
    (Object.keys(filtros) as (keyof Filtros)[]).forEach((k) => filtros[k] && q.set(k, filtros[k].trim()));
    try {
      const r = await api.get<{ items: Infraccion[]; total: number }>(`/infracciones?${q}`);
      setItems(r.items); setTotal(r.total); setError(null);
    } catch (e) { setError(mensajeError(e)); } finally { setCargando(false); }
  }, [filtros]);

  // Recarga al cambiar filtros y cuando llega un evento en vivo (con pequeña espera para agrupar ráfagas).
  useEffect(() => { const t = setTimeout(cargar, 250); return () => clearTimeout(t); }, [cargar, contador]);

  const seleccionada = useMemo(() => items.find((i) => i.id === seleccionadaId) ?? null, [items, seleccionadaId]);

  const ejecutar = async (fn: () => Promise<unknown>, mensajeOk: string) => {
    setAccionError(null); setAviso(null); setTrabajando(true);
    try { await fn(); setAviso(mensajeOk); await cargar(); return true; }
    catch (e) { setAccionError(mensajeError(e)); await cargar(); return false; }
    finally { setTrabajando(false); }
  };

  return {
    items, total, cargando, error, filtros, setFiltros, seleccionada,
    seleccionar: (id: string | null) => { setSeleccionadaId(id); setAccionError(null); setAviso(null); },
    accionError, aviso, trabajando,
    tomarEnRevision: (id: string) => ejecutar(() => api.post(`/infracciones/${id}/revision`), "La infracción quedó en revisión."),
    resolver: (id: string, d: DatosResolucion) => ejecutar(
      () => api.post(`/infracciones/${id}/resolver`, { ...d, observaciones: d.observaciones.trim() }),
      d.resolucion === "CURSAR" ? "Infracción cursada. Se generó el acta con la evidencia." : "Infracción descartada. Se generó el acta."),
  };
}
