import "leaflet/dist/leaflet.css";
import React from "react";
import ReactDOM from "react-dom/client";
import { Provider } from "react-redux";
import { BrowserRouter } from "react-router-dom";
import { PersistGate } from "redux-persist/integration/react";
import App from "./App";
import { configurarCliente } from "./api/client";
import { persistor, store } from "./store";
import { sesionCerrada, sesionIniciada } from "./store/authSlice";
import "./styles.css";

configurarCliente({
  tokens: () => ({ access: store.getState().auth.access, refresh: store.getState().auth.refresh }),
  guardar: (s) => store.dispatch(sesionIniciada(s)),
  cerrar: () => store.dispatch(sesionCerrada()),
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Provider store={store}>
      <PersistGate loading={null} persistor={persistor}>
        <BrowserRouter><App /></BrowserRouter>
      </PersistGate>
    </Provider>
  </React.StrictMode>,
);
