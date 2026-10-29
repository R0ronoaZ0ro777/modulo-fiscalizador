import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import type { Infraccion } from "../api/types";

/** Feed en vivo de infracciones (máx. 30). `contador` avisa a las vistas que deben refrescar. */
const slice = createSlice({
  name: "alertas",
  initialState: { items: [] as Infraccion[], contador: 0 },
  reducers: {
    /** Resincroniza el feed con lo que el servidor tiene abierto (al iniciar sesión y al reconectar). */
    alertasSincronizadas: (s, a: PayloadAction<Infraccion[]>) => {
      const porId = new Map<string, Infraccion>();
      [...a.payload, ...s.items.filter((i) => i.estado === "DETECTADA" || i.estado === "EN_REVISION")]
        .forEach((i) => { if (!porId.has(i.id)) porId.set(i.id, i); });
      s.items = [...porId.values()]
        .filter((i) => i.estado === "DETECTADA" || i.estado === "EN_REVISION")
        .sort((x, y) => y.detectada_en.localeCompare(x.detectada_en)).slice(0, 30);
      s.contador += 1;
    },
    infraccionRecibida: (s, a: PayloadAction<Infraccion>) => {
      s.items = [a.payload, ...s.items.filter((i) => i.id !== a.payload.id)].slice(0, 30);
      s.contador += 1;
    },
  },
});
export const { infraccionRecibida, alertasSincronizadas } = slice.actions;
export default slice.reducer;
