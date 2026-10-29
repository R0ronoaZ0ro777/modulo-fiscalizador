import { useEffect } from "react";
import { api, refrescarSesion } from "../api/client";
import type { Flota, Infraccion } from "../api/types";
import { conectarRealtime } from "../api/realtime";
import { store } from "../store";
import { alertasSincronizadas, infraccionRecibida } from "../store/alertasSlice";
import { conexionCambio, flotaRecibida } from "../store/flotaSlice";
import { umbralRecibido } from "../store/sincronizacionSlice";
import { useAppDispatch, useAppSelector } from "./hooks";

/** Trae del servidor el estado vigente (posiciones y alertas abiertas): toda sesión, nueva o
 *  reconectada, parte del mismo punto que las demás en vez de empezar "desde cero". */
async function sincronizar(dispatch: ReturnType<typeof useAppDispatch>) {
  try {
    const [flota, det, rev] = await Promise.all([
      api.get<Flota>("/flota"),
      api.get<{ items: Infraccion[] }>("/infracciones?estado=DETECTADA&limit=30"),
      api.get<{ items: Infraccion[] }>("/infracciones?estado=EN_REVISION&limit=30"),
    ]);
    dispatch(flotaRecibida(flota));
    dispatch(alertasSincronizadas([...det.items, ...rev.items]));
  } catch { /* el WebSocket reintenta y vuelve a sincronizar al conectar */ }
}

/** Mantiene la suscripción en tiempo real mientras haya sesión y traduce mensajes a acciones del store. */
export function useRealtime() {
  const dispatch = useAppDispatch();
  const haySesion = useAppSelector((s) => !!s.auth.access);
  useEffect(() => {
    if (!haySesion) return;
    void sincronizar(dispatch);
    return conectarRealtime({
      token: () => store.getState().auth.access,
      renovar: refrescarSesion,
      alEstado: (c) => { dispatch(conexionCambio(c)); if (c) void sincronizar(dispatch); },
      alMensaje: (m) => {
        if (m.tipo === "flota") dispatch(flotaRecibida(m.datos));
        else if (m.tipo === "infraccion") dispatch(infraccionRecibida(m.datos));
        else if (m.tipo === "umbral") dispatch(umbralRecibido(m.datos));
      },
    });
  }, [haySesion, dispatch]);
}
