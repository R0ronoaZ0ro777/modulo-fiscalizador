import { createSlice, PayloadAction } from "@reduxjs/toolkit";

interface SincronizacionState {
  umbralesRevision: number;
}

const slice = createSlice({
  name: "sincronizacion",
  initialState: { umbralesRevision: 0 } as SincronizacionState,
  reducers: {
    umbralRecibido: (s, _a: PayloadAction<{ clave: string }>) => {
      s.umbralesRevision += 1;
    },
  },
});

export const { umbralRecibido } = slice.actions;
export default slice.reducer;
