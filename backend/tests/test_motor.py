from datetime import datetime, timedelta, timezone

from app.domain.models import EstadoBus
from tests.conftest import tel


async def test_motor_detecta_exceso_y_respeta_cooldown(container):
    m = container.motor
    assert len(await m.procesar(tel(speed=90))) == 1
    assert await m.procesar(tel(seq=2, speed=92)) == []          # misma infracción dentro del cooldown
    assert await m.procesar(tel(seq=3, speed=30)) == []          # velocidad normal
    assert len(container.repos.infracciones.items) == 1


async def test_motor_ignora_bus_fuera_de_catalogo(container):
    assert await container.motor.procesar(tel(bus_id="BUS-999", speed=120)) == []


async def test_motor_perdida_de_senal_periodica(container):
    viejo = tel(ts=datetime.now(timezone.utc) - timedelta(seconds=400))
    await container.repos.flota.actualizar(viejo)
    creadas = await container.motor.revisar_periodicas()
    assert [c["tipo"] for c in creadas] == ["PERDIDA_SENAL"]
