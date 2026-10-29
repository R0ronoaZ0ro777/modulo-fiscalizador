import { useState } from "react";
import { api } from "../api/client";
import { sesionCerrada, sesionIniciada } from "../store/authSlice";
import { mensajeError, useAppDispatch, useAppSelector } from "./hooks";

export function useAuthViewModel() {
  const dispatch = useAppDispatch();
  const usuario = useAppSelector((s) => s.auth.usuario);
  const [paso, setPaso] = useState<"credenciales" | "mfa">("credenciales");
  const [mfaToken, setMfaToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const ejecutar = async (fn: () => Promise<void>) => {
    setError(null); setCargando(true);
    try { await fn(); } catch (e) { setError(mensajeError(e)); } finally { setCargando(false); }
  };

  return {
    usuario, paso, error, cargando,
    enviarCredenciales: (email: string, password: string) => ejecutar(async () => {
      if (!email.trim() || !password) throw new Error("Ingresa tu correo y contraseña.");
      const r = await api.login(email.trim(), password);
      if (r.mfa_required) { setMfaToken(r.mfa_token); setPaso("mfa"); } else dispatch(sesionIniciada(r));
    }),
    enviarCodigo: (codigo: string) => ejecutar(async () => {
      if (!/^\d{6}$/.test(codigo.trim())) throw new Error("El código tiene 6 dígitos.");
      dispatch(sesionIniciada(await api.mfa(mfaToken, codigo.trim())));
    }),
    volver: () => { setPaso("credenciales"); setError(null); },
    cerrarSesion: () => dispatch(sesionCerrada()),
  };
}
