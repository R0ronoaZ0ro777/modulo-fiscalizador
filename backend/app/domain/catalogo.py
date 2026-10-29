"""Catálogo de demostración: concesionarias ficticias, rutas aproximadas de Santiago,
buses, usuarios y umbrales iniciales. Lo usan el seed, el simulador y las pruebas."""

CONCESIONARIAS = [
    (1, "Buses Metropolitanos S.A."),
    (2, "Transporte Andes Ltda."),
    (3, "Alameda Mobility SpA"),
]

# Geometrías aproximadas (lat, lon) — solo con fines de demostración.
RUTAS = {
    "102": {"nombre": "Estación Central – Plaza Baquedano", "concesionaria_id": 1, "geometria": [
        [-33.4519, -70.6786], [-33.4501, -70.6700], [-33.4455, -70.6600],
        [-33.4402, -70.6430], [-33.4372, -70.6342]]},
    "205": {"nombre": "Plaza Baquedano – Escuela Militar", "concesionaria_id": 2, "geometria": [
        [-33.4372, -70.6342], [-33.4297, -70.6110], [-33.4222, -70.6040],
        [-33.4180, -70.5990], [-33.4084, -70.5860]]},
    "501": {"nombre": "Hipódromo – Santa Lucía", "concesionaria_id": 3, "geometria": [
        [-33.4150, -70.6560], [-33.4230, -70.6545], [-33.4320, -70.6530],
        [-33.4402, -70.6430]]},
}


def generar_buses(n: int) -> list[dict]:
    rutas = list(RUTAS)
    out = []
    for i in range(1, n + 1):
        ruta = rutas[(i - 1) % len(rutas)]
        out.append({"id": f"BUS-{i:03d}", "patente": f"FX{i:02d}{(i * 7) % 90 + 10}",
                    "ruta_id": ruta, "concesionaria_id": RUTAS[ruta]["concesionaria_id"]})
    return out


UMBRALES = [
    ("velocidad_max_kmh", 60.0, "km/h", "Velocidad máxima permitida en vía urbana"),
    ("desvio_max_m", 250.0, "m", "Distancia máxima permitida respecto al trazado autorizado"),
    ("senal_perdida_s", 180.0, "s", "Tiempo sin reportar antes de fiscalizar por pérdida de señal"),
]

# Rangos válidos para edición de umbrales (validación de negocio)
RANGOS_UMBRAL = {"velocidad_max_kmh": (20, 120), "desvio_max_m": (50, 2000), "senal_perdida_s": (30, 3600)}

# ⚠ Solo demostración. Los secretos TOTP son fijos para poder probar el MFA.
USUARIOS_DEMO = [
    {"email": "admin@mtt.cl", "nombre": "Ana Administradora", "password": "Admin#2026",
     "rol": "ADMIN", "mfa_enabled": True, "totp_secret": "JBSWY3DPEHPK3PXP"},
    {"email": "fiscalizador@mtt.cl", "nombre": "Felipe Fiscalizador", "password": "Fiscal#2026",
     "rol": "FISCALIZADOR", "mfa_enabled": True, "totp_secret": "KRSXG5CTMVRXEZLU"},
    {"email": "operador@mtt.cl", "nombre": "Olga Operadora", "password": "Operador#2026",
     "rol": "OPERADOR", "mfa_enabled": False, "totp_secret": None},
]
