"""Geometría mínima: distancia de un punto a una ruta (polilínea)."""
from math import asin, cos, radians, sin, sqrt
from typing import Sequence

M_POR_GRADO = 111_194.9   # metros por grado de latitud (R * pi / 180)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = radians(lat1), radians(lat2)
    dphi, dl = p2 - p1, radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * 6_371_000 * asin(sqrt(a))


def distancia_a_polilinea_m(lat: float, lon: float, puntos: Sequence[Sequence[float]]) -> float:
    """Distancia mínima (m) del punto a cualquier segmento de la ruta.

    Usa una proyección plana local centrada en el punto: error despreciable
    para distancias de pocos km, y mucho más barato que geodésicas por segmento.
    """
    if not puntos:
        return float("inf")
    k = cos(radians(lat))

    def xy(p: Sequence[float]) -> tuple[float, float]:
        return (p[1] - lon) * k * M_POR_GRADO, (p[0] - lat) * M_POR_GRADO

    pts = [xy(p) for p in puntos]
    if len(pts) == 1:
        return sqrt(pts[0][0] ** 2 + pts[0][1] ** 2)
    mejor = float("inf")
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        dx, dy = bx - ax, by - ay
        largo2 = dx * dx + dy * dy
        t = 0.0 if largo2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / largo2))
        px, py = ax + t * dx, ay + t * dy
        mejor = min(mejor, sqrt(px * px + py * py))
    return mejor
