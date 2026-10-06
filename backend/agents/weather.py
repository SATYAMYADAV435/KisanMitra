"""
KisanMitra — backend/agents/weather.py
Weather agent returning shared AgentResult contract per ARCHITECTURE.md §2 & §3.
"""

from typing import Optional
from backend.schemas import AgentResult, FarmerProfile
from backend.tools.weather_tool import get_weather_forecast

def run_weather_agent(profile: FarmerProfile, crop: Optional[str] = None) -> AgentResult:
    district = profile.district or "nashik"
    lang = profile.language or "mr"
    forecast = get_weather_forecast(district, lang=lang)

    advisory = forecast.get("advisory", {})
    current = forecast.get("current", {})
    spray_flag = advisory.get("spray_flag", "green")

    # Map spray flag to risk level
    risk_map = {"green": "low", "amber": "medium", "red": "high"}
    risk = risk_map.get(spray_flag, "low")

    temp = current.get("temperature_c", 28.0)
    wind = current.get("wind_speed_kmh", 10.0)
    source = advisory.get("source", "open-meteo")
    data_source = "open-meteo" if "Live" in source else "cache"

    soil_temp = current.get("soil_temperature_0cm", temp - 1.5)
    soil_advice = advisory.get("soil_advice", "")
    finding = f"{advisory.get('spray_reason', 'हवामान अनुकूल आहे.')} {soil_advice} {advisory.get('irrigation_advice', '')}".strip()

    evidence = [
        f"District: {district.capitalize()}",
        f"Current Temp: {temp}°C",
        f"Soil Temp (0cm): {soil_temp}°C",
        f"Wind Speed: {wind} km/h",
        f"Spray Condition: {spray_flag.upper()}"
    ]

    return AgentResult(
        agent="weather",
        finding=finding[:400],
        risk=risk,
        evidence=evidence,
        data_source=data_source,
        next_check="Check again in 24 hours"
    )
