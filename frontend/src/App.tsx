import { Route, Routes } from "react-router-dom";
import AuditoriaView from "./views/AuditoriaView";
import DashboardView from "./views/DashboardView";
import InfraccionesView from "./views/InfraccionesView";
import LoginView from "./views/LoginView";
import ReportesView from "./views/ReportesView";
import Shell from "./views/Shell";
import UmbralesView from "./views/UmbralesView";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginView />} />
      <Route element={<Shell />}>
        <Route index element={<DashboardView />} />
        <Route path="infracciones" element={<InfraccionesView />} />
        <Route path="reportes" element={<ReportesView />} />
        <Route path="auditoria" element={<AuditoriaView />} />
        <Route path="umbrales" element={<UmbralesView />} />
      </Route>
    </Routes>
  );
}
