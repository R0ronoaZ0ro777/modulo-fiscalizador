export type Rol = "ADMIN" | "FISCALIZADOR" | "OPERADOR";
export type TipoInfraccion = "EXCESO_VELOCIDAD" | "DESVIO_RUTA" | "PERDIDA_SENAL";
export type Severidad = "LEVE" | "GRAVE" | "CRITICA";
export type EstadoInfraccion = "DETECTADA" | "EN_REVISION" | "CURSADA" | "DESCARTADA";

export interface Usuario { nombre: string; email: string; rol: Rol }

export interface Sesion {
  mfa_required: false;
  access_token: string;
  refresh_token: string;
  expires_in: number;
  usuario: Usuario;
}
export interface DesafioMfa { mfa_required: true; mfa_token: string }

export interface Bus {
  bus_id: string; lat: number; lon: number; speed_kmh: number; heading: number;
  ts: string; edad_s: number; estado: "EN_RUTA" | "SIN_SENAL";
}
export interface ResumenFlota { total: number; activos: number; sin_senal: number }
export interface Flota { buses: Bus[]; resumen: ResumenFlota }

export interface Infraccion {
  id: string; bus_id: string; patente: string; ruta_id: string; concesionaria: string;
  tipo: TipoInfraccion; severidad: Severidad; estado: EstadoInfraccion;
  detectada_en: string; valor_medido: number; umbral: number;
  lat: number | null; lon: number | null; detalle: Record<string, unknown>;
}

export interface Sancion { tipo: "AMONESTACION" | "MULTA"; monto_uf?: number | null }
export interface EntradaAuditoria {
  id: number; ts: string; actor_id: string | null; actor_rol: string; accion: string;
  entidad: string | null; entidad_id: string | null; payload: Record<string, unknown>; hash: string;
}
export interface Verificacion {
  valida: boolean; total: number; primer_invalido: number | null; motivo: string | null; ultimo_hash?: string | null;
}
export interface Umbral { clave: string; valor: number; unidad: string; descripcion: string; version: number }
export interface FilaCumplimiento {
  concesionaria_id: number; nombre: string; buses: number; muestras: number; sobre_limite: number;
  vel_prom: number; vel_max: number; infracciones: number; exceso_velocidad: number; desvio_ruta: number;
  perdida_senal: number; cursadas: number; cumplimiento_velocidad_pct: number | null;
}
export interface PuntoHorario { hora: string; muestras: number; vel_prom: number; vel_max: number }

export interface ErrorApi { codigo: string; mensaje: string; campos?: { campo: string; mensaje: string }[] }
