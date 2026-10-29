import { useEffect, useState } from "react";
import { TypedUseSelectorHook, useDispatch, useSelector } from "react-redux";
import type { AppDispatch, RootState } from "../store";

export const useAppDispatch = () => useDispatch<AppDispatch>();
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector;

/** Reloj que fuerza re-render cada `ms` (para mostrar "hace 5 s" y detectar datos viejos). */
export function useAhora(ms = 1000) {
  const [t, setT] = useState(() => Date.now());
  useEffect(() => { const i = setInterval(() => setT(Date.now()), ms); return () => clearInterval(i); }, [ms]);
  return t;
}

export const mensajeError = (e: unknown) => (e instanceof Error ? e.message : "Ocurrió un error inesperado.");
