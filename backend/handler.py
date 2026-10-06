"""
KisanMitra — backend/handler.py
AWS Lambda Function URL entrypoint (thin wrapper) and full multi-agent pipeline per ARCHITECTURE.md §1 & §4.
Pipeline: POST /chat -> router -> parallel agents -> recommender/guide -> supervisor -> schema-validated AnswerCard.
"""

import json
import logging
from typing import Any, Dict

from backend.schemas import (
    FarmerProfile,
    safe_fallback_card,
    validate_answer_card_dict
)
from backend.router import route_query
from backend.recommender import recommend_crops
from backend.agents.weather import run_weather_agent
from backend.agents.land import run_land_agent
from backend.agents.market import run_market_agent
from backend.agents.crop_guide import run_crop_guide_agent
from backend.supervisor import synthesize_answer

logger = logging.getLogger("kisanmitra.handler")

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Content-Type": "application/json; charset=utf-8"
}

def get_hello_card(lang: str = "mr") -> Dict[str, Any]:
    """Returns a hardcoded welcome card conforming to ARCHITECTURE.md §3."""
    if lang == "hi":
        return {
            "title": "नमस्ते, मैं किसान मित्र हूँ",
            "summary_lines": [
                "अपनी भाषा में बोलकर या लिखकर खेती की सलाह लें।",
                "आज का मौसम, मंडी भाव और फसल प्रबंधन जानें।",
                "नाशिक रबी सीजन के लिए सेवाएं उपलब्ध हैं।"
            ],
            "steps": [
                "1. माइक बटन दबाएं और अपना सवाल पूछें।",
                "2. या नीचे दिए गए 4 फीचर कार्ड्स में से चुनें।",
                "3. उत्तर सुनने के लिए 'पुनः सुनें' बटन दबाएं।"
            ],
            "labels": ["डेमो संस्करण", "प्रातिनिधिक सलाह"],
            "sources": ["किसान मित्र सलाहकार प्रणाली"],
            "speak_text": "नमस्ते! किसान मित्र में आपका स्वागत है। बोलकर या नीचे दिए गए बटनों को दबाकर अपनी खेती की जानकारी प्राप्त करें।",
            "language": "hi",
            "metrics": [
                {"label": "मौसम", "value": "अनुकूल"},
                {"label": "सत्र", "value": "रबी २०२६"},
                {"label": "सहायता", "value": "उपलब्ध"}
            ]
        }
    elif lang == "en":
        return {
            "title": "Welcome to KisanMitra",
            "summary_lines": [
                "Ask farming queries by speaking or typing in your language.",
                "Access real-time weather, mandi prices, and crop guides.",
                "Tailored advisory for Maharashtra rabi season."
            ],
            "steps": [
                "1. Tap the giant mic button and ask your question.",
                "2. Or tap any of the 4 quick feature cards below.",
                "3. Tap 'Listen Again' anytime to replay the advice."
            ],
            "labels": ["Demo Version", "Indicative Advisory"],
            "sources": ["KisanMitra Advisory Core"],
            "speak_text": "Welcome to KisanMitra. Tap the microphone or select a feature card below to get personalized farm advisory.",
            "language": "en",
            "metrics": [
                {"label": "Season", "value": "Rabi 2026"},
                {"label": "Advisory", "value": "Certified"},
                {"label": "Support", "value": "24x7"}
            ]
        }
    else: # mr default
        return {
            "title": "नमस्कार, मी किसान मित्र आहे",
            "summary_lines": [
                "तुमच्या स्वतःच्या भाषेत बोलून किंवा लिहून शेती सल्ला मिळवा.",
                "आजचे हवामान, बाजार भाव आणि योग्य पीक व्यवस्थापन जाणून घ्या.",
                "नाशिक रब्बी हंगामासाठी अचूक माहिती उपलब्ध आहे."
            ],
            "steps": [
                "1. मोठा माइक बटन दाबा आणि आपला प्रश्न विचारा.",
                "2. किंवा खालील 4 पैकी एका पर्यायावर टॅप करा.",
                "3. दिलेला सल्ला पुन्हा ऐकण्यासाठी 'पुन्हा ऐका' दाबा."
            ],
            "labels": ["डेमो आवृत्ती", "प्रातिनिधिक सल्ला"],
            "sources": ["किसान मित्र सल्लागार प्रणाली"],
            "speak_text": "नमस्कार! किसान मित्र मध्ये आपले स्वागत आहे. बोला किंवा खालील बटनांवर टॅप करून आपल्या शेतीची माहिती मिळवा.",
            "language": "mr",
            "metrics": [
                {"label": "हंगाम", "value": "रब्बी २०२६"},
                {"label": "दर्जा", "value": "प्रमाणित"},
                {"label": "सल्ला", "value": "सक्रिय"}
            ]
        }

def process_chat_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    End-to-end /chat pipeline:
    1. Parse profile & query
    2. Route query to intent
    3. Run parallel agents
    4. Run recommender math (pure Python)
    5. Synthesize AnswerCard via supervisor
    6. Validate schema with safe fallback
    """
    raw_text = payload.get("text", "")
    explicit_intent = payload.get("intent")
    explicit_crop = payload.get("crop")
    user_lang = payload.get("language") or "mr"

    # Hello card if empty query or greeting without explicit action
    if (not raw_text or raw_text.strip().lower() in ("hello", "hi", "namaste", "namaskar", "नमस्कार", "नमस्ते")) and not explicit_intent:
        return get_hello_card(user_lang)

    # 1. Routing
    router_out = route_query(
        text=raw_text,
        default_lang=user_lang,
        explicit_intent=explicit_intent,
        explicit_crop=explicit_crop
    )

    # 2. Build Profile
    profile = FarmerProfile(
        district=payload.get("district", "nashik"),
        acres=float(payload.get("acres", 3.0)),
        water_source=payload.get("water_source", "well"),
        language=router_out.language,
        season=payload.get("season", "rabi"),
        farm_id=payload.get("farm_id"),
        farm_name=payload.get("farm_name", "Farm 1"),
        state=payload.get("state", "Maharashtra"),
        locality=payload.get("locality", ""),
        soil_type=payload.get("soil_type", "medium_black"),
        soil_ph=str(payload.get("soil_ph", "6.8")),
        soil_quality=payload.get("soil_quality", "good"),
        irrigation_type=payload.get("irrigation_type", "drip"),
        current_crop=payload.get("current_crop"),
        crop_stage=payload.get("crop_stage"),
        notes=payload.get("notes", "")
    )

    intent = router_out.intent
    target_crop = router_out.crop or profile.current_crop

    # 3. Agent Execution
    findings = []
    recommender_data = None

    if intent == "what_to_grow":
        # Run Weather, Land, Market agents + pure Python recommender math
        findings.append(run_weather_agent(profile))
        findings.append(run_land_agent(profile))
        findings.append(run_market_agent(profile, crop=target_crop or "onion"))
        recommender_data = recommend_crops(profile)

    elif intent == "weather_today":
        findings.append(run_weather_agent(profile))
        findings.append(run_land_agent(profile))

    elif intent == "prices":
        findings.append(run_market_agent(profile, crop=target_crop or "onion"))

    elif intent == "how_to_grow":
        findings.append(run_crop_guide_agent(profile, crop=target_crop or "onion"))
        findings.append(run_weather_agent(profile))

    else: # unknown
        # Friendly reply listing app capabilities and pointing to 4 buttons per PRD §9
        if user_lang == "hi":
            return {
                "title": "किसान मित्र सहायता",
                "summary_lines": [
                    "मैं मुख्य रूप से खेती, मौसम, मंडी भाव और फसलों की जानकारी दे सकता हूँ।",
                    "कृपया खेती से जुड़ा सवाल पूछें जैसे 'अभी कौन सी फसल लगाएं' या 'आज का मौसम'।",
                    "या नीचे दिए गए 4 फीचर कार्ड्स में से किसी एक पर टैप करें।"
                ],
                "steps": [
                    "1. 'क्या लगाएं' बटन दबाकर फसल सुझाव देखें।",
                    "2. 'आज का मौसम' दबाकर छिड़काव सलाह लें।",
                    "3. 'बाजार भाव' से मंडी के ताजा रेट जानें।"
                ],
                "labels": ["मार्गदर्शन", "सहायता"],
                "sources": ["किसान मित्र मार्गदर्शिका"],
                "speak_text": "माफ़ करें, मैं केवल खेती, मौसम, मंडी भाव और फसल सलाह में मदद कर सकता हूँ। कृपया नीचे दिए गए बटनों में से चुनें।",
                "language": "hi",
                "metrics": [
                    {"label": "सेवा", "value": "कृषि"},
                    {"label": "मौसम", "value": "सक्रिय"},
                    {"label": "मंडी", "value": "सक्रिय"}
                ]
            }
        elif user_lang == "en":
            return {
                "title": "KisanMitra Capabilities",
                "summary_lines": [
                    "I am specialized in farming advice, weather forecasts, mandi prices, and crop guides.",
                    "Please ask an agricultural query like 'What crop to grow now?' or 'Today's onion price'.",
                    "Or tap any of the 4 quick feature cards below."
                ],
                "steps": [
                    "1. Tap 'What to Grow' for rabi crop recommendations.",
                    "2. Tap 'Weather Today' for spray advisory.",
                    "3. Tap 'Mandi Prices' for live APMC market rates."
                ],
                "labels": ["Capabilities", "Help"],
                "sources": ["KisanMitra System Guide"],
                "speak_text": "I can help with crop planning, weather, mandi rates, and crop guides. Please select one of the feature cards below.",
                "language": "en",
                "metrics": [
                    {"label": "Service", "value": "Farming"},
                    {"label": "Weather", "value": "Active"},
                    {"label": "Mandi", "value": "Active"}
                ]
            }
        else: # mr
            return {
                "title": "किसान मित्र सहाय्य",
                "summary_lines": [
                    "मी प्रामुख्याने शेती सल्ला, आजचे हवामान, बाजार भाव आणि पीक नियोजनात मदत करतो.",
                    "कृपया शेतीविषयक प्रश्न विचारा, जसे की 'आता कोणते पीक घ्यावे' किंवा 'कांद्याचा भाव'.",
                    "किंवा खालील ४ मुख्य पर्यायांपैकी एकावर टॅप करा."
                ],
                "steps": [
                    "1. 'काय पिकवावे' दाबून रब्बी पिकांचे नियोजन पहा.",
                    "2. 'आजचे हवामान' दाबून फवारणी सल्ला घ्या.",
                    "3. 'बाजार भाव' दाबून आजचे बाजारभाव तपासा."
                ],
                "labels": ["मार्गदर्शन", "सहाय्य"],
                "sources": ["किसान मित्र मार्गदर्शिका"],
                "speak_text": "माफ करा, मी फक्त शेती, हवामान, बाजार भाव आणि पीक सल्ल्यात मदत करू शकतो. कृपया खालील पर्यायांपैकी एक निवडा.",
                "language": "mr",
                "metrics": [
                    {"label": "सेवा", "value": "शेती"},
                    {"label": "हवामान", "value": "सक्रिय"},
                    {"label": "बाजार", "value": "सक्रिय"}
                ]
            }

    # 4. Supervisor Synthesis
    card = synthesize_answer(
        router_output=router_out,
        profile=profile,
        agent_findings=findings,
        recommender_data=recommender_data
    )

    # 5. Schema Validation & Safe Fallback
    validated_card = validate_answer_card_dict(card.model_dump(), lang=router_out.language)
    return validated_card

def process_farm_intelligence_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    from backend.farm_intelligence import compute_farm_intelligence
    profile = FarmerProfile(
        district=payload.get("district", "nashik"),
        acres=float(payload.get("acres", 3.0)),
        water_source=payload.get("water_source", "well"),
        language=payload.get("language", "mr"),
        season=payload.get("season", "rabi"),
        farm_id=payload.get("farm_id"),
        farm_name=payload.get("farm_name", "Farm 1"),
        state=payload.get("state", "Maharashtra"),
        locality=payload.get("locality", ""),
        soil_type=payload.get("soil_type", "medium_black"),
        soil_ph=str(payload.get("soil_ph", "6.8")),
        soil_quality=payload.get("soil_quality", "good"),
        irrigation_type=payload.get("irrigation_type", "drip"),
        current_crop=payload.get("current_crop", "onion"),
        crop_stage=payload.get("crop_stage", "vegetative")
    )
    return compute_farm_intelligence(profile)

def process_crop_image_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    from backend.image_analyzer import analyze_crop_image
    image_b64 = payload.get("image") or payload.get("image_base64") or ""
    mime_type = payload.get("mime_type", "image/jpeg")
    farm_context = dict(payload.get("farm_context") or {})
    if not farm_context.get("language") and payload.get("language"):
        farm_context["language"] = payload.get("language")
    if not farm_context.get("current_crop") and (payload.get("crop") or payload.get("current_crop")):
        farm_context["current_crop"] = payload.get("crop") or payload.get("current_crop")
    if not farm_context.get("district") and payload.get("district"):
        farm_context["district"] = payload.get("district")
    if not farm_context.get("crop_stage") and payload.get("crop_stage"):
        farm_context["crop_stage"] = payload.get("crop_stage")
    return analyze_crop_image(image_b64, mime_type=mime_type, farm_context=farm_context)

def lambda_handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Lambda Function URL entry handler."""
    http_method = event.get("requestContext", {}).get("http", {}).get("method") or event.get("httpMethod", "GET")
    raw_path = event.get("rawPath") or event.get("path", "/")

    if http_method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": ""
        }

    if raw_path in ("/health", "/api/health"):
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps({"status": "ok", "service": "kisanmitra"})
        }

    if raw_path in ("/api/regions", "/regions"):
        from backend.tools.regions import get_all_districts, get_state_languages
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps({
                "districts": get_all_districts(),
                "state_languages": get_state_languages()
            }, ensure_ascii=False)
        }

    # Parse body
    try:
        body_str = event.get("body", "{}")
        if event.get("isBase64Encoded"):
            import base64
            body_str = base64.b64decode(body_str).decode("utf-8")
        payload = json.loads(body_str) if body_str else {}
    except Exception as e:
        logger.warning(f"Error parsing request body: {e}")
        payload = {}

    if raw_path in ("/api/farm-intelligence", "/farm-intelligence"):
        intel_res = process_farm_intelligence_request(payload)
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps(intel_res, ensure_ascii=False)
        }

    if raw_path in ("/api/crop-image-analysis", "/crop-image-analysis"):
        img_res = process_crop_image_request(payload)
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps(img_res, ensure_ascii=False)
        }

    # /chat endpoint default
    response_card = process_chat_request(payload)

    return {
        "statusCode": 200,
        "headers": CORS_HEADERS,
        "body": json.dumps(response_card, ensure_ascii=False)
    }
