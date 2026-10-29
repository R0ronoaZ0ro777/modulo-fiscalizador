import json


def json_safe(obj):
    """Convierte datetimes/UUID/Decimal a tipos JSON (para eventos y evidencia)."""
    return json.loads(json.dumps(obj, default=str))
