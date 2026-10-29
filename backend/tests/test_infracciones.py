import pytest

from app.domain.models import Actor, InfraccionCandidata
from app.errors import ConflictoEstado, PermisoDenegado, ReglaNegocio
from app.events import INFRACCION_ACTUALIZADA, INFRACCION_CREADA
from datetime import datetime, timezone
from tests.conftest import tel

FISC = Actor("00000000-0000-0000-0000-000000000002", "fiscalizador@mtt.cl", "FISCALIZADOR")
OPER = Actor("00000000-0000-0000-0000-000000000003", "operador@mtt.cl", "OPERADOR")
OBS = "Velocidad registrada por telemetría, confirmada con muestras."


async def _crear(c, sev="GRAVE"):
    return await c.infracciones.registrar_detectada(InfraccionCandidata(
        bus_id="BUS-001", tipo="EXCESO_VELOCIDAD", severidad=sev, detectada_en=datetime.now(timezone.utc),
        valor_medido=80, umbral=60))


async def test_registrar_publica_evento_y_audita(container):
    vistos = []
    container.bus.subscribe(INFRACCION_CREADA, lambda t, p: vistos.append(p))
    inf = await _crear(container)
    assert vistos and vistos[0]["id"] == inf["id"]
    assert container.repos.auditoria.filas[-1]["accion"] == "INFRACCION_DETECTADA"


async def test_cursar_multa_genera_acta_con_evidencia(container):
    await container.repos.telemetria.insertar_lote(None, [tel(speed=80)])
    inf = await _crear(container)
    eventos = []
    container.bus.subscribe(INFRACCION_ACTUALIZADA, lambda t, p: eventos.append(p))
    r = await container.infracciones.resolver(inf["id"], FISC, "CURSAR", OBS, {"tipo": "MULTA", "monto_uf": 10})
    assert r["infraccion"]["estado"] == "CURSADA"
    assert r["acta"]["id"] and eventos[0]["estado"] == "CURSADA"
    acta = container.repos.actas.items[0]
    assert len(acta["evidencia"]["muestras_telemetria"]) == 1
    assert container.repos.auditoria.filas[-1]["accion"] == "ACTA_CURSADA"


@pytest.mark.parametrize("resolucion,obs,sancion,fragmento", [
    ("CURSAR", "corto", {"tipo": "MULTA", "monto_uf": 5}, "20 caracteres"),
    ("CURSAR", OBS, None, "sanción"),
    ("CURSAR", OBS, {"tipo": "MULTA", "monto_uf": 0}, "monto"),
    ("CURSAR", OBS, {"tipo": "MULTA", "monto_uf": 9999}, "monto"),
    ("CURSAR", OBS, {"tipo": "AMONESTACION", "monto_uf": 3}, "no lleva monto"),
    ("DESCARTAR", "no", None, "motivo"),
    ("DESCARTAR", "Lectura errónea del GPS", {"tipo": "MULTA", "monto_uf": 1}, "no puede llevar sanción"),
])
async def test_validaciones_de_resolucion(container, resolucion, obs, sancion, fragmento):
    inf = await _crear(container)
    with pytest.raises(ReglaNegocio) as e:
        await container.infracciones.resolver(inf["id"], FISC, resolucion, obs, sancion)
    assert fragmento in e.value.mensaje
    assert container.repos.infracciones.items[inf["id"]]["estado"] == "DETECTADA"   # nada cambió


async def test_critica_no_se_resuelve_con_amonestacion(container):
    inf = await _crear(container, "CRITICA")
    with pytest.raises(ReglaNegocio):
        await container.infracciones.resolver(inf["id"], FISC, "CURSAR", OBS, {"tipo": "AMONESTACION"})


async def test_no_se_puede_resolver_dos_veces(container):
    inf = await _crear(container)
    await container.infracciones.resolver(inf["id"], FISC, "DESCARTAR", "Lectura errónea del GPS", None)
    with pytest.raises(ConflictoEstado):
        await container.infracciones.resolver(inf["id"], FISC, "DESCARTAR", "Lectura errónea del GPS", None)


async def test_operador_no_puede_resolver_pero_si_revisar(container):
    inf = await _crear(container)
    with pytest.raises(PermisoDenegado):
        await container.infracciones.resolver(inf["id"], OPER, "DESCARTAR", "Lectura errónea del GPS", None)
    r = await container.infracciones.marcar_en_revision(inf["id"], OPER)
    assert r["estado"] == "EN_REVISION"
    with pytest.raises(ConflictoEstado):          # ya no está recién detectada
        await container.infracciones.marcar_en_revision(inf["id"], OPER)
