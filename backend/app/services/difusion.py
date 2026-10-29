"""Difusión en tiempo real hacia las consolas web (WebSocket).

El hub es un OBSERVER del bus de eventos: recibe hechos del dominio y los
reenvía a cada conexión sin que los servicios sepan que existe una UI.
"""
import asyncio
import logging
from dataclasses import dataclass, field

from ..events import (
    FLOTA_SNAPSHOT,
    INFRACCION_ACTUALIZADA,
    INFRACCION_CREADA,
    UMBRAL_ACTUALIZADO,
    EventBus,
)

log = logging.getLogger(__name__)


@dataclass(eq=False)
class Conexion:
    exp: float                                   # expiración del JWT con que se conectó
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=100))

    def encolar(self, msg: dict) -> None:
        if self.queue.full():                    # cliente lento: descarta lo más antiguo (backpressure)
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        self.queue.put_nowait(msg)


class HubWS:
    def __init__(self, bus: EventBus) -> None:
        self.conexiones: set[Conexion] = set()
        bus.subscribe(INFRACCION_CREADA, lambda _t, p: self._difundir({"tipo": "infraccion", "evento": "creada", "datos": p}))
        bus.subscribe(INFRACCION_ACTUALIZADA, lambda _t, p: self._difundir({"tipo": "infraccion", "evento": "actualizada", "datos": p}))
        bus.subscribe(FLOTA_SNAPSHOT, lambda _t, p: self._difundir({"tipo": "flota", "datos": p}))
        bus.subscribe(UMBRAL_ACTUALIZADO, lambda _t, p: self._difundir({"tipo": "umbral", "datos": p}))

    def _difundir(self, msg: dict) -> None:
        for c in self.conexiones:
            c.encolar(msg)

    def agregar(self, c: Conexion) -> None:
        self.conexiones.add(c)

    def quitar(self, c: Conexion) -> None:
        self.conexiones.discard(c)


def resumen_flota(estados) -> dict:
    buses = [e.a_dict() for e in estados]
    sin = sum(1 for e in estados if e.estado == "SIN_SENAL")
    return {"buses": buses, "resumen": {"total": len(buses), "activos": len(buses) - sin, "sin_senal": sin}}


async def ticker_flota(flota, bus: EventBus, hub: HubWS, intervalo_s: float = 2.0) -> None:
    while True:
        await asyncio.sleep(intervalo_s)
        if not hub.conexiones:
            continue
        try:
            await bus.publish(FLOTA_SNAPSHOT, resumen_flota(await flota.snapshot()))
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Fallo al publicar snapshot de flota")
