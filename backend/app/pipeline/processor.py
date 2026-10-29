"""Procesador de telemetría (hot path, despliegue independiente).

raw-telemetry → valida → deduplica → persiste en TimescaleDB → actualiza
la última posición en Redis → publica en telemetry-validated.
Semántica at-least-once: el offset se confirma SOLO tras persistir y publicar;
la clave primaria de la hypertable hace idempotente cualquier reproceso.
"""
import asyncio
import logging
from datetime import timedelta

import redis.asyncio as aioredis
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from pydantic import ValidationError

from ..config import Settings, get_settings
from ..db import Database
from ..domain.models import Telemetria
from ..repositories.postgres import PgTelemetria
from ..repositories.redis_flota import FlotaRedis
from .kafka_utils import asegurar_topicos

log = logging.getLogger("processor")
DEDUP_TTL = int(timedelta(hours=24).total_seconds())


async def procesar_lote(mensajes, *, redis, flota, telemetria, db, productor, settings: Settings) -> dict:
    stats = {"recibidos": len(mensajes), "validos": 0, "duplicados": 0, "invalidos": 0}
    candidatos, vistos = [], set()
    for m in mensajes:
        try:
            t = Telemetria.model_validate_json(m.value)
        except ValidationError as e:                           # a la cola de mensajes fallidos (DLQ)
            stats["invalidos"] += 1
            await productor.send(settings.topic_dlq, value=m.value,
                                 headers=[("error", str(e.errors()[0]["msg"]).encode()[:200])])
            continue
        clave = (t.bus_id, t.sequence_number)
        if clave in vistos:
            stats["duplicados"] += 1
            continue
        vistos.add(clave)
        candidatos.append(t)

    if candidatos:                                             # duplicados ya procesados en lotes anteriores
        pipe = redis.pipeline()
        for t in candidatos:
            pipe.exists(f"dedup:{t.bus_id}:{t.sequence_number}")
        existen = await pipe.execute()
    nuevos = [t for t, ya in zip(candidatos, existen if candidatos else []) if not ya]
    stats["duplicados"] += len(candidatos) - len(nuevos)

    if nuevos:
        async with db.tx() as conn:
            await telemetria.insertar_lote(conn, nuevos)       # idempotente (ON CONFLICT DO NOTHING)
        for t in sorted(nuevos, key=lambda x: x.ts):
            await flota.actualizar(t)                          # un backfill viejo no pisa la posición actual
        for t in nuevos:
            await productor.send(settings.topic_validated, key=t.bus_id.encode(), value=t.model_dump_json().encode())
        await productor.flush()
        pipe = redis.pipeline()                                # recién ahora se marca como visto
        for t in nuevos:
            pipe.set(f"dedup:{t.bus_id}:{t.sequence_number}", "1", ex=DEDUP_TTL)
        await pipe.execute()
        stats["validos"] = len(nuevos)
    return stats


async def main() -> None:
    s = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s processor: %(message)s")
    await asegurar_topicos(s)
    db = Database(s.database_url)
    redis = aioredis.from_url(s.redis_url, decode_responses=True)
    flota, telemetria = FlotaRedis(redis, s.offline_after_s), PgTelemetria()
    consumidor = AIOKafkaConsumer(s.topic_raw, bootstrap_servers=s.kafka_bootstrap, group_id="processor",
                                  enable_auto_commit=False, auto_offset_reset="latest")
    productor = AIOKafkaProducer(bootstrap_servers=s.kafka_bootstrap, acks="all", enable_idempotence=True, linger_ms=5)
    await consumidor.start()
    await productor.start()
    log.info("Procesador listo: %s → %s", s.topic_raw, s.topic_validated)
    try:
        while True:
            lotes = await consumidor.getmany(timeout_ms=500, max_records=500)
            ##max_records lo que hace es limitar la cantidad de mensajes que se pueden recibir en un solo lote,
            # lo cual es útil para controlar la carga de procesamiento y evitar que el consumidor se vea abrumado por
            # demasiados mensajes a la vez.
            mensajes = [m for ms in lotes.values() for m in ms]
            if not mensajes:
                continue
            try:
                st = await procesar_lote(mensajes, redis=redis, flota=flota, telemetria=telemetria, db=db,
                                         productor=productor, settings=s)
                await consumidor.commit()
                log.info("lote %s", st)
            except Exception:
                log.exception("Fallo al procesar el lote; se reintentará (sin confirmar offset)")
                await asyncio.sleep(2)
                for tp in lotes:                               # vuelve al primer offset no confirmado
                    consumidor.seek(tp, lotes[tp][0].offset)
    finally:
        await consumidor.stop()
        await productor.stop()
        await db.dispose()


if __name__ == "__main__":
    asyncio.run(main())
