import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { EntradaAuditoria, Verificacion } from "../api/types";
import { mensajeError } from "./hooks";

const POR_PAGINA = 25;

export function useAuditoriaViewModel() {
  const [items, setItems] = useState<EntradaAuditoria[]>([]);
  const [total, setTotal] = useState(0);
  const [pagina, setPagina] = useState(0);
  const [accion, setAccion] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [verificacion, setVerificacion] = useState<Verificacion | null>(null);
  const [verificando, setVerificando] = useState(false);

  const cargar = useCallback(async () => {
    const q = new URLSearchParams({ limit: String(POR_PAGINA), offset: String(pagina * POR_PAGINA) });
    if (accion) q.set("accion", accion);
    try { const r = await api.get<{ items: EntradaAuditoria[]; total: number }>(`/auditoria?${q}`); setItems(r.items); setTotal(r.total); setError(null); }
    catch (e) { setError(mensajeError(e)); }
  }, [pagina, accion]);
  useEffect(() => { cargar(); }, [cargar]);

  return {
    items, total, pagina, error, accion, verificacion, verificando,
    paginas: Math.max(1, Math.ceil(total / POR_PAGINA)),
    setPagina, recargar: cargar,
    setAccion: (a: string) => { setAccion(a); setPagina(0); },
    verificar: async () => {
      setVerificando(true); setVerificacion(null);
      try { setVerificacion(await api.get<Verificacion>("/auditoria/verificar")); } catch (e) { setError(mensajeError(e)); }
      finally { setVerificando(false); }
    },
  };
}
