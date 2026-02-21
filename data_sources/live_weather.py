"""Open-Meteo weather fetcher. Free API, no key required."""

from __future__ import annotations

import asyncio
import time

import httpx


class LiveWeatherFetcher:
    """Fetches current weather from Open-Meteo API with caching."""

    OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
    CACHE_TTL = 300  # 5 minutes

    def __init__(self, latitude: float = 48.8566, longitude: float = 2.3522) -> None:
        """Default location: Paris, France."""
        self.latitude = latitude
        self.longitude = longitude
        self._cache: dict | None = None
        self._cache_time: float = 0

    async def fetch(self) -> dict | None:
        """Fetch current weather. Returns None on failure."""
        now = time.time()
        if self._cache and (now - self._cache_time) < self.CACHE_TTL:
            return self._cache

        params = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "current": "temperature_2m,wind_speed_10m,relative_humidity_2m,surface_pressure,rain",
            "timezone": "auto",
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(self.OPEN_METEO_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            current = data.get("current", {})
            result = {
                "temperature": current.get("temperature_2m", 20.0),
                "wind_speed": current.get("wind_speed_10m", 10.0),
                "humidity": current.get("relative_humidity_2m", 50.0),
                "pressure": current.get("surface_pressure", 1013.0),
                "rain_probability": min(1.0, current.get("rain", 0.0) / 10.0),
            }

            self._cache = result
            self._cache_time = now
            return result

        except Exception:
            return self._cache  # Return stale cache or None
