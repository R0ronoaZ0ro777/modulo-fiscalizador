"""Estado en vivo de la flota en Redis: última posición por bus (lecturas sub-milisegundo)
y control de enfriamiento (cooldown) para no repetir infracciones."""
from datetime import datetime, timezone

from ..domain.models import EstadoBus, Telemetria


class FlotaRedis:
    def __init__(self, redis, offline_after_s: int) -> None:
        self.r = redis
        self.offline_after_s = offline_after_s

    async def actualizar(self, t: Telemetria) -> bool:
        """Guarda la posición solo si es más nueva que la almacenada (un backfill
        atrasado no pisa la posición actual). Cada bus cae en una única partición de
        Kafka, así que hay un solo escritor por bus y no se requiere script atómico."""
        key = f"bus:{t.bus_id}"
        ts_ms = int(t.ts.timestamp() * 1000)
        previo = await self.r.hget(key, "ts_ms")
        if previo is not None and int(previo) >= ts_ms:
            return False
        pipe = self.r.pipeline()
        pipe.hset(key, mapping={"lat": t.lat, "lon": t.lon, "speed": t.speed_kmh,
                                "heading": t.heading, "ts_ms": ts_ms, "seq": t.sequence_number})
        pipe.zadd("fleet:lastseen", {t.bus_id: t.ts.timestamp()})
        pipe.geoadd("fleet:geo", (t.lon, t.lat, t.bus_id))     # índice geoespacial
        await pipe.execute()
        return True

    async def snapshot(self, ahora: datetime | None = None) -> list[EstadoBus]:
        ahora = ahora or datetime.now(timezone.utc)
        ids = await self.r.zrange("fleet:lastseen", 0, -1)
        if not ids:
            return []
        pipe = self.r.pipeline()
        for i in ids:
            pipe.hgetall(f"bus:{i}")
        datos = await pipe.execute()
        out = []
        for bus_id, h in zip(ids, datos):
            if not h:
                continue
            ts = datetime.fromtimestamp(int(h["ts_ms"]) / 1000, tz=timezone.utc)
            edad = (ahora - ts).total_seconds()
            out.append(EstadoBus(bus_id, float(h["lat"]), float(h["lon"]), float(h["speed"]),
                                 float(h["heading"]), ts, max(edad, 0.0),
                                 "SIN_SENAL" if edad > self.offline_after_s else "EN_RUTA"))
        return out


class CooldownRedis:
    """SET NX EX: la primera llamada gana; las siguientes dentro de la ventana son ignoradas."""
    def __init__(self, redis) -> None:
        self.r = redis

    async def adquirir(self, clave: str, segundos: int) -> bool:
        return bool(await self.r.set(f"cooldown:{clave}", "1", nx=True, ex=segundos))
