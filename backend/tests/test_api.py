import pyotp

from app.domain.catalogo import USUARIOS_DEMO
from app.domain.models import InfraccionCandidata
from datetime import datetime, timezone

TOTP = {u["email"]: u["totp_secret"] for u in USUARIOS_DEMO}
PASS = {u["email"]: u["password"] for u in USUARIOS_DEMO}


async def sesion(client, email):
    r = await client.post("/api/auth/login", json={"email": email, "password": PASS[email]})
    assert r.status_code == 200, r.text
    d = r.json()
    if d["mfa_required"]:
        r = await client.post("/api/auth/mfa", json={"mfa_token": d["mfa_token"], "codigo": pyotp.TOTP(TOTP[email]).now()})
        assert r.status_code == 200, r.text
        d = r.json()
    return {"Authorization": f"Bearer {d['access_token']}"}, d


async def _infraccion(container, sev="GRAVE"):
    return await container.infracciones.registrar_detectada(InfraccionCandidata(
        "BUS-001", "EXCESO_VELOCIDAD", sev, datetime.now(timezone.utc), 80, 60))


async def test_login_con_mfa_y_sin_mfa(client):
    r = await client.post("/api/auth/login", json={"email": "fiscalizador@mtt.cl", "password": PASS["fiscalizador@mtt.cl"]})
    assert r.json()["mfa_required"] is True and "access_token" not in r.json()
    _, d = await sesion(client, "operador@mtt.cl")
    assert d["usuario"]["rol"] == "OPERADOR"
    _, d = await sesion(client, "fiscalizador@mtt.cl")
    assert d["usuario"]["rol"] == "FISCALIZADOR" and d["expires_in"] == 15 * 60


async def test_credenciales_y_codigo_incorrectos(client):
    r = await client.post("/api/auth/login", json={"email": "operador@mtt.cl", "password": "mala"})
    assert r.status_code == 401 and r.json()["codigo"] == "CREDENCIALES_INVALIDAS"
    r = await client.post("/api/auth/login", json={"email": "no@existe.cl", "password": "x"})
    assert r.status_code == 401
    r = await client.post("/api/auth/login", json={"email": "fiscalizador@mtt.cl", "password": PASS["fiscalizador@mtt.cl"]})
    r = await client.post("/api/auth/mfa", json={"mfa_token": r.json()["mfa_token"], "codigo": "000000"})
    assert r.status_code == 401


async def test_bloqueo_tras_intentos_fallidos(client):
    for _ in range(5):
        await client.post("/api/auth/login", json={"email": "operador@mtt.cl", "password": "mala"})
    r = await client.post("/api/auth/login", json={"email": "operador@mtt.cl", "password": PASS["operador@mtt.cl"]})
    assert r.status_code == 429 and r.json()["codigo"] == "CUENTA_BLOQUEADA"


async def test_sin_token_o_token_mfa_no_sirve(client):
    assert (await client.get("/api/flota")).status_code == 401
    r = await client.post("/api/auth/login", json={"email": "fiscalizador@mtt.cl", "password": PASS["fiscalizador@mtt.cl"]})
    h = {"Authorization": f"Bearer {r.json()['mfa_token']}"}
    assert (await client.get("/api/flota", headers=h)).status_code == 401      # el token de MFA no da acceso


async def test_rbac_resolver_solo_fiscalizador(client, container):
    inf = await _infraccion(container)
    body = {"resolucion": "DESCARTAR", "observaciones": "Lectura errónea del GPS"}
    h_op, _ = await sesion(client, "operador@mtt.cl")
    h_ad, _ = await sesion(client, "admin@mtt.cl")
    h_fi, _ = await sesion(client, "fiscalizador@mtt.cl")
    assert (await client.post(f"/api/infracciones/{inf['id']}/resolver", json=body, headers=h_op)).status_code == 403
    assert (await client.post(f"/api/infracciones/{inf['id']}/resolver", json=body, headers=h_ad)).status_code == 403
    r = await client.post(f"/api/infracciones/{inf['id']}/resolver", json=body, headers=h_fi)
    assert r.status_code == 200 and r.json()["infraccion"]["estado"] == "DESCARTADA"
    r = await client.post(f"/api/infracciones/{inf['id']}/resolver", json=body, headers=h_fi)
    assert r.status_code == 409 and r.json()["codigo"] == "CONFLICTO_ESTADO"


async def test_operador_no_ve_auditoria_ni_actas(client):
    h_op, _ = await sesion(client, "operador@mtt.cl")
    assert (await client.get("/api/auditoria", headers=h_op)).status_code == 403
    assert (await client.get("/api/actas", headers=h_op)).status_code == 403


async def test_validacion_de_entrada(client, container):
    inf = await _infraccion(container)
    h_fi, _ = await sesion(client, "fiscalizador@mtt.cl")
    r = await client.post(f"/api/infracciones/{inf['id']}/resolver", json={"resolucion": "OTRA"}, headers=h_fi)
    assert r.status_code == 422 and r.json()["codigo"] == "VALIDACION"
    r = await client.get("/api/infracciones/no-es-uuid", headers=h_fi)
    assert r.status_code == 422
    r = await client.get("/api/infracciones/00000000-0000-0000-0000-0000000000ff", headers=h_fi)
    assert r.status_code == 404
    r = await client.get("/api/infracciones?limit=9999", headers=h_fi)
    assert r.status_code == 422


async def test_auditoria_registra_y_verifica(client, container):
    inf = await _infraccion(container)
    h_fi, _ = await sesion(client, "fiscalizador@mtt.cl")
    await client.post(f"/api/infracciones/{inf['id']}/resolver", headers=h_fi,
                      json={"resolucion": "CURSAR", "observaciones": "Exceso confirmado con la telemetría.",
                            "sancion": {"tipo": "MULTA", "monto_uf": 12}})
    acciones = [f["accion"] for f in (await client.get("/api/auditoria", headers=h_fi)).json()["items"]]
    assert "ACTA_CURSADA" in acciones and "LOGIN_OK" in acciones
    v = (await client.get("/api/auditoria/verificar", headers=h_fi)).json()
    assert v["valida"] is True


async def test_umbrales_solo_admin_y_versionado_optimista(client):
    h_ad, _ = await sesion(client, "admin@mtt.cl")
    h_fi, _ = await sesion(client, "fiscalizador@mtt.cl")
    cuerpo = {"valor": 50, "version": 1}
    assert (await client.put("/api/umbrales/velocidad_max_kmh", json=cuerpo, headers=h_fi)).status_code == 403
    r = await client.put("/api/umbrales/velocidad_max_kmh", json=cuerpo, headers=h_ad)
    assert r.status_code == 200 and r.json()["version"] == 2
    r = await client.put("/api/umbrales/velocidad_max_kmh", json=cuerpo, headers=h_ad)      # versión desfasada
    assert r.status_code == 409 and r.json()["codigo"] == "CONFLICTO_VERSION"
    r = await client.put("/api/umbrales/velocidad_max_kmh", json={"valor": 500, "version": 2}, headers=h_ad)
    assert r.status_code == 422
