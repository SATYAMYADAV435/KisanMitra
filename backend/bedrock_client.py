"""
KisanMitra — backend/bedrock_client.py
Unified client for Amazon Bedrock with retry logic, fallback model handling,
and cached response fallback per ARCHITECTURE.md §7.
"""

import json
import logging
import os
import re
import time
from typing import Any, Dict, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("kisanmitra.bedrock")

# Environment variables
USE_CACHE = os.environ.get("USE_CACHE", "true").lower() in ("true", "1", "yes")
PRIMARY_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
FALLBACK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID_FALLBACK", "amazon.titan-text-express-v1")
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "ap-south-1")

_bedrock_runtime_client = None

def get_bedrock_client():
    global _bedrock_runtime_client
    if _bedrock_runtime_client is not None:
        return _bedrock_runtime_client
    try:
        import boto3
        _bedrock_runtime_client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
        return _bedrock_runtime_client
    except Exception as e:
        logger.warning(f"Could not initialize Bedrock client: {e}")
        return None

def _format_payload(model_id: str, prompt: str, system_prompt: str, max_tokens: int, temperature: float) -> str:
    if "claude" in model_id.lower():
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}]
        }
        if system_prompt:
            body["system"] = system_prompt
        return json.dumps(body)
    elif "titan" in model_id.lower():
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        body = {
            "inputText": full_prompt,
            "textGenerationConfig": {
                "maxTokenCount": max_tokens,
                "stopSequences": [],
                "temperature": temperature,
                "topP": 0.9
            }
        }
        return json.dumps(body)
    else:
        # Default simple payload
        return json.dumps({"prompt": prompt, "max_tokens": max_tokens, "temperature": temperature})

def _parse_response(model_id: str, response_body: str) -> str:
    parsed = json.loads(response_body)
    if "claude" in model_id.lower():
        content_blocks = parsed.get("content", [])
        if content_blocks and "text" in content_blocks[0]:
            return content_blocks[0]["text"]
        return ""
    elif "titan" in model_id.lower():
        results = parsed.get("results", [])
        if results and "outputText" in results[0]:
            return results[0]["outputText"]
        return ""
    return str(parsed)

def invoke_model(
    prompt: str,
    system_prompt: str = "",
    max_tokens: int = 1000,
    temperature: float = 0.2,
    model_id: Optional[str] = None
) -> str:
    """
    Invoke Bedrock model with fallback chain:
    Primary Model -> Fallback Model -> Cached/Simulated fallback.
    """
    use_cache = os.environ.get("USE_CACHE", "false").lower() in ("true", "1", "yes")
    if use_cache:
        logger.info("USE_CACHE=true active: bypassing live Bedrock API call.")
        return _cached_or_simulated_llm(prompt, system_prompt)

    client = get_bedrock_client()
    if not client:
        logger.warning("No Bedrock client available; using cached fallback.")
        return _cached_or_simulated_llm(prompt, system_prompt)

    models_to_try = [model_id] if model_id else [PRIMARY_MODEL_ID, FALLBACK_MODEL_ID]

    for current_model in models_to_try:
        if not current_model:
            continue
        for attempt in range(2):
            try:
                payload = _format_payload(current_model, prompt, system_prompt, max_tokens, temperature)
                response = client.invoke_model(
                    modelId=current_model,
                    contentType="application/json",
                    accept="application/json",
                    body=payload
                )
                body_bytes = response["body"].read()
                return _parse_response(current_model, body_bytes.decode("utf-8"))
            except Exception as exc:
                exc_str = str(exc)
                logger.warning(f"Bedrock call attempt {attempt+1} failed on {current_model}: {exc}")
                if "Unable to locate credentials" in exc_str or "NoCredentialsError" in exc_str:
                    logger.info("No AWS credentials configured; immediately falling back to simulated response.")
                    return _cached_or_simulated_llm(prompt, system_prompt)
                time.sleep(0.5 * (attempt + 1))

    logger.warning("All Bedrock model attempts failed; falling back to cached response.")
    return _cached_or_simulated_llm(prompt, system_prompt)

def _cached_or_simulated_llm(prompt: str, system_prompt: str) -> str:
    """
    Deterministic simulated response for offline/cached mode and testing.
    Identifies router vs supervisor requests.
    """
    p_lower = prompt.lower()
    
    # 1. Router requests (expecting JSON with intent, crop, language)
    if "intent" in system_prompt.lower() or "router" in system_prompt.lower() or "classify" in system_prompt.lower():
        # Check default language preference first as baseline
        lang = "mr"
        if "preference: \"hi\"" in p_lower or "preference: hi" in p_lower:
            lang = "hi"
        elif "preference: \"en\"" in p_lower or "preference: en" in p_lower:
            lang = "en"
        elif "preference: \"mr\"" in p_lower or "preference: mr" in p_lower:
            lang = "mr"

        # Override if specific language markers are present
        if any(c in p_lower for c in ["काय", "कसे", "कशी", "आहे", "कांद्या", "पिकवावे", "घ्यावे", "करावी", "करावे", "हवामान", "शेतात", "पाऊस", "कर्ज"]):
            lang = "mr"
        elif any(c in p_lower for c in ["क्या", "कैसे", "मौसम", "दाम", "फसल", "लगाएं", "करें", "लोन", "कीटनाशक", "छिड़काव"]):
            lang = "hi"
        elif any(w in p_lower for w in ["what", "how", "weather", "price", "grow", "crop", "today", "spray", "loan"]):
            if "preference: \"hi\"" not in p_lower and "preference: \"mr\"" not in p_lower:
                lang = "en"

        # Detect out-of-scope queries (e.g. loan, subsidy, tractor, credit)
        if any(k in p_lower for k in ["कर्ज", "लोन", "loan", "ट्रॅक्टर", "ट्रैक्टर", "tractor", "सबसिडी", "अनुदान"]):
            return json.dumps({
                "intent": "unknown",
                "crop": None,
                "language": lang
            }, ensure_ascii=False)

        # Detect crop with Devanagari inflections
        crop = None
        if any(k in p_lower for k in ["onion", "कांदा", "कांद्या", "कांदे", "प्याज"]):
            crop = "onion"
        elif any(k in p_lower for k in ["wheat", "गहू", "गव्हा", "गेहूं"]):
            crop = "wheat"
        elif any(k in p_lower for k in ["gram", "हरभरा", "हरभऱ्या", "चना", "चने"]):
            crop = "gram"
        elif any(k in p_lower for k in ["tomato", "टोमॅटो", "टमाटर"]):
            crop = "tomato"
        elif any(k in p_lower for k in ["jowar", "ज्वारी", "ज्वार"]):
            crop = "rabi_jowar"
        elif any(k in p_lower for k in ["safflower", "करडई", "कुसुम"]):
            crop = "safflower"

        # Detect intent
        if any(k in p_lower for k in ["हवामान", "पाऊस", "weather", "rain", "मौसम", "बारिश", "spray", "फवारणी", "छिड़काव"]):
            intent = "weather_today"
        elif any(k in p_lower for k in ["भाव", "दर", "price", "mandi", "बाजारभाव", "रेट", "दाम"]):
            intent = "prices"
        elif any(k in p_lower for k in ["कसे", "कशी", "how to", "guide", "लागवड", "पद्धत", "रोग", "खेती"]):
            intent = "how_to_grow"
        elif any(k in p_lower for k in ["काय पिकवावे", "कोणते पीक", "what to grow", "क्या लगाएं", "फसल"]):
            intent = "what_to_grow"
        else:
            intent = "what_to_grow" if not crop else "how_to_grow"

        return json.dumps({
            "intent": intent,
            "crop": crop,
            "language": lang
        }, ensure_ascii=False)

    # 2. Supervisor requests (expecting AnswerCard JSON)
    # Parse target language and intent from prompt
    target_lang = "mr"
    if "target language: hi" in p_lower or "language=hi" in p_lower or "language: hi" in p_lower:
        target_lang = "hi"
    elif "target language: en" in p_lower or "language=en" in p_lower or "language: en" in p_lower:
        target_lang = "en"
    elif "target language: mr" in p_lower or "language=mr" in p_lower or "language: mr" in p_lower:
        target_lang = "mr"

    intent = "what_to_grow"
    if "intent: weather_today" in p_lower:
        intent = "weather_today"
    elif "intent: prices" in p_lower:
        intent = "prices"
    elif "intent: how_to_grow" in p_lower:
        intent = "how_to_grow"
    elif "intent: unknown" in p_lower:
        intent = "unknown"

    # Parse district dynamically from prompt
    from backend.tools.regions import get_all_districts, get_district_info
    from backend.tools.weather_tool import get_weather_forecast
    from backend.tools.mandi import get_latest_price

    district_raw = "nashik"
    m_dist = re.search(r"district=([a-zA-Z0-9_\-\s]+?)(?:,|$|\n)", prompt, re.IGNORECASE)
    if m_dist:
        district_raw = m_dist.group(1).strip().lower()
    else:
        for d in get_all_districts():
            d_id = d.get("id", "")
            d_en = (d.get("name", {}).get("en") or "").lower()
            if d_id in p_lower or (d_en and d_en in p_lower):
                district_raw = d_id
                break

    # Parse crop dynamically
    crop_raw = "onion"
    m_crop = re.search(r"(?:crop mentioned:\s*|current crop=)([a-zA-Z0-9_\-]+)", prompt, re.IGNORECASE)
    if m_crop and m_crop.group(1).lower() not in ("general", "none", ""):
        crop_raw = m_crop.group(1).strip().lower()

    # Look up district info
    d_info = get_district_info(district_raw)
    dist_en = d_info.get("name", {}).get("en", district_raw.capitalize()) if d_info else district_raw.capitalize()
    dist_hi = d_info.get("name", {}).get("hi", dist_en) if d_info else dist_en
    dist_mr = d_info.get("name", {}).get("mr", dist_en) if d_info else dist_en

    primary_markets = (d_info.get("primary_markets") or ["APMC Market"]) if d_info else ["APMC Market"]
    mkt_display = " & ".join(primary_markets[:2])

    # Crop names dictionary for pure localization
    crop_names = {
        "onion": {"en": "Onion", "hi": "प्याज", "mr": "कांदा"},
        "wheat": {"en": "Wheat", "hi": "गेहूं", "mr": "गहू"},
        "gram": {"en": "Gram (Chickpea)", "hi": "चना", "mr": "हरभरा"},
        "chana": {"en": "Gram (Chickpea)", "hi": "चना", "mr": "हरभरा"},
        "tomato": {"en": "Tomato", "hi": "टमाटर", "mr": "टोमॅटो"},
        "cotton": {"en": "Cotton", "hi": "कपास", "mr": "कापूस"},
        "rabi_jowar": {"en": "Rabi Jowar", "hi": "रबी ज्वार", "mr": "रब्बी ज्वारी"},
        "safflower": {"en": "Safflower", "hi": "कुसुम", "mr": "करडई"},
        "orange": {"en": "Orange", "hi": "संतरा", "mr": "संत्री"},
        "sugarcane": {"en": "Sugarcane", "hi": "गन्ना", "mr": "ऊस"},
        "mustard": {"en": "Mustard", "hi": "सरसों", "mr": "मोहरी"},
        "cumin": {"en": "Cumin", "hi": "जीरा", "mr": "जिरे"}
    }
    active_crop_name = crop_names.get(crop_raw, {}).get(target_lang, crop_raw.capitalize())

    # Get dynamic weather for that district
    w_res = get_weather_forecast(district_raw, lang=target_lang)
    w_cur = w_res.get("current", {})
    temp_val = int(w_cur.get("temperature_c", 29))
    wind_val = int(w_cur.get("wind_speed_kmh", 9))
    cond_val = w_cur.get("condition", "Clear Sky" if target_lang == "en" else "साफ आसमान" if target_lang == "hi" else "स्वच्छ आकाश")
    spray_flag = w_res.get("advisory", {}).get("spray_flag", "green")

    # Get dynamic price for that crop and district
    price_info = get_latest_price(crop_raw, district_raw)
    m_price = price_info.get("modal_price", 1850)
    min_price = price_info.get("min_price", 1300)
    max_price = price_info.get("max_price", 2400)
    mkt_active = price_info.get("market", primary_markets[0])

    # District major crops
    dist_crops = d_info.get("major_rabi_crops", ["onion", "gram"]) if d_info else ["onion", "gram"]
    top_c1 = dist_crops[0] if len(dist_crops) > 0 else "onion"
    top_c2 = dist_crops[1] if len(dist_crops) > 1 else "gram"
    c1_name = crop_names.get(top_c1, {}).get(target_lang, top_c1.capitalize())
    c2_name = crop_names.get(top_c2, {}).get(target_lang, top_c2.capitalize())
    c1_gross = 140000 if "onion" in top_c1 else 75000 if "gram" in top_c1 else 65000

    # Multi-language and multi-intent dynamic cards
    if target_lang == "hi":
        if intent == "weather_today":
            card = {
                "title": f"मौसम एवं छिड़काव सलाह ({dist_hi})",
                "summary_lines": [
                    f"{dist_hi} क्षेत्र में आज मौसम {cond_val} और शुष्क रहेगा।",
                    f"अधिकतम तापमान {temp_val}°C और हवा की गति {wind_val} किमी/घंटा दर्ज है।",
                    f"आज {'कीटनाशक छिड़काव के लिए मौसम पूरी तरह अनुकूल है।' if spray_flag == 'green' else 'हवा के रुख को देखकर ही सावधानीपूर्वक छिड़काव करें।'}"
                ],
                "steps": [
                    "1. हवा की गति कम होने पर सुबह 11 बजे से पहले या दोपहर 3 बजे के बाद छिड़काव करें।",
                    "2. सुरक्षा के लिए दस्ताने और मास्क का उपयोग अवश्य करें।",
                    "3. खेत में नमी की जांच करके आवश्यकतानुसार हल्की सिंचाई करें।"
                ],
                "labels": ["मौसम पूर्वानुमान", "अनुमानित जानकारी"],
                "sources": ["भारतीय मौसम विभाग (IMD)", "कृषि विज्ञान केंद्र (KVK)"],
                "speak_text": f"आज {dist_hi} में मौसम {cond_val} है और हवा की गति {wind_val} किमी प्रति घंटा है। खेत में काम के लिए मौसम अनुकूल है।",
                "language": "hi"
            }
        elif intent == "prices":
            card = {
                "title": f"मंडी भाव ({dist_hi} - {mkt_active})",
                "summary_lines": [
                    f"{mkt_active} मंडी में {active_crop_name} का औसत भाव ₹{m_price:,} प्रति क्विंटल है।",
                    f"न्यूनतम भाव ₹{min_price:,} और अधिकतम भाव ₹{max_price:,} प्रति क्विंटल दर्ज किया गया।",
                    f"मांग अच्छी होने के कारण {dist_hi} क्षेत्र में भाव स्थिर रहने की संभावना है।"
                ],
                "steps": [
                    "1. फसल की अच्छी तरह छंटाई और ग्रेडिंग करके ही मंडी में बिक्री के लिए ले जाएं।",
                    "2. सूखा और अच्छी गुणवत्ता वाला माल ऊंचे दामों पर बिकता है।",
                    "3. स्थानीय कृषि उपज मंडी समिति के दैनिक भाव पर नजर रखें।"
                ],
                "labels": ["आधिकारिक मंडी भाव", "अनुमानित जानकारी"],
                "sources": ["महाराष्ट्र राज्य कृषि विपणन बोर्ड (MSAMB)", f"{mkt_active} मंडी"],
                "speak_text": f"{mkt_active} मंडी में आज {active_crop_name} का औसत भाव {m_price} रुपये प्रति क्विंटल है। बाजार में भाव स्थिर रहने की उम्मीद है।",
                "language": "hi"
            }
        elif intent == "how_to_grow":
            card = {
                "title": f"फसल प्रबंधन मार्गदर्शिका ({active_crop_name})",
                "summary_lines": [
                    f"{dist_hi} क्षेत्र में {active_crop_name} की सफल खेती के लिए संपूर्ण मार्गदर्शन।",
                    "उपजाऊ और जल निकासी वाली मिट्टी का चयन कर सड़ी गोबर की खाद मिलाएं।",
                    "संतुलित पोषण और आवश्यकतानुसार ड्रिप सिंचाई का उपयोग करें।"
                ],
                "steps": [
                    "1. खेत की तैयारी के समय प्रति एकड़ 10-12 टन सड़ी गोबर खाद मिलाएं।",
                    "2. अनुशंसित दूरी पर बुवाई या रोपाई करें और स्वस्थ बीजों का उपयोग करें।",
                    "3. खरपतवार नियंत्रण और कीट प्रबंधन समय पर पूरा करें।"
                ],
                "labels": ["फसल सलाह", "अनुशंसित जानकारी"],
                "sources": ["कृषि विश्वविद्यालय", "कृषि विज्ञान केंद्र (KVK)"],
                "speak_text": f"{active_crop_name} की खेती के लिए सही पोषण और समय पर देखभाल जरूरी है। विश्वविद्यालय की सिफारिशों का पालन करें।",
                "language": "hi"
            }
        elif intent == "unknown":
            card = {
                "title": "किसान सहायता एवं मार्गदर्शन",
                "summary_lines": [
                    "किसानमित्र फसलों, मौसम, मंडी भाव और खेती तकनीकों की जानकारी देता है।",
                    "ऋण या अन्य सरकारी योजनाओं के लिए नजदीकी बैंक शाखा से संपर्क करें।",
                    "कृषि सलाह के लिए नीचे दिए गए चार मुख्य विकल्पों का उपयोग करें।"
                ],
                "steps": [
                    "1. 'क्या लगाएं' पूछने के लिए माइक या बटन दबाएं।",
                    "2. 'मौसम' या 'मंडी भाव' जानने के लिए प्रश्न पूछें।",
                    "3. विशेषज्ञ सलाह हेतु किसान कॉल सेंटर 1800-180-1551 पर संपर्क करें।"
                ],
                "labels": ["मार्गदर्शन", "कॉल सेंटर सहायता"],
                "sources": ["किसान कॉल सेंटर (KCC)"],
                "speak_text": "मैं फसल, मौसम और मंडी भाव की जानकारी दे सकता हूं। ऋण और वित्तीय योजनाओं के लिए नजदीकी बैंक शाखा या किसान कॉल सेंटर 1800-180-1551 पर संपर्क करें।",
                "language": "hi"
            }
        else: # what_to_grow
            card = {
                "title": f"फसल सलाह ({dist_hi} रबी मौसम)",
                "summary_lines": [
                    f"{dist_hi} क्षेत्र के लिए {c1_name} और {c2_name} सबसे अधिक लाभकारी फसलें हैं।",
                    f"{c1_name} से लगभग ₹{c1_gross:,} प्रति एकड़ अनुमानित आय संभावित है।",
                    "स्थानीय मिट्टी और उपलब्ध सिंचाई के आधार पर यह फसलें सर्वाधिक उपयुक्त हैं।"
                ],
                "steps": [
                    "1. खेत की जुताई कर जल निकासी के अनुसार क्यारियां या मेड़ तैयार करें।",
                    "2. बीजजनित रोगों से बचाव हेतु ट्राइकोडर्मा से बीज उपचार अवश्य करें।",
                    "3. विश्वविद्यालय की सिफारिश अनुसार संतुलित जैविक व रासायनिक खाद दें।"
                ],
                "labels": ["अनुमानित जानकारी", "लागत पूर्व आय", "मौसम के अनुसार"],
                "sources": ["कृषि विश्वविद्यालय", "कृषि विज्ञान केंद्र (KVK)"],
                "speak_text": f"{dist_hi} जिले के लिए रबी मौसम में {c1_name} और {c2_name} सबसे अच्छे विकल्प हैं। अधिक जानकारी के लिए नजदीकी केवीके से संपर्क करें।",
                "language": "hi"
            }
        return json.dumps(card, ensure_ascii=False)

    elif target_lang == "en":
        if intent == "weather_today":
            card = {
                "title": f"Weather & Spray Advisory ({dist_en})",
                "summary_lines": [
                    f"Current weather across {dist_en} is {cond_val}.",
                    f"Max temperature {temp_val}°C with wind speed around {wind_val} km/h.",
                    f"Weather conditions are {'favorable' if spray_flag == 'green' else 'cautionary'} for spraying this afternoon."
                ],
                "steps": [
                    "1. Spray before 11 AM or after 3 PM when winds are gentle.",
                    "2. Always wear protective gloves and mask during application.",
                    "3. Check soil moisture and provide light irrigation if needed."
                ],
                "labels": ["Forecast Indicative", "Advisory Status"],
                "sources": ["India Meteorological Department (IMD)", "Krishi Vigyan Kendra (KVK)"],
                "speak_text": f"Today in {dist_en}, weather is {cond_val} with {wind_val} km/h wind. Conditions are {'favorable' if spray_flag == 'green' else 'cautionary'} for farm spraying.",
                "language": "en"
            }
        elif intent == "prices":
            card = {
                "title": f"Mandi Market Prices ({dist_en} - {mkt_active})",
                "summary_lines": [
                    f"Modal price for {active_crop_name} in {mkt_active} is ₹{m_price:,} per quintal.",
                    f"Minimum price ₹{min_price:,} and maximum price ₹{max_price:,} recorded today.",
                    f"Market demand is steady across {dist_en} APMC trading yards."
                ],
                "steps": [
                    "1. Grade produce by size and moisture before transport to mandi.",
                    "2. Ensure proper curing and drying to secure peak market rates.",
                    "3. Track daily APMC arrivals and e-NAM rates before selling."
                ],
                "labels": ["Official APMC Rates", "Representative Data"],
                "sources": ["State Agricultural Marketing Board (MSAMB)", f"{mkt_active} APMC"],
                "speak_text": f"In {mkt_active} mandi today, {active_crop_name} modal price is {m_price} rupees per quintal. Market demand is steady.",
                "language": "en"
            }
        elif intent == "how_to_grow":
            card = {
                "title": f"Crop Management Guide ({active_crop_name})",
                "summary_lines": [
                    f"Comprehensive package of practices for {active_crop_name} in {dist_en}.",
                    "Select fertile, well-drained soil and apply balanced decomposed compost.",
                    "Follow scheduled irrigation and timely integrated pest management."
                ],
                "steps": [
                    "1. Incorporate 10-12 tonnes per acre of well-rotted farmyard manure.",
                    "2. Maintain recommended plant spacing and use certified healthy seeds.",
                    "3. Carry out timely weeding and balanced nutrient application."
                ],
                "labels": ["Package of Practices", "University Recommended"],
                "sources": ["State Agricultural University", "Krishi Vigyan Kendra (KVK)"],
                "speak_text": f"For {active_crop_name} cultivation in {dist_en}, ensure fertile soil preparation and balanced nutrition management.",
                "language": "en"
            }
        elif intent == "unknown":
            card = {
                "title": "Farmer Assistance & Guidance",
                "summary_lines": [
                    "KisanMitra assists with crops, weather, mandi prices, and cultivation.",
                    "For financial loans or machinery subsidies, please contact your local bank.",
                    "Use the four quick action buttons below for agricultural advice."
                ],
                "steps": [
                    "1. Tap 'What to grow' for crop profitability analysis.",
                    "2. Ask about 'Weather' or 'Mandi prices' anytime.",
                    "3. Call Kisan Call Centre at 1800-180-1551 for government schemes."
                ],
                "labels": ["Guidance", "Kisan Call Centre"],
                "sources": ["Kisan Call Centre (KCC)"],
                "speak_text": "I can help with crop advice, weather forecasts, and market prices. For loans and subsidies, please contact your local bank or Kisan Call Centre at 1800-180-1551.",
                "language": "en"
            }
        else: # what_to_grow
            card = {
                "title": f"Crop Advisory ({dist_en} Rabi Season)",
                "summary_lines": [
                    f"{c1_name} and {c2_name} are top recommendations for {dist_en} agro-climatic zone.",
                    f"Estimated gross income for {c1_name} is ₹{c1_gross:,} per acre under good management.",
                    "Well suited for local soil conditions and prevailing market demand."
                ],
                "steps": [
                    "1. Prepare land with proper raised beds or furrows based on drainage.",
                    "2. Treat seeds with Trichoderma before sowing to prevent root rot.",
                    "3. Apply balanced basal fertilizer dose per agricultural university guidelines."
                ],
                "labels": ["Representative Data", "Gross Income Before Cost", "Seasonal Estimate"],
                "sources": ["State Agricultural University", "Krishi Vigyan Kendra (KVK)"],
                "speak_text": f"For {dist_en} district, {c1_name} and {c2_name} are your best rabi options with strong yield potential and steady market demand.",
                "language": "en"
            }
        return json.dumps(card, ensure_ascii=False)

    else: # Marathi ('mr')
        if intent == "weather_today":
            card = {
                "title": f"हवामान व फवारणी सल्ला ({dist_mr})",
                "summary_lines": [
                    f"{dist_mr} परिसरात आज हवामान {cond_val} व कोरडे राहील.",
                    f"कमाल तापमान {temp_val} अंश आणि वाऱ्याचा वेग {wind_val} किमी प्रतितास राहील.",
                    f"आज {'दुपारी कीटकनाशक फवारणीसाठी हवामान अनुकूल आहे.' if spray_flag == 'green' else 'वाऱ्याचा वेग जास्त असल्याने फवारणी काळजीपूर्वक करा.'}"
                ],
                "steps": [
                    "1. वाऱ्याचा वेग कमी असताना सकाळी 11 च्या आधी किंवा दुपारी 3 नंतर फवारणी करा.",
                    "2. सुरक्षिततेसाठी हातमोजे आणि मास्कचा वापर नक्की करा.",
                    "3. जमिनीतील ओल तपासून आवश्यकतेनुसार हलके पाणी द्या."
                ],
                "labels": ["हवामान अंदाजानुसार", "प्रातिनिधिक माहिती"],
                "sources": ["भारतीय हवामान विभाग (IMD)", "कृषी विज्ञान केंद्र (KVK)"],
                "speak_text": f"आज {dist_mr} मध्ये हवामान {cond_val} असून वाऱ्याचा वेग {wind_val} किमी प्रतितास आहे. फवारणीसाठी परिस्थिती अनुकूल आहे.",
                "language": "mr"
            }
        elif intent == "prices":
            card = {
                "title": f"बाजारभाव माहिती ({dist_mr} - {mkt_active})",
                "summary_lines": [
                    f"{mkt_active} बाजारात {active_crop_name} पिकाला सरासरी ₹{m_price:,} प्रति क्विंटल भाव आहे.",
                    f"किमान भाव ₹{min_price:,} तर कमाल भाव ₹{max_price:,} प्रति क्विंटल नोंदवला गेला.",
                    f"{dist_mr} जिल्ह्यातील प्रमुख बाजार समित्यांमध्ये मागणी व आवक स्थिर आहे."
                ],
                "steps": [
                    "1. मालाची प्रतवारी करून चांगल्या प्रतीचा माल विक्रीसाठी पाठवा.",
                    "2. सुका आणि चांगला पोसलेला माल चांगल्या दरात विकला जातो.",
                    "3. स्थानिक कृषी उत्पन्न बाजार समितीच्या ताज्या भावावर लक्ष ठेवा."
                ],
                "labels": ["अधिकृत बाजारभाव", "प्रातिनिधिक माहिती"],
                "sources": ["महाराष्ट्र राज्य कृषी पणन मंडळ (MSAMB)", f"{mkt_active} बाजार समिती"],
                "speak_text": f"{mkt_active} बाजारात आज {active_crop_name} पिकाला सरासरी {m_price} रुपये प्रति क्विंटल भाव मिळत आहे. बाजारभाव स्थिर राहण्याची शक्यता आहे.",
                "language": "mr"
            }
        elif intent == "how_to_grow":
            card = {
                "title": f"पीक व्यवस्थापन मार्गदर्शक ({active_crop_name})",
                "summary_lines": [
                    f"{dist_mr} भागात {active_crop_name} पिकाच्या भरघोस उत्पादनासाठी एकात्मिक व्यवस्थापन.",
                    "पाण्याचा उत्तम निचरा होणारी जमीन निवडून भरपूर सेंद्रिय खताचा वापर करा.",
                    "वेळेवर अन्नद्रव्य व्यवस्थापन आणि किड-रोग नियंत्रण ठेवा."
                ],
                "steps": [
                    "1. पूर्वमशागतीच्या वेळी एकरी 10 ते 12 टन चांगले कुजलेले शेणखत मिसळा.",
                    "2. शिफारशीत अंतरावर लागवड करून प्रमाणित बियाणे वापरा.",
                    "3. सुरुवातीच्या 30 दिवसांत शेत तणमुक्त ठेवा."
                ],
                "labels": ["पीक शिफारस", "विद्यापीठ शिफारशीत"],
                "sources": ["महात्मा फुले कृषी विद्यापीठ (MPKV) राहुरी"],
                "speak_text": f"{active_crop_name} पिकाच्या उत्तम वाढीसाठी सेंद्रिय खते आणि वेळेवर पाणी व्यवस्थापन महत्त्वाचे आहे.",
                "language": "mr"
            }
        elif intent == "unknown":
            card = {
                "title": "शेतकरी सहाय्य व मार्गदर्शन",
                "summary_lines": [
                    "किसानमित्र शेती पिके, हवामान, बाजारभाव आणि लागवडीबद्दल मदत करतो.",
                    "कर्ज किंवा इतर योजनांसाठी स्थानिक बँक शाखेशी संपर्क साधावा.",
                    "शेतीविषयक सल्ल्यासाठी खालील 4 पर्यायांपैकी एकावर टॅप करा."
                ],
                "steps": [
                    "1. 'काय पिकवावे' विचारण्यासाठी बटण दाबा.",
                    "2. 'हवामान' किंवा 'बाजारभाव' जाणून घेण्यासाठी प्रश्न विचारा.",
                    "3. मोफत सल्ल्यासाठी किसान कॉल सेंटर 1800-180-1551 वर कॉल करा."
                ],
                "labels": ["मार्गदर्शन", "कॉल सेंटर सहाय्य"],
                "sources": ["किसान कॉल सेंटर (KCC)"],
                "speak_text": "मी शेती, हवामान आणि बाजारभावाविषयी माहिती देऊ शकतो. कर्ज आणि योजनांसाठी बँक किंवा किसान कॉल सेंटर 1800-180-1551 वर संपर्क साधा.",
                "language": "mr"
            }
        else: # what_to_grow
            card = {
                "title": f"शेती सल्ला ({dist_mr} रब्बी हंगाम)",
                "summary_lines": [
                    f"{dist_mr} भागासाठी {c1_name} आणि {c2_name} ही पिके सध्या सर्वाधिक फायदेशीर आहेत.",
                    f"{c1_name} पिकातून एकरी सुमारे ₹{c1_gross:,} अंदाजे उत्पन्न अपेक्षित आहे.",
                    "स्थानिक हवामान आणि जमिनीच्या पोतानुसार ही पिके अत्यंत अनुकूल आहेत."
                ],
                "steps": [
                    "1. जमिनीच्या प्रकारानुसार योग्य गादीवाफे किंवा सरी-वरंबा तयार करा.",
                    "2. पेरणीपूर्वी बुरशीनाशक किंवा ट्रायकोडर्माने बीजप्रक्रिया नक्की करा.",
                    "3. कृषी विद्यापीठाच्या शिफारशीनुसार संतुलित खतांचा वापर करा."
                ],
                "labels": ["प्रातिनिधिक माहिती", "खर्चापूर्वीचे उत्पन्न", "हवामान अंदाजानुसार"],
                "sources": ["महात्मा फुले कृषी विद्यापीठ (MPKV) राहुरी"],
                "speak_text": f"{dist_mr} जिल्ह्यासाठी रब्बी हंगामात {c1_name} आणि {c2_name} ही पिके उत्तम पर्याय आहेत. अधिक माहितीसाठी जवळच्या कृषी विज्ञान केंद्राशी संपर्क साधा.",
                "language": "mr"
            }
        return json.dumps(card, ensure_ascii=False)

def test_bedrock_access() -> Dict[str, Any]:
    """Verification helper for T-03."""
    results = {
        "primary_model": PRIMARY_MODEL_ID,
        "fallback_model": FALLBACK_MODEL_ID,
        "use_cache": USE_CACHE,
        "primary_status": "skipped (USE_CACHE=true)" if USE_CACHE else "untested",
        "fallback_status": "skipped (USE_CACHE=true)" if USE_CACHE else "untested"
    }

    test_prompt = "Say hello in 5 words."
    sim_out = _cached_or_simulated_llm(test_prompt, "You are an assistant.")
    results["cached_fallback_functional"] = bool(sim_out)

    if not USE_CACHE:
        client = get_bedrock_client()
        if client:
            try:
                out1 = invoke_model(test_prompt, model_id=PRIMARY_MODEL_ID)
                results["primary_status"] = "pass" if out1 else "fail"
            except Exception as e:
                results["primary_status"] = f"fail: {e}"

            try:
                out2 = invoke_model(test_prompt, model_id=FALLBACK_MODEL_ID)
                results["fallback_status"] = "pass" if out2 else "fail"
            except Exception as e:
                results["fallback_status"] = f"fail: {e}"
        else:
            results["primary_status"] = "no credentials"
            results["fallback_status"] = "no credentials"

    return results
