"""Gateway MQTT → Kafka (hot path, despliegue independiente).

Recibe la telemetría de las OBU por MQTT (QoS 1) y la publica en `raw-telemetry`
con clave = bus_id: todos los eventos de un bus caen en la misma partición y
conservan su orden. No valida el negocio; solo evita la suplantación de bus.
"""
import asyncio
import json
import logging

import aiomqtt
from aiokafka import AIOKafkaProducer

from ..config import get_settings
from .kafka_utils import asegurar_topicos

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s gateway: %(message)s")
log = logging.getLogger("gateway")


def bus_coincide(topico: str, payload: bytes) -> str | None:
    """Devuelve el bus_id si el tópico obu/<bus>/telemetria coincide con el payload; si no, None.
    (En producción esto lo garantiza el CN del certificado mTLS de cada OBU.)"""
    partes = topico.split("/")
    try:
        if len(partes) == 3 and json.loads(payload).get("bus_id") == partes[1]:
            return partes[1]
    except (ValueError, AttributeError):
        pass
    return None


async def main() -> None:
    s = get_settings()
    await asegurar_topicos(s)
    productor = AIOKafkaProducer(bootstrap_servers=s.kafka_bootstrap, acks="all", enable_idempotence=True, linger_ms=5)
    await productor.start()
    espera, reenviados, descartados = 1, 0, 0
    try:
        while True:
            try:
                async with aiomqtt.Client(s.mqtt_host, s.mqtt_port, identifier="gateway-fiscalizacion",
                                          clean_session=False) as cliente:
                    await cliente.subscribe("obu/+/telemetria", qos=1)
                    log.info("Conectado a MQTT %s:%s", s.mqtt_host, s.mqtt_port)
                    espera = 1
                    async for msg in cliente.messages:
                        bus = bus_coincide(str(msg.topic), msg.payload)
                        if bus is None:
                            descartados += 1
                            log.warning("Mensaje descartado (tópico/bus no coinciden o JSON inválido)")
                            continue
                        await productor.send(s.topic_raw, key=bus.encode(), value=msg.payload)
                        reenviados += 1
                        if reenviados % 500 == 0:
                            log.info("Reenviados=%d descartados=%d", reenviados, descartados)
            except aiomqtt.MqttError as e:
                log.warning("MQTT desconectado (%s). Reintento en %ds", e, espera)
                await asyncio.sleep(espera)
                espera = min(espera * 2, 30)            # backoff exponencial
    finally:
        await productor.stop()


if __name__ == "__main__":
    asyncio.run(main())
