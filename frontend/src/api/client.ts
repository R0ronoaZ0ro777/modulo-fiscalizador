import type { DesafioMfa, ErrorApi, Sesion } from "./types";

/** Hooks inyectados desde main.tsx para evitar dependencia circular con el store. */
interface Enlaces {
  tokens: () => { access?: string; refresh?: string };
  guardar: (s: Sesion) => void;
  cerrar: () => void;
}
let enlaces: Enlaces | null = null;
export const configurarCliente = (e: Enlaces) => { enlaces = e; };

export class ApiError extends Error {
  constructor(public status: number, public codigo: string, mensaje: string, public datos?: ErrorApi) { super(mensaje); }
}

let refrescando: Promise<boolean> | null = null;

/** Renueva el access token con el refresh token (una sola petición aunque fallen varias a la vez). */
export function refrescarSesion(): Promise<boolean> {
  if (!refrescando) {
    refrescando = (async () => {
      const refresh = enlaces?.tokens().refresh;
      if (!refresh) return false;
      const r = await fetch("/api/auth/refresh", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: refresh }),
      });
      if (!r.ok) return false;
      enlaces!.guardar(await r.json());
      return true;
    })().catch(() => false).finally(() => { refrescando = null; });
  }
  return refrescando;
}

async function peticion(ruta: string, opts: RequestInit = {}, reintento = true): Promise<Response> {
  const { access } = enlaces?.tokens() ?? {};
  const headers: Record<string, string> = { ...(opts.body ? { "Content-Type": "application/json" } : {}) };
  if (access) headers.Authorization = `Bearer ${access}`;
  let r: Response;
  try {
    r = await fetch(`/api${ruta}`, { ...opts, headers: { ...headers, ...(opts.headers as object) } });
  } catch {
    throw new ApiError(0, "SIN_CONEXION", "No hay conexión con el servidor. Se reintentará automáticamente.");
  }
  if (r.status === 401 && reintento && access && !ruta.startsWith("/auth/")) {
    if (await refrescarSesion()) return peticion(ruta, opts, false);
    enlaces?.cerrar();
  }
  return r;
}

async function procesar<T>(r: Response): Promise<T> {
  if (r.ok) return (r.headers.get("content-type")?.includes("json") ? r.json() : r.text()) as Promise<T>;
  let d: ErrorApi | undefined;
  try { d = await r.json(); } catch { /* respuesta sin cuerpo */ }
  const msg = d?.campos?.length ? d.campos.map((c) => `${c.campo}: ${c.mensaje}`).join(" · ") : d?.mensaje;
  throw new ApiError(r.status, d?.codigo ?? "ERROR", msg ?? "Ocurrió un error inesperado.", d);
}

const json = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });

export const api = {
  get: <T>(ruta: string) => peticion(ruta).then((r) => procesar<T>(r)),
  post: <T>(ruta: string, body?: unknown) => peticion(ruta, body === undefined ? { method: "POST" } : json(body)).then((r) => procesar<T>(r)),
  put: <T>(ruta: string, body: unknown) => peticion(ruta, { method: "PUT", body: JSON.stringify(body) }).then((r) => procesar<T>(r)),
  async descargar(ruta: string, nombre: string) {
    const r = await peticion(ruta);
    if (!r.ok) await procesar(r);
    const url = URL.createObjectURL(await r.blob());
    const a = Object.assign(document.createElement("a"), { href: url, download: nombre });
    a.click();
    URL.revokeObjectURL(url);
  },
  login: (email: string, password: string) => api.post<Sesion | DesafioMfa>("/auth/login", { email, password }),
  mfa: (mfa_token: string, codigo: string) => api.post<Sesion>("/auth/mfa", { mfa_token, codigo }),
};
