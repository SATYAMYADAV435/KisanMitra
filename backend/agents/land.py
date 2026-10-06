"""
KisanMitra — backend/agents/land.py
Land & region agent returning shared AgentResult contract per ARCHITECTURE.md §2 & §3.
"""

from typing import Optional
from backend.schemas import AgentResult, FarmerProfile
from backend.tools.regions import get_district_info

def run_land_agent(profile: FarmerProfile, crop: Optional[str] = None) -> AgentResult:
    district = profile.district or "nashik"
    info = get_district_info(district)

    if not info:
        return AgentResult(
            agent="land",
            finding=f"जमिनीचा प्रकार मध्यम काळी असून रब्बी हंगामासाठी उपयुक्त आहे.",
            risk="low",
            evidence=[f"District: {district}"],
            data_source="regions.json",
            next_check=None
        )

    soils = profile.soil_type or ", ".join(info.get("typical_soils", ["medium_black"]))
    rainfall = info.get("annual_rainfall_mm", 700)
    zone = info.get("climate_zone", "Transition Zone")
    lang = profile.language or "mr"
    farm_name = profile.farm_name or ("Your Farm" if lang == "en" else "आपका खेत" if lang == "hi" else "तुमची शेती")
    soil_ph = profile.soil_ph or "6.8"

    if lang == "en":
        finding = (
            f"{farm_name} ({district.capitalize()}): Soil is '{soils.replace('_', ' ')}' with pH {soil_ph}. "
            f"Annual rainfall is {rainfall} mm, suitable for rabi cropping under irrigation. "
            f"(Indicative analysis, verify with soil health card)."
        )
    elif lang == "hi":
        finding = (
            f"{farm_name} ({district.capitalize()}): मिट्टी का प्रकार '{soils.replace('_', ' ')}' व pH {soil_ph} है। "
            f"वार्षिक वर्षा {rainfall} मिमी है, रबी फसलों के लिए उपयुक्त है। "
            f"(यह प्रातिनिधिक विश्लेषण है, सॉयल टेस्ट कार्ड जांचें)।"
        )
    else:
        finding = (
            f"{farm_name} ({district.capitalize()}): जमिनीचा प्रकार '{soils.replace('_', ' ')}' व pH {soil_ph} आहे. "
            f"पावसाचे प्रमाण {rainfall} मिमी असून जमीन रब्बी पिकांसाठी अनुकूल आहे. "
            f"(हे प्रातिनिधिक विश्लेषण आहे, सॉईल टेस्ट कार्ड तपासा)."
        )

    evidence = [
        f"Farm: {farm_name}",
        f"District: {district.capitalize()}",
        f"Farm Soil: {soils}",
        f"Soil pH: {soil_ph}",
        f"Climate Zone: {zone}",
        f"Annual Rainfall: {rainfall} mm"
    ]

    return AgentResult(
        agent="land",
        finding=finding[:400],
        risk="low",
        evidence=evidence,
        data_source="regions.json",
        next_check=None
    )

