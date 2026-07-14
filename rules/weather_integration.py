"""Open-Meteo Integration for Weather-Aware Logic"""
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