import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { Umbral } from "../api/types";
import { mensajeError, useAppSelector } from "./hooks";

export function useUmbralesViewModel() {
  const revision = useAppSelector((s) => s.sincronizacion.umbralesRevision);
  const [items, setItems] = useState<Umbral[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    try { setItems((await api.get<{ items: Umbral[] }>("/umbrales")).items); }
    catch (e) { setError(mensajeError(e)); }
  }, []);
  useEffect(() => { cargar(); }, [cargar, revision]);

  return {
    items, error, aviso,
    guardar: async (u: Umbral, valor: number) => {
      setError(null); setAviso(null);
      if (!Number.isFinite(valor)) { setError("Ingresa un número válido."); return; }
      try {
        await api.put(`/umbrales/${u.clave}`, { valor, version: u.version });
        setAviso(`Umbral actualizado: ${u.clave} = ${valor} ${u.unidad}.`);
      } catch (e) { setError(mensajeError(e)); }      // p. ej. conflicto de versión
      await cargar();
    },
  };
}
