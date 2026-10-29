"""Simulador de OBUs: reemplaza a los buses reales publicando telemetría por MQTT (QoS 1).

Reproduce lo que importa para la fiscalización: exceso de velocidad, desvíos del
trazado, túneles (pérdida breve de señal con reenvío posterior = backfill), fallas
largas del equipo y reintentos que generan mensajes duplicados.
"""
import asyncio
import json
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone
from math import atan2, cos, degrees, radians, sin

import aiomqtt

from ..config import get_settings
from ..domain.catalogo import RUTAS, generar_buses
from ..domain.geo import M_POR_GRADO, haversine_m

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s simulador: %(message)s")
log = logging.getLogger("simulador")


class Trazado:
    def __init__(self, puntos: list[list[float]]) -> None:
        self.p = puntos ## aqui van a estar los puntos del trazado
        self.acum = [0.0]## va a contener todos los puntos recorridos acumulados
        for a, b in zip(puntos, puntos[1:]): # calcular la distancia acumulada entre puntos
            self.acum.append(self.acum[-1] + haversine_m(a[0], a[1], b[0], b[1]))
        self.largo = self.acum[-1]

    def posicion(self, d: float) -> tuple[float, float, float]: ##esta funcion devuelve la posicion del
        #bus en el trazado dado una distancia d
        d = max(0.0, min(self.largo, d))
        for i in range(1, len(self.acum)):
            if d <= self.acum[i]:
                f = (d - self.acum[i - 1]) / ((self.acum[i] - self.acum[i - 1]) or 1)
                a, b = self.p[i - 1], self.p[i]
                lat, lon = a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])
                rumbo = (degrees(atan2((b[1] - a[1]) * cos(radians(lat)), b[0] - a[0])) + 360) % 360
                return lat, lon, rumbo
        return self.p[-1][0], self.p[-1][1], 0.0


class BusSim:
    def __init__(self, idx: int, bus: dict, trazado: Trazado, intervalo: float, tasa: float, rng: random.Random):
        self.id, self.t, self.dt, self.tasa, self.rng = bus["id"], trazado, intervalo, tasa, rng
        self.dist = rng.uniform(0, trazado.largo)
        self.dir = rng.choice((1, -1))
        self.vel = rng.uniform(25, 42)
        self.seq = 0
        self.modo, self.modo_hasta, self.desvio_m = "normal", None, 0.0
        self.offline_hasta: datetime | None = None
        self.buffer: list[dict] = []
        self.propenso_vel, self.propenso_desvio, self.propenso_falla = idx % 5 == 0, idx % 9 == 4, idx % 13 == 7

    def _p(self, base: float, prop: float | None = None, es_propenso: bool = False) -> bool:
        return self.rng.random() < (prop if es_propenso and prop else base) * self.tasa

    def _cambiar_modo(self, ahora: datetime) -> None:
        if self.modo != "normal" and ahora >= self.modo_hasta:
            self.modo = "normal"
        if self.offline_hasta and ahora >= self.offline_hasta:
            self.offline_hasta = None
        if self.modo != "normal" or self.offline_hasta:
            return
        r = self.rng
        if self._p(0.001, 0.02, self.propenso_vel):
            self.modo, self.modo_hasta = "exceso", ahora + timedelta(seconds=r.uniform(15, 35))
        elif self._p(0.0, 0.015, self.propenso_desvio):
            self.modo, self.modo_hasta = "desvio", ahora + timedelta(seconds=r.uniform(40, 70))
            self.desvio_m = r.choice((1, -1)) * r.uniform(350, 700)
        elif self._p(0.0, 0.004, self.propenso_falla):
            self.offline_hasta = ahora + timedelta(seconds=r.uniform(200, 280))      # falla larga del equipo
        elif self._p(0.008):
            self.offline_hasta = ahora + timedelta(seconds=r.uniform(15, 40))        # túnel

    def tick(self, ahora: datetime) -> list[dict]:
        self._cambiar_modo(ahora)
        if self.modo == "exceso":
            self.vel = self.rng.uniform(78, 105)
        else:
            self.vel = max(10, min(48, self.vel + self.rng.uniform(-3, 3)))
        self.dist += self.dir * self.vel / 3.6 * self.dt
        if self.dist <= 0 or self.dist >= self.t.largo:
            self.dir *= -1
            self.dist = max(0.0, min(self.t.largo, self.dist))
        lat, lon, rumbo = self.t.posicion(self.dist)
        if self.modo == "desvio":
            lat += self.desvio_m / M_POR_GRADO
        self.seq += 1
        ev = {"event_id": str(uuid.uuid4()), "bus_id": self.id, "sequence_number": self.seq,
              "ts": ahora.isoformat(), "lat": round(lat, 6), "lon": round(lon, 6),
              "speed_kmh": round(self.vel, 1), "heading": round(rumbo if self.dir > 0 else (rumbo + 180) % 360, 1),
              "is_backfill": False}
        if self.offline_hasta:
            self.buffer.append(ev)                      # sin cobertura: se acumula localmente
            return []
        salida: list[dict] = []
        if self.buffer:                                 # recuperó señal: reenvía en orden
            salida += [{**e, "is_backfill": True} for e in self.buffer]
            if self.rng.random() < 0.3:                 # algunos ACK se pierden → el OBU reenvía
                salida += self.rng.sample(salida, min(3, len(salida)))
            self.buffer.clear()
        salida.append(ev)
        if self.rng.random() < 0.01:
            salida.append(ev)                           # duplicado por reintento
        return salida


async def main() -> None:
    s = get_settings()
    rng = random.Random(2026)
    trazados = {k: Trazado(v["geometria"]) for k, v in RUTAS.items()}
    buses = [BusSim(i, b, trazados[b["ruta_id"]], s.sim_interval_s, s.sim_fault_rate, rng)
             for i, b in enumerate(generar_buses(s.sim_buses), start=1)]
    log.info("Simulando %d buses, 1 muestra cada %.1fs (tasa de fallas x%.1f)", len(buses), s.sim_interval_s, s.sim_fault_rate)
    espera = 1
    while True:
        try:
            async with aiomqtt.Client(s.mqtt_host, s.mqtt_port, identifier="simulador-obu") as cliente:
                espera = 1
                while True:
                    inicio = asyncio.get_event_loop().time()
                    ahora = datetime.now(timezone.utc)
                    for b in buses:
                        for ev in b.tick(ahora):
                            await cliente.publish(f"obu/{b.id}/telemetria", json.dumps(ev), qos=1)
                    await asyncio.sleep(max(0.0, s.sim_interval_s - (asyncio.get_event_loop().time() - inicio)))
        except aiomqtt.MqttError as e:
            log.warning("MQTT no disponible (%s). Reintento en %ds", e, espera)
            await asyncio.sleep(espera)
            espera = min(espera * 2, 30)


if __name__ == "__main__":
    asyncio.run(main())
