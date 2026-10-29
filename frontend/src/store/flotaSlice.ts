import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import type { Flota } from "../api/types";

/** Último estado conocido de la flota. Se persiste: si la consola se recarga o pierde
 *  la conexión, el ViewModel muestra lo último que supo (marcado como desactualizado). */
interface FlotaState extends Flota { actualizadoEn: number | null; conectado: boolean }

const vacio: FlotaState = { buses: [], resumen: { total: 0, activos: 0, sin_senal: 0 }, actualizadoEn: null, conectado: false };

const slice = createSlice({
  name: "flota",
  initialState: vacio,
  reducers: {
    flotaRecibida: (s, a: PayloadAction<Flota>) => { s.buses = a.payload.buses; s.resumen = a.payload.resumen; s.actualizadoEn = Date.now(); },
    conexionCambio: (s, a: PayloadAction<boolean>) => { s.conectado = a.payload; },
  },
});
export const { flotaRecibida, conexionCambio } = slice.actions;
export default slice.reducer;
