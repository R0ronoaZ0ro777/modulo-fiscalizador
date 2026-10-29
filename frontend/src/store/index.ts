import { combineReducers, configureStore } from "@reduxjs/toolkit";
import { FLUSH, PAUSE, PERSIST, persistReducer, persistStore, PURGE, REGISTER, REHYDRATE } from "redux-persist";
import storage from "redux-persist/lib/storage";
import sessionStorage from "redux-persist/lib/storage/session";
import alertas from "./alertasSlice";
import auth from "./authSlice";
import flota from "./flotaSlice";
import sincronizacion from "./sincronizacionSlice";

// La sesión vive en sessionStorage: cada ventana/pestaña puede tener su propio rol a la vez
// (con localStorage, iniciar sesión en otra ventana pisaba la sesión de la primera).
const authPersistido = persistReducer({ key: "fiscalizacion-auth", storage: sessionStorage }, auth);
// Último estado de la flota: solo como respaldo visual; "conectado" nunca se restaura.
const flotaPersistida = persistReducer({ key: "fiscalizacion-flota", storage, blacklist: ["conectado"] }, flota);

const reducer = combineReducers({ auth: authPersistido, flota: flotaPersistida, alertas, sincronizacion });

export const store = configureStore({
  reducer,
  middleware: (gdm) => gdm({
    serializableCheck: { ignoredActions: [FLUSH, REHYDRATE, PAUSE, PERSIST, PURGE, REGISTER] },
  }),
});
export const persistor = persistStore(store);
export type RootState = ReturnType<typeof reducer>;
export type AppDispatch = typeof store.dispatch;
