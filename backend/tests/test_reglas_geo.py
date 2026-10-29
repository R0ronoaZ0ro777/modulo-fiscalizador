from datetime import datetime, timedelta, timezone

from app.domain.catalogo import RUTAS
from app.domain.geo import distancia_a_polilinea_m
from app.domain.models import EstadoBus
from app.domain.reglas import ContextoRegla, DesvioRuta, ExcesoVelocidad, FabricaReglas, PerdidaSenalProlongada
from tests.conftest import UMBRALES, tel

RUTA = RUTAS["102"]["geometria"]
CTX = ContextoRegla(UMBRALES, RUTA, datetime.now(timezone.utc))


def test_distancia_punto_sobre_ruta_es_cero():
    assert distancia_a_polilinea_m(*RUTA[1], RUTA) < 1


def test_distancia_lateral_aproximada():
    lat, lon = RUTA[1]
    d = distancia_a_polilinea_m(lat + 450 / 111_195, lon, RUTA)       # ~450 m al norte
    assert 300 < d < 460


def test_exceso_velocidad_severidades():
    r = ExcesoVelocidad()
    assert r.evaluar(tel(speed=60), CTX) is None
    assert r.evaluar(tel(speed=70), CTX).severidad == "LEVE"
    assert r.evaluar(tel(speed=78), CTX).severidad == "GRAVE"
    assert r.evaluar(tel(speed=95), CTX).severidad == "CRITICA"


def test_desvio_ruta():
    r = DesvioRuta()
    en_ruta = tel(lat=RUTA[1][0], lon=RUTA[1][1])
    fuera = tel(lat=RUTA[1][0] + 400 / 111_195, lon=RUTA[1][1])
    assert r.evaluar(en_ruta, CTX) is None
    c = r.evaluar(fuera, CTX)
    assert c.tipo == "DESVIO_RUTA" and c.valor_medido > 250
    assert r.evaluar(fuera, ContextoRegla(UMBRALES, None, CTX.ahora)) is None   # sin ruta no se evalúa


def test_perdida_senal_solo_si_supera_umbral():
    r = PerdidaSenalProlongada()
    ts = datetime.now(timezone.utc)
    mk = lambda edad: EstadoBus("BUS-001", -33.4, -70.6, 30, 0, ts - timedelta(seconds=edad), edad, "SIN_SENAL")
    assert r.evaluar(mk(100), CTX) is None            # un túnel normal no se fiscaliza
    assert r.evaluar(mk(200), CTX).severidad == "LEVE"
    assert r.evaluar(mk(600), CTX).severidad == "GRAVE"


def test_fabrica_permite_extender_sin_tocar_el_motor():
    class SiempreInfringe:
        tipo = "EXCESO_VELOCIDAD"
        def evaluar(self, t, ctx): return "x"

    original = FabricaReglas._telemetria["EXCESO_VELOCIDAD"]
    try:
        FabricaReglas.registrar_telemetria(SiempreInfringe)
        assert any(isinstance(r, SiempreInfringe) for r in FabricaReglas.telemetria())
    finally:
        FabricaReglas._telemetria["EXCESO_VELOCIDAD"] = original
