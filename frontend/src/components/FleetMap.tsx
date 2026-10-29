import { CircleMarker, MapContainer, TileLayer, Tooltip } from "react-leaflet";
import type { Bus, Infraccion } from "../api/types";

const COLOR = { ok: "#1e7b52", sinSenal: "#7b8494", LEVE: "#2b64a8", GRAVE: "#b86e00", CRITICA: "#b3261e" };

export function FleetMap({ buses, alertas }: { buses: Bus[]; alertas: Infraccion[] }) {
  // Un bus con infracción abierta se destaca con el color de su mayor severidad.
  const orden = { LEVE: 1, GRAVE: 2, CRITICA: 3 } as const;
  const abierta = new Map<string, Infraccion["severidad"]>();
  alertas.filter((a) => a.estado === "DETECTADA" || a.estado === "EN_REVISION").forEach((a) => {
    const prev = abierta.get(a.bus_id);
    if (!prev || orden[a.severidad] > orden[prev]) abierta.set(a.bus_id, a.severidad);
  });

  return (
    <MapContainer center={[-33.432, -70.63]} zoom={13} className="mapa" aria-label="Mapa con la posición de los buses">
      <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                 url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
      {buses.map((b) => {
        const sev = abierta.get(b.bus_id);
        const color = sev ? COLOR[sev] : b.estado === "SIN_SENAL" ? COLOR.sinSenal : COLOR.ok;
        return (
          <CircleMarker key={b.bus_id} center={[b.lat, b.lon]} radius={sev ? 9 : 6}
                        pathOptions={{ color: "#fff", weight: 2, fillColor: color, fillOpacity: b.estado === "SIN_SENAL" ? 0.55 : 1 }}>
            <Tooltip>{b.bus_id} · {b.speed_kmh} km/h{b.estado === "SIN_SENAL" ? " · sin señal" : ""}{sev ? ` · alerta ${sev.toLowerCase()}` : ""}</Tooltip>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}
