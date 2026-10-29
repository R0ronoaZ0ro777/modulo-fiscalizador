import { FormEvent, useState } from "react";
import { Navigate } from "react-router-dom";
import { Mensaje } from "../components/Etiquetas";
import { useAuthViewModel } from "../viewmodels/useAuthViewModel";

export default function LoginView() {
  const vm = useAuthViewModel();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [codigo, setCodigo] = useState("");
  if (vm.usuario) return <Navigate to="/" replace />;

  const enviar = (e: FormEvent) => {
    e.preventDefault();
    return vm.paso === "credenciales" ? vm.enviarCredenciales(email, password) : vm.enviarCodigo(codigo);
  };

  return (
    <main className="login">
      <section className="login-marca">
        <h1>Centro de Control</h1>
        <p>Fiscalización de la flota de transporte urbano. Cada acción queda registrada en un log de auditoría inalterable.</p>
      </section>
      <form className="login-form" onSubmit={enviar} noValidate>
        {vm.paso === "credenciales" ? (
          <>
            <h2>Iniciar sesión</h2>
            <label>Correo institucional
              <input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus />
            </label>
            <label>Contraseña
              <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </label>
          </>
        ) : (
          <>
            <h2>Verifica tu identidad</h2>
            <p className="suave">Ingresa el código de 6 dígitos de tu aplicación de autenticación.</p>
            <label>Código de verificación
              <input inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={codigo}
                     onChange={(e) => setCodigo(e.target.value.replace(/\D/g, ""))} autoFocus className="codigo" />
            </label>
          </>
        )}
        {vm.error && <Mensaje tipo="error">{vm.error}</Mensaje>}
        <button className="primario" disabled={vm.cargando}>
          {vm.cargando ? "Verificando…" : vm.paso === "credenciales" ? "Continuar" : "Entrar"}
        </button>
        {vm.paso === "mfa" && <button type="button" className="enlace" onClick={vm.volver}>Usar otra cuenta</button>}
      </form>
    </main>
  );
}
