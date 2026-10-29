"""WebSocket (WSS en producción): alertas y estado de flota en tiempo real."""
import asyncio
import time

from fastapi import APIRouter, Query, WebSocket

from ..errors import ErrorDominio
from ..security import decodificar_token
from ..services.difusion import Conexion, resumen_flota

router = APIRouter()


@router.websocket("/ws")
async def ws(websocket: WebSocket, token: str = Query(...)):
    c = websocket.app.state.c
    try:   # los navegadores no pueden enviar cabeceras en WebSocket: el JWT viaja como parámetro
        claims = decodificar_token(token, secret=c.settings.jwt_secret, alg=c.settings.jwt_alg, scope="access")
    except ErrorDominio:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    con = Conexion(exp=claims["exp"])
    c.hub.agregar(con)
    recv = asyncio.create_task(websocket.receive_text())
    try:
        await websocket.send_json({"tipo": "flota", "datos": resumen_flota(await c.repos.flota.snapshot())})
        while True:
            get = asyncio.create_task(con.queue.get())
            hecho, _ = await asyncio.wait({recv, get}, timeout=5, return_when=asyncio.FIRST_COMPLETED)
            if recv in hecho:
                try:
                    recv.result()                       # mensaje del cliente (ping): se ignora
                except Exception:
                    get.cancel()
                    break                               # el cliente cerró la conexión
                recv = asyncio.create_task(websocket.receive_text())
            if get in hecho:
                await websocket.send_json(get.result())
            else:
                get.cancel()
            if time.time() > con.exp:                   # el token venció: el cliente debe renovarlo y reconectar
                await websocket.close(code=4401)
                break
    except Exception:
        pass
    finally:
        c.hub.quitar(con)
        recv.cancel()
