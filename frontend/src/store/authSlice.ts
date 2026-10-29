import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import type { Sesion, Usuario } from "../api/types";

interface AuthState { access?: string; refresh?: string; usuario?: Usuario }

const slice = createSlice({
  name: "auth",
  initialState: {} as AuthState,
  reducers: {
    sesionIniciada: (_, a: PayloadAction<Sesion>) => ({
      access: a.payload.access_token, refresh: a.payload.refresh_token, usuario: a.payload.usuario,
    }),
    sesionCerrada: () => ({}),
  },
});
export const { sesionIniciada, sesionCerrada } = slice.actions;
export default slice.reducer;
