import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.config import Settings
from app.pipeline.processor import procesar_lote
from app.repositories.memoria import MemDatabase, MemTelemetria
from app.repositories.redis_flota import FlotaRedis
from tests.conftest import tel


class FakeProductor:
    def __init__(self): self.enviados = []
    async def send(self, topic, value=None, key=None, headers=None): self.enviados.append((topic, key, value))
    async def flush(self): ...


def msg(t=None, raw=None):
    return SimpleNamespace(value=raw if raw is not None else t.model_dump_json().encode(), offset=0)


async def _correr(mensajes, redis, tel_repo, prod):
    s = Settings()
    return await procesar_lote(mensajes, redis=redis, flota=FlotaRedis(redis, 45), telemetria=tel_repo,
                               db=MemDatabase(), productor=prod, settings=s)


async def test_valida_deduplica_y_publica(redis):
    repo, prod = MemTelemetria(), FakeProductor()
    a, b = tel(seq=1), tel(seq=2)
    st = await _correr([msg(a), msg(b), msg(a)], redis, repo, prod)          # a llega duplicado
    assert st["validos"] == 2 and st["duplicados"] == 1
    assert len(repo.filas) == 2
    assert [t for t, *_ in prod.enviados].count("telemetry-validated") == 2

    st2 = await _correr([msg(b)], redis, repo, prod)                         # reenvío en otro lote
    assert st2["validos"] == 0 and st2["duplicados"] == 1 and len(repo.filas) == 2


async def test_mensajes_invalidos_van_a_dlq(redis):
    repo, prod = MemTelemetria(), FakeProductor()
    malo = tel().model_dump_json().replace('"speed_kmh":40.0', '"speed_kmh":999')
    st = await _correr([msg(raw=malo.encode()), msg(raw=b"no es json")], redis, repo, prod)
    assert st["invalidos"] == 2 and st["validos"] == 0
    assert all(t == "telemetry-dlq" for t, *_ in prod.enviados)


async def test_backfill_atrasado_no_pisa_la_posicion_actual(redis):
    repo, prod = MemTelemetria(), FakeProductor()
    ahora = datetime.now(timezone.utc)
    actual = tel(seq=10, lat=-33.40, ts=ahora)
    viejo = tel(seq=5, lat=-33.50, ts=ahora - timedelta(minutes=2), backfill=True)
    await _correr([msg(actual), msg(viejo)], redis, repo, prod)
    snap = await FlotaRedis(redis, 45).snapshot()
    assert snap[0].lat == -33.40 and len(repo.filas) == 2                     # el histórico sí se guarda


async def test_telemetria_futura_se_rechaza(redis):
    repo, prod = MemTelemetria(), FakeProductor()
    d = json.loads(tel().model_dump_json())
    d["ts"] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    st = await _correr([msg(raw=json.dumps(d).encode())], redis, repo, prod)
    assert st["invalidos"] == 1
