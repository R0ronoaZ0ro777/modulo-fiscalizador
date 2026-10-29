"""Motor de fiscalización: aplica las reglas (Strategy) a la telemetría ya validada
y deduplicada que publica el procesador en Kafka. Corre dentro del monolito
modular, en su propio consumer group: no agrega latencia al hot path."""
import asyncio
import json
import logging
import time
from datetime import datetime, timezone

from ..domain.models import InfraccionCandidata, Telemetria
from ..domain.reglas import ContextoRegla, FabricaReglas

log = logging.getLogger(__name__)


class MotorFiscalizacion:
    def __init__(self, *, db, catalogo, umbrales, infracciones, flota, cooldown, cooldown_s: int,
                 reglas_telemetria=None, reglas_periodicas=None) -> None:
        self.db, self.catalogo, self.umbrales = db, catalogo, umbrales
        self.infracciones, self.flota, self.cooldown, self.cooldown_s = infracciones, flota, cooldown, cooldown_s
        self.reglas_t = reglas_telemetria if reglas_telemetria is not None else FabricaReglas.telemetria()
        self.reglas_p = reglas_periodicas if reglas_periodicas is not None else FabricaReglas.periodicas()
        self._cat: tuple[dict, dict] | None = None
        self._cat_t = 0.0

    async def _catalogo(self) -> tuple[dict, dict]:
        if self._cat is None or time.monotonic() - self._cat_t > 60:
            async with self.db.tx() as conn:
                self._cat = (await self.catalogo.rutas(conn), await self.catalogo.bus_ruta(conn))
            self._cat_t = time.monotonic()
        return self._cat

    async def _registrar(self, c: InfraccionCandidata) -> dict | None:
        if not await self.cooldown.adquirir(f"{c.bus_id}:{c.tipo}", self.cooldown_s):
            return None          # ya se fiscalizó hace poco: evita inundar con alertas repetidas
        return await self.infracciones.registrar_detectada(c)

    async def procesar(self, t: Telemetria) -> list[dict]:
        rutas, bus_ruta = await self._catalogo()
        if t.bus_id not in bus_ruta:
            log.warning("Bus %s no está en el catálogo; se ignora", t.bus_id)
            return []
        ctx = ContextoRegla(await self.umbrales.get(), rutas.get(bus_ruta[t.bus_id]), datetime.now(timezone.utc))
        creadas = []
        for regla in self.reglas_t:                   # el motor no conoce reglas concretas
            c = regla.evaluar(t, ctx)
            if c and (inf := await self._registrar(c)):
                creadas.append(inf)
        return creadas

    async def revisar_periodicas(self) -> list[dict]:
        rutas, bus_ruta = await self._catalogo()
        umb, ahora = await self.umbrales.get(), datetime.now(timezone.utc)
        creadas = []
        for estado in await self.flota.snapshot(ahora):
            if estado.bus_id not in bus_ruta:
                continue
            ctx = ContextoRegla(umb, rutas.get(bus_ruta[estado.bus_id]), ahora)
            for regla in self.reglas_p:
                c = regla.evaluar(estado, ctx)
                if c and (inf := await self._registrar(c)):
                    creadas.append(inf)
        return creadas


async def consumir_kafka(settings, motor: MotorFiscalizacion) -> None:
    from aiokafka import AIOKafkaConsumer
    from ..pipeline.kafka_utils import asegurar_topicos

    while True:
        consumer = None
        try:
            await asegurar_topicos(settings)
            consumer = AIOKafkaConsumer(settings.topic_validated, bootstrap_servers=settings.kafka_bootstrap,
                                        group_id="fiscalizacion", enable_auto_commit=False,
                                        auto_offset_reset="latest")
            await consumer.start()
            log.info("Motor de fiscalización consumiendo '%s'", settings.topic_validated)
            while True:
                lotes = await consumer.getmany(timeout_ms=1000, max_records=200)
                for msgs in lotes.values():
                    for m in msgs:
                        try:
                            await motor.procesar(Telemetria.model_validate(json.loads(m.value)))
                        except Exception:
                            log.exception("Mensaje descartado por error en el motor")
                if lotes:
                    await consumer.commit()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Consumidor Kafka caído; reintentando en 5 s")
            await asyncio.sleep(5)
        finally:
            if consumer:
                await consumer.stop()


async def vigilante_periodico(motor: MotorFiscalizacion, intervalo_s: float = 10) -> None:
    while True:
        await asyncio.sleep(intervalo_s)
        try:
            await motor.revisar_periodicas()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Fallo en la revisión periódica")
