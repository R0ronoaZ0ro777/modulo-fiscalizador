import type { EstadoInfraccion, Rol, Severidad, TipoInfraccion } from "../api/types";

export const TIPOS: Record<TipoInfraccion, string> = {
  EXCESO_VELOCIDAD: "Exceso de velocidad", DESVIO_RUTA: "Desvío de ruta", PERDIDA_SENAL: "Pérdida de señal",
};
export const ESTADOS: Record<EstadoInfraccion, string> = {
  DETECTADA: "Detectada", EN_REVISION: "En revisión", CURSADA: "Cursada", DESCARTADA: "Descartada",
};
export const SEVERIDADES: Record<Severidad, string> = { LEVE: "Leve", GRAVE: "Grave", CRITICA: "Crítica" };
export const ROLES: Record<Rol, string> = { ADMIN: "Administración", FISCALIZADOR: "Fiscalización", OPERADOR: "Operación" };

export const fechaHora = (iso: string) =>
  new Date(iso).toLocaleString("es-CL", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" });

export const hace = (ms: number) => {
  const s = Math.max(0, Math.round(ms / 1000));
  return s < 60 ? `${s} s` : s < 3600 ? `${Math.floor(s / 60)} min` : `${Math.floor(s / 3600)} h`;
};

/** Texto que lee un lector de pantalla cuando llega una alerta (la misma info que el mapa, en texto). */
export const frase = (i: { tipo: TipoInfraccion; bus_id: string; severidad: Severidad; valor_medido: number; umbral: number }) =>
  i.tipo === "EXCESO_VELOCIDAD" ? `${i.bus_id}: exceso de velocidad ${i.severidad.toLowerCase()}, ${i.valor_medido} km/h sobre un máximo de ${i.umbral}`
  : i.tipo === "DESVIO_RUTA" ? `${i.bus_id}: desvío de ruta ${i.severidad.toLowerCase()}, a ${i.valor_medido} m del trazado`
  : `${i.bus_id}: sin señal hace ${Math.round(i.valor_medido / 60)} min`;

/** Matriz de permisos de la UI (el backend vuelve a validar cada acción). */
export const permisos = {
  verAuditoria: (r?: Rol) => r === "FISCALIZADOR" || r === "ADMIN",
  tomarEnRevision: (r?: Rol) => r === "FISCALIZADOR" || r === "OPERADOR",
  resolver: (r?: Rol) => r === "FISCALIZADOR",
  editarUmbrales: (r?: Rol) => r === "ADMIN",
  exportar: (r?: Rol) => r === "FISCALIZADOR" || r === "ADMIN",
};
