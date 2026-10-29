import { NavLink, Navigate, Outlet } from "react-router-dom";
import { ROLES, permisos } from "../viewmodels/format";
import { useAppSelector } from "../viewmodels/hooks";
import { useAuthViewModel } from "../viewmodels/useAuthViewModel";
import { useRealtime } from "../viewmodels/useRealtime";

export default function Shell() {
  const vm = useAuthViewModel();
  const conectado = useAppSelector((s) => s.flota.conectado);
  useRealtime();
  if (!vm.usuario) return <Navigate to="/login" replace />;
  const rol = vm.usuario.rol;

  return (
    <div className="app">
      <a href="#contenido" className="saltar">Saltar al contenido</a>
      <nav className="riel" aria-label="Principal">
        <div className="marca"><strong>Centro de Control</strong><span>Fiscalización de flota</span></div>
        <NavLink to="/" end>Flota en vivo</NavLink>
        <NavLink to="/infracciones">Infracciones</NavLink>
        <NavLink to="/reportes">Reportes</NavLink>
        {permisos.verAuditoria(rol) && <NavLink to="/auditoria">Auditoría</NavLink>}
        <NavLink to="/umbrales">Umbrales</NavLink>
        <div className="riel-pie">
          <span className={`conexion ${conectado ? "on" : "off"}`}>{conectado ? "Tiempo real activo" : "Sin conexión en tiempo real"}</span>
          <strong>{vm.usuario.nombre}</strong>
          <span>{ROLES[rol]}</span>
          <button className="secundario" onClick={vm.cerrarSesion}>Cerrar sesión</button>
        </div>
      </nav>
      <main id="contenido" className="contenido" tabIndex={-1}><Outlet /></main>
    </div>
  );
}
