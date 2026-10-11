"""Геокодинг через Nominatim (OpenStreetMap) и расстояние между точками."""
from __future__ import annotations

import asyncio
import json
import math
import urllib.parse
import urllib.request

UA = {"User-Agent": "DatingBot/1.0"}


def _http_get(url: str, timeout: int = 10) -> str | None:
    """Синхронный GET. None = нет сети/ошибка."""
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8")
    except Exception:
        return None


def _pick_city(data: dict) -> str | None:
    addr = data.get("address") or {}
    for key in ("city", "town", "village", "municipality", "county", "state"):
        if addr.get(key):
            return str(addr[key]).strip()
    disp = (data.get("display_name") or "").split(",")
    return disp[0].strip() if disp and disp[0].strip() else None


async def forward_city(name: str) -> dict | None:
    """Прямой геокодинг.

    Возвращает {'city', 'lat', 'lon'} если город найден,
    {'error': 'network'} если нет сети,
    None если город не найден.
    """
    q = (name or "").strip()
    if not q:
        return None
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": q, "format": "jsonv2", "limit": 1, "accept-language": "ru"})
    raw = await asyncio.to_thread(_http_get, url)
    if raw is None:
        return {"error": "network"}
    try:
        items = json.loads(raw)
    except Exception:
        return {"error": "network"}
    if not items:
        return None
    it = items[0]
    city = _pick_city(it)
    if not city:
        return None
    try:
        return {"city": city, "lat": float(it["lat"]), "lon": float(it["lon"])}
    except Exception:
        return None


async def reverse_city(lat: float, lon: float) -> dict | None:
    """Обратный геокодинг: координаты -> город. None = не вышло."""
    url = "https://nominatim.openstreetmap.org/reverse?" + urllib.parse.urlencode(
        {"lat": lat, "lon": lon, "format": "jsonv2", "accept-language": "ru"})
    raw = await asyncio.to_thread(_http_get, url)
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    city = _pick_city(data)
    if not city:
        return None
    return {"city": city, "lat": float(lat), "lon": float(lon)}


def haversine_km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    """Расстояние в км между двумя точками."""
    r = 6371.0
    d_lat = math.radians(b_lat - a_lat)
    d_lon = math.radians(b_lon - a_lon)
    s = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(a_lat)) * math.cos(math.radians(b_lat)) * math.sin(d_lon / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(s))
