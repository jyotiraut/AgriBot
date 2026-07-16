"""Open-Meteo Integration for Weather-Aware Logic"""
import time
import httpx
import logging

logger = logging.getLogger(__name__)

# Approximate coordinates for Nepal zones (Fallback)
NEPAL_ZONES = {
    "Terai": {"lat": 26.8, "lon": 85.5},
    "Hills": {"lat": 28.0, "lon": 84.0},
    "Mountains": {"lat": 29.0, "lon": 83.5}
}

def fetch_7_day_forecast(zone: str) -> dict:
    """
    Fetches the 7-day precipitation and temperature forecast from Open-Meteo.
    """
    coords = NEPAL_ZONES.get(zone, NEPAL_ZONES["Hills"])
    url = f"https://api.open-meteo.com/v1/forecast?latitude={coords['lat']}&longitude={coords['lon']}&daily=temperature_2m_max,temperature_2m_min,precipitation_sum&timezone=auto"
    
    try:
        response = httpx.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        daily = data.get("daily", {})
        forecasts = []
        
        # Check the next 3 days for heavy rain and general forecast
        heavy_rain_upcoming = False
        if "precipitation_sum" in daily:
            for i in range(3):
                if daily["precipitation_sum"][i] > 10.0: # More than 10mm
                    heavy_rain_upcoming = True
                    
        return {
            "forecast_available": True,
            "heavy_rain_upcoming": heavy_rain_upcoming,
            "raw_daily": daily
        }

    except Exception as e:
        logger.error(f"Error fetching Open-Meteo data: {e}")
        return {
            "forecast_available": False,
            "heavy_rain_upcoming": False
        }


def format_weather_for_disease_prompt(zone: str) -> str:
    try:
        forecast = fetch_7_day_forecast(zone)
        if forecast.get("heavy_rain_upcoming"):
            return f"⚠️ Heavy rain expected in {zone} zone. High disease risk."
        return f"Stable conditions in {zone} zone."
    except:
        return "Weather data unavailable."


# ── TTL cache — chat calls weather per turn; Open-Meteo shouldn't be ──────────
_WX_TTL_SECONDS = 3600
_wx_cache: dict = {}   # zone -> (fetched_at, forecast_dict)


def fetch_7_day_forecast_cached(zone: str, ttl: int = _WX_TTL_SECONDS) -> dict:
    """fetch_7_day_forecast with a per-zone TTL cache (default 1 h). Failed
    fetches (forecast_available=False) are not cached, so the next turn retries."""
    now = time.time()
    hit = _wx_cache.get(zone)
    if hit and now - hit[0] < ttl:
        return hit[1]
    data = fetch_7_day_forecast(zone)
    if data.get("forecast_available"):
        _wx_cache[zone] = (now, data)
    return data


def summarize_forecast(zone: str) -> dict:
    """Farming-relevant 7-day summary for a zone:
    {available, heavy_rain_upcoming, frost_risk, heat_stress, t_min, t_max,
     rain_3day_mm}. Thresholds: frost < 2°C min, heat > 35°C max, heavy rain
    already computed by fetch (>10 mm/day in next 3 days)."""
    fc = fetch_7_day_forecast_cached(zone)
    if not fc.get("forecast_available"):
        return {"available": False}
    daily = fc.get("raw_daily", {})
    t_max = [t for t in (daily.get("temperature_2m_max") or []) if t is not None]
    t_min = [t for t in (daily.get("temperature_2m_min") or []) if t is not None]
    rain  = [r for r in (daily.get("precipitation_sum") or []) if r is not None]
    return {
        "available":           True,
        "heavy_rain_upcoming": bool(fc.get("heavy_rain_upcoming")),
        "frost_risk":          bool(t_min) and min(t_min) < 2.0,
        "heat_stress":         bool(t_max) and max(t_max) > 35.0,
        "t_min":               round(min(t_min), 1) if t_min else None,
        "t_max":               round(max(t_max), 1) if t_max else None,
        "rain_3day_mm":        round(sum(rain[:3]), 1) if rain else None,
    }


def format_weather_facts(summary: dict, zone: str) -> str:
    """Compact DATA-block rendering of summarize_forecast for the chat LLM."""
    if not summary.get("available"):
        return "NO_DATA (weather service unavailable)"
    lines = [
        f"Zone: {zone} (7-day outlook)",
        f"Temperature: {summary['t_min']}°C to {summary['t_max']}°C",
        f"Rain next 3 days: {summary['rain_3day_mm']} mm",
    ]
    if summary["heavy_rain_upcoming"]:
        lines.append("ALERT: heavy rain expected within 3 days")
    if summary["frost_risk"]:
        lines.append("ALERT: frost risk (min below 2°C)")
    if summary["heat_stress"]:
        lines.append("ALERT: heat stress (max above 35°C)")
    return "\n".join(lines)