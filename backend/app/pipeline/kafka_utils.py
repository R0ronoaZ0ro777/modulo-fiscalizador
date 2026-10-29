import asyncio
import logging

from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.errors import TopicAlreadyExistsError

log = logging.getLogger(__name__)


async def asegurar_topicos(settings, intentos: int = 30) -> None:
    """Crea los tópicos con varias particiones (clave = bus_id) si aún no existen."""
    nombres = (settings.topic_raw, settings.topic_validated, settings.topic_dlq)
    for i in range(1, intentos + 1):
        admin = AIOKafkaAdminClient(bootstrap_servers=settings.kafka_bootstrap)
        try:
            await admin.start()
            await admin.create_topics([NewTopic(n, settings.topic_partitions, 1) for n in nombres])
            return
        except TopicAlreadyExistsError:
            return
        except Exception as e:
            log.warning("Kafka no disponible (%s). Intento %d/%d", e.__class__.__name__, i, intentos)
            await asyncio.sleep(2)
        finally:
            await admin.close()
    raise RuntimeError("No fue posible conectar con Kafka")
