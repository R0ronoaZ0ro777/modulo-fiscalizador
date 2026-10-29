/** Cliente WebSocket con reconexión por backoff exponencial. */
export interface MensajeRT {
  tipo: "flota" | "infraccion" | "umbral";
  evento?: "creada" | "actualizada";
  datos: any;
}

export function conectarRealtime(opts: {
  token: () => string | undefined;
  renovar: () => Promise<boolean>;
  alMensaje: (m: MensajeRT) => void;
  alEstado: (conectado: boolean) => void;
}): () => void {
  let ws: WebSocket | null = null, cerrado = false, espera = 1000, timer: number | undefined;

  const abrir = () => {
    const token = opts.token();
    if (!token || cerrado) return;
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws?token=${encodeURIComponent(token)}`);
    ws.onopen = () => { espera = 1000; opts.alEstado(true); };
    ws.onmessage = (e) => { try { opts.alMensaje(JSON.parse(e.data)); } catch { /* ignora mensajes mal formados */ } };
    ws.onclose = async (e) => {
      opts.alEstado(false);
      if (cerrado) return;
      if (e.code === 4401) await opts.renovar();          // token vencido: renovar y reconectar
      timer = window.setTimeout(abrir, espera);
      espera = Math.min(espera * 2, 30000);
    };
    ws.onerror = () => ws?.close();
  };
  abrir();
  return () => { cerrado = true; window.clearTimeout(timer); ws?.close(); };
}
