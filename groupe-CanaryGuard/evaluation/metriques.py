"""Taux et intervalles de confiance."""

from __future__ import annotations

import math


def wilson(succes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalle de confiance de Wilson à 95 % pour une proportion."""
    if n == 0:
        return (0.0, 0.0)
    p = succes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    marge = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - marge), min(1.0, centre + marge))


def taux(succes: int, n: int) -> dict:
    bas, haut = wilson(succes, n)
    return {"n": n, "succes": succes, "taux": succes / n if n else 0.0,
            "ic_bas": bas, "ic_haut": haut}