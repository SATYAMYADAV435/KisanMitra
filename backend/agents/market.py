"""
KisanMitra — backend/agents/market.py
Market agent returning shared AgentResult contract per ARCHITECTURE.md §2 & §3.
"""

from typing import Optional
from backend.schemas import AgentResult, FarmerProfile
from backend.tools.mandi import get_latest_price, get_price_trend

def run_market_agent(profile: FarmerProfile, crop: Optional[str] = "onion") -> AgentResult:
    target_crop = crop or "onion"
    district = profile.district or "nashik"

    price_info = get_latest_price(target_crop, district)
    trend_info = get_price_trend(target_crop, days=30)

    modal_price = price_info.get("modal_price", 1850)
    market = price_info.get("market", "APMC")
    pct_change = trend_info.get("pct_change", 0.0)
    direction = trend_info.get("direction", "stable")

    # Evaluate risk based on price crash or stability
    if direction == "down" and pct_change < -10.0:
        risk = "high"
    elif direction == "down":
        risk = "medium"
    else:
        risk = "low"

    trend_sign = "+" if pct_change > 0 else ""
    lang = profile.language or "mr"
    if lang == "en":
        finding = (
            f"At {market} APMC, modal price for {target_crop.capitalize()} is ₹{modal_price} per quintal. "
            f"30-day price trend has been {direction} ({trend_sign}{pct_change}%)."
        )
    elif lang == "hi":
        finding = (
            f"{market} मंडी में {target_crop.capitalize()} का औसत भाव ₹{modal_price} प्रति क्विंटल है। "
            f"पिछले ३० दिनों में भाव का रुख {direction} ({trend_sign}{pct_change}%) रहा है।"
        )
    else:
        finding = (
            f"{market} बाजारात {target_crop.capitalize()} पिकाचा आजचा सरासरी दर ₹{modal_price} प्रति क्विंटल आहे. "
            f"गेल्या ३० दिवसांत बाजारभाव कल {direction} ({trend_sign}{pct_change}%) राहिला आहे."
        )

    source_name = price_info.get("source", "MSAMB Archives")
    data_source = "agmarknet" if "Agmarknet" in source_name else "csv"

    evidence = [
        f"Commodity: {target_crop}",
        f"Market: {market}",
        f"Modal Price: ₹{modal_price}/quintal",
        f"Min-Max Range: ₹{price_info.get('min_price', 1200)} - ₹{price_info.get('max_price', 2200)}",
        f"30-day Trend: {direction} ({trend_sign}{pct_change}%)",
        f"Data Source: {source_name}"
    ]

    return AgentResult(
        agent="market",
        finding=finding[:400],
        risk=risk,
        evidence=evidence,
        data_source=data_source,
        next_check="Check daily APMC closing rate"
    )
