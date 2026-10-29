from app.services.auditoria import GENESIS


async def _llenar(container, n=5):
    for i in range(n):
        await container.auditoria.registrar(None, actor=None, accion="X", entidad="e", entidad_id=str(i),
                                            payload={"i": i, "texto": "ñandú"})


async def test_cadena_valida(container):
    await _llenar(container)
    r = await container.auditoria.verificar(None)
    assert r["valida"] and r["total"] == 5 and r["ultimo_hash"]
    assert container.repos.auditoria.filas[0]["prev_hash"] == GENESIS


async def test_detecta_modificacion_de_contenido(container):
    await _llenar(container)
    container.repos.auditoria.filas[2]["payload_canonico"] = '{"i":999}'
    r = await container.auditoria.verificar(None)
    assert not r["valida"] and r["primer_invalido"] == 3


async def test_detecta_fila_eliminada(container):
    await _llenar(container)
    del container.repos.auditoria.filas[1]
    r = await container.auditoria.verificar(None)
    assert not r["valida"] and "Enlace roto" in r["motivo"]
