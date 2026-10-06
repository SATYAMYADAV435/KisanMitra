"""
KisanMitra — backend/farm_intelligence.py
Personalized farm intelligence engine computing farm health, soil health,
crop risks, live weather, and stage-specific recommendations in the requested language.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from backend.schemas import FarmerProfile
from backend.tools.weather_tool import get_weather_forecast

def compute_farm_intelligence(profile: FarmerProfile) -> Dict[str, Any]:
    district = profile.district or "nashik"
    farm_name = profile.farm_name or "Farm 1"
    crop = (profile.current_crop or "onion").lower()
    stage = (profile.crop_stage or "vegetative").lower()
    soil = (profile.soil_type or "medium_black").lower()
    soil_ph = str(profile.soil_ph or "6.8").lower()
    water_source = (profile.water_source or "well").lower()
    irrigation = (profile.irrigation_type or "drip").lower()
    acres = profile.acres or 3.0
    lang = profile.language or "mr"

    # 1. Fetch live or cached weather in requested language
    weather = get_weather_forecast(district, lang=lang)
    current_weather = weather.get("current", {})
    weather_adv = weather.get("advisory", {})
    spray_flag = weather_adv.get("spray_flag", "green")
    temp_c = current_weather.get("temperature_c", 29.0)
    wind_kmh = current_weather.get("wind_speed_kmh", 9.5)

    # 2. Compute Soil Health Score (0-100)
    soil_score = 80
    soil_guidance = ""

    if "acid" in soil_ph or (soil_ph.replace(".", "").isdigit() and float(soil_ph) < 6.0):
        soil_score -= 15
        if lang == "en":
            soil_guidance = "Soil is acidic (< 6.0 pH). Apply 500 kg/acre Agricultural Lime to balance acidity."
        elif lang == "hi":
            soil_guidance = "मिट्टी अम्लीय (< 6.0 pH) है। अम्लता संतुलित करने के लिए 500 किग्रा/एकड़ कृषि चूना मिलाएं।"
        else:
            soil_guidance = "माती आम्लधर्मी (Acidic) आहे. ५०० किलो प्रति एकर कृषी चुना (Lime) मिसळा."
    elif "alkali" in soil_ph or (soil_ph.replace(".", "").isdigit() and float(soil_ph) > 8.0):
        soil_score -= 15
        if lang == "en":
            soil_guidance = "Soil is alkaline (> 8.0 pH). Apply Gypsum and increase decomposed farmyard manure."
        elif lang == "hi":
            soil_guidance = "मिट्टी क्षारीय (> 8.0 pH) है। जिप्सम और सड़ी हुई गोबर की खाद का भरपूर उपयोग करें।"
        else:
            soil_guidance = "माती क्षारयुक्त (Alkaline) आहे. जिप्सम आणि सेंद्रिय शेणखताचा भरपूर वापर करा."
    elif "unknown" in soil_ph or "don" in soil_ph:
        soil_score = 75
        if lang == "en":
            soil_guidance = "Soil test not completed yet. We recommend testing a sample at your nearest Krishi Vigyan Kendra (KVK)."
        elif lang == "hi":
            soil_guidance = "मिट्टी परीक्षण अभी नहीं हुआ है। नजदीकी कृषि विज्ञान केंद्र (KVK) से सॉयल हेल्थ कार्ड अवश्य बनवाएं।"
        else:
            soil_guidance = "माती परीक्षण अद्याप झालेले नाही. जवळच्या कृषी विज्ञान केंद्रातून (KVK) सॉईल हेल्थ कार्ड काढून घ्या."
    else:
        soil_score = 88
        if lang == "en":
            soil_guidance = "Soil pH is balanced (6.5 - 7.5). Continue applying organic matter and biofertilizers."
        elif lang == "hi":
            soil_guidance = "मिट्टी का पीएच संतुलित (6.5 - 7.5) है। जैविक खाद और संवर्धक जारी रखें।"
        else:
            soil_guidance = "मातीचा सामू (pH) आदर्श संतुलित आहे (६.५ ते ७.५). जिवाणू संवर्धक खते चालू ठेवा."

    if soil in ("medium_black", "deep_black", "alluvial_clay"):
        soil_score = min(100, soil_score + 5)

    # 3. Compute Crop Risk & Farm Health Score
    risk_level = "low"
    alerts: List[Dict[str, str]] = []
    recommendations: List[str] = []
    prompts: List[str] = []

    # Weather Alerts
    if spray_flag == "red" or wind_kmh > 18:
        risk_level = "high"
        if lang == "en":
            alerts.append({
                "type": "weather",
                "level": "high",
                "title": "Do Not Spray (High Wind)",
                "message": f"Wind speed is {wind_kmh} km/h. Pesticide spray drift will lead to wastage."
            })
        elif lang == "hi":
            alerts.append({
                "type": "weather",
                "level": "high",
                "title": "छिड़काव से बचें (तेज हवा)",
                "message": f"हवा की गति {wind_kmh} किमी/घंटा है। छिड़काव का बहाव होने से दवा व्यर्थ होगी।"
            })
        else:
            alerts.append({
                "type": "weather",
                "level": "high",
                "title": "फवारणी टाळा (High Wind)",
                "message": f"वाऱ्याचा वेग {wind_kmh} किमी/तास आहे. औषध हवेत उडून वाया जाईल."
            })
    elif spray_flag == "amber" or wind_kmh > 12:
        risk_level = "moderate"
        if lang == "en":
            alerts.append({
                "type": "weather",
                "level": "medium",
                "title": "Spray With Caution",
                "message": "Spray only during calm hours before 11:00 AM or after 4:00 PM."
            })
        elif lang == "hi":
            alerts.append({
                "type": "weather",
                "level": "medium",
                "title": "सावध छिड़काव",
                "message": "सुबह 11 बजे से पहले या शाम 4 बजे के बाद ही छिड़काव करें।"
            })
        else:
            alerts.append({
                "type": "weather",
                "level": "medium",
                "title": "सावध फवारणी (Caution)",
                "message": "सकाळी ११ च्या आधी किंवा संध्याकाळी ४ नंतरच फवारणी करावी."
            })
    else:
        if lang == "en":
            alerts.append({
                "type": "weather",
                "level": "low",
                "title": "Favorable Spray Conditions",
                "message": f"Temperature is {temp_c}°C with gentle breeze. Ideal window for field application."
            })
        elif lang == "hi":
            alerts.append({
                "type": "weather",
                "level": "low",
                "title": "छिड़काव के लिए अनुकूल मौसम",
                "message": f"तापमान {temp_c}°C है और हवा धीमी है। खेत में काम के लिए उत्तम दिन।"
            })
        else:
            alerts.append({
                "type": "weather",
                "level": "low",
                "title": "फवारणीस अनुकूल हवामान",
                "message": f"आज तापमान {temp_c}°C असून हलका वारा आहे. फवारणीसाठी योग्य दिवस."
            })

    # Crop & Stage Intelligence
    if "onion" in crop or "कांदा" in crop or "प्याज" in crop:
        if "sow" in stage or "पेरणी" in stage or "nurser" in stage or "रोपाई" in stage:
            if lang == "en":
                recommendations = [
                    "Treat onion seeds with Trichoderma @ 5g/kg before nursery sowing.",
                    "Ensure raised bed drainage and light irrigation at 10-12 day intervals.",
                    "Transplant seedlings only when 45-50 days old for sturdy root establishment."
                ]
                prompts = [
                    f"Nursery care schedule for {farm_name}",
                    "How to prevent damping-off in onion nursery?",
                    f"Today's onion mandi price in {district.capitalize()}"
                ]
            elif lang == "hi":
                recommendations = [
                    "प्याज नर्सरी में बीज को ट्राइकोडर्मा 5 ग्राम प्रति किलो से उपचारित करें।",
                    "उठी हुई क्यारियों पर 10-12 दिनों पर हल्की सिंचाई और जल निकासी रखें।",
                    "45-50 दिन के स्वस्थ पौधे होने पर ही मुख्य खेत में रोपाई करें।"
                ]
                prompts = [
                    f"{farm_name} के लिए प्याज नर्सरी प्रबंधन",
                    "प्याज रोपाई में मर रोग से कैसे बचें?",
                    f"{district.capitalize()} में आज प्याज का मंडी भाव क्या है?"
                ]
            else:
                recommendations = [
                    "रोपवाटिकेमध्ये ट्रायकोडर्मा ५ ग्रॅम प्रति किलो बियाण्यास चोळून पेरणी करा.",
                    "गादीवाफ्यावर १०-१२ दिवसांनी रोपांची हलकी विरळणी व पाणी व्यवस्थापन करा.",
                    "रोपे ४५-५० दिवसांची झाल्यावरच मुख्य शेतात पुनर्लागवड करा."
                ]
                prompts = [
                    f"{farm_name} साठी कांदा रोपवाटिका व्यवस्थापन",
                    "कांदा रोपांवर मर रोगासाठी काय फवारावे?",
                    f"{district.capitalize()} बाजारात कांद्याचे आजचे भाव काय आहेत?"
                ]
        elif "flower" in stage or "bulb" in stage or "फळ" in stage or "कंद" in stage:
            if lang == "en":
                recommendations = [
                    "Foliar spray 00:00:50 or 13:00:45 Potassium Sulphate for bulb sizing.",
                    "Monitor for thrips and purple blotch; apply Azadirachtin neem oil 5ml/L preventively.",
                    "Stop irrigation strictly 15 days prior to harvest to improve shelf life."
                ]
                prompts = [
                    f"Best fertilizer for onion bulb sizing in {farm_name}",
                    "How to control purple blotch in rabi onion?",
                    "When to stop watering onion before harvest?"
                ]
            elif lang == "hi":
                recommendations = [
                    "कंद फुलाव के लिए 00:00:50 या 13:00:45 पोटेशियम सल्फेट का छिड़काव करें।",
                    "थ्रिप्स और करपा रोग की रोकथाम हेतु नीम तेल 5 मिली/लीटर का छिड़काव करें।",
                    "भंडारण क्षमता बढ़ाने के लिए कटाई से 15 दिन पहले सिंचाई पूरी तरह बंद कर दें।"
                ]
                prompts = [
                    f"{farm_name} में प्याज कंद फुलाव हेतु श्रेष्ठ पोषण",
                    "प्याज में जामुनी धब्बा (Purple Blotch) का उपचार",
                    "प्याज कटाई और सुरक्षित भंडारण के नियम"
                ]
            else:
                recommendations = [
                    "कंद फुगवणीसाठी १३:००:४५ किंवा ००:००:५० पोटॅशियम खताची फवारणी करा.",
                    "थ्रिप्स (फुलकिडे) व करपा रोगासाठी निंबोळी अर्क ५ मिली/लिटरने फवारा.",
                    "काढणीपूर्वी १५ दिवस आधी पाणी देणे पूर्णपणे बंद करा."
                ]
                prompts = [
                    f"{farm_name} मध्ये कांदा कंद फुगवणीसाठी खत",
                    "कांद्यावरील जांभळा करपा नियंत्रण कसे करावे?",
                    "कांदा काढणी व साठवणूक तंत्र"
                ]
        else: # Vegetative
            if lang == "en":
                recommendations = [
                    f"Apply 19:19:19 soluble NPK via {irrigation} for balanced canopy growth.",
                    "Maintain soil moisture at field capacity; avoid water stagnation.",
                    "Keep weed-free in first 40 days to ensure vigorous root development."
                ]
                prompts = [
                    f"Fertigation schedule for {farm_name} onion",
                    "Today's weather and spray advice for onion",
                    f"Onion price forecast in {district.capitalize()} mandi"
                ]
            elif lang == "hi":
                recommendations = [
                    f"{irrigation} के माध्यम से 19:19:19 घुलनशील खाद देकर वानस्पतिक वृद्धि तेज करें।",
                    "खेत में नमी बनाए रखें, जलभराव न होने दें।",
                    "शुरुआती 40 दिनों में निराई-गुड़ाई कर खरपतवार नियंत्रित रखें।"
                ]
                prompts = [
                    f"{farm_name} के लिए प्याज खाद अनुसूची",
                    "प्याज की जोत में आज छिड़काव करें या नहीं?",
                    f"{district.capitalize()} मंडी में प्याज का भाव"
                ]
            else:
                recommendations = [
                    f"{irrigation.capitalize()} द्वारे १९:१९:१९ विद्राव्य खताची मात्रा देऊन जोमदार वाढ साधा.",
                    "जमिनीत वाफसा ठेवा, पाण्याचा ताण किंवा साचलेपण टाळा.",
                    "पिकाच्या वाढीच्या काळात तण नियंत्रण वेळेवर ठेवा."
                ]
                prompts = [
                    f"{farm_name} कांदा पिकासाठी विद्राव्य खत वेळापत्रक",
                    "कांद्यासाठी आजचा फवारणी सल्ला",
                    f"{district.capitalize()} बाजारात कांदा बाजारभाव"
                ]

    elif "wheat" in crop or "गहू" in crop or "गेहूं" in crop:
        if lang == "en":
            recommendations = [
                "Ensure critical irrigation at Crown Root Initiation (21 DAS) and Flowering stages.",
                "Top dress second dose of Urea under moist soil conditions.",
                "Scout regularly for yellow/brown rust symptoms."
            ]
            prompts = [
                f"Irrigation stages for {farm_name} wheat",
                "How to identify wheat rust disease?",
                "Wheat MSP and local APMC market price"
            ]
        elif lang == "hi":
            recommendations = [
                "मुकुट जड़ निकलने (21 दिन) और फूल आने के समय सिंचाई अत्यंत महत्वपूर्ण है।",
                "पर्याप्त नमी की स्थिति में यूरिया की दूसरी खुराक दें।",
                "पीला/भूरा रतुआ (Rust) रोग की नियमित निगरानी करें।"
            ]
            prompts = [
                f"{farm_name} में गेहूं सिंचाई समय सारणी",
                "गेहूं में रतुआ रोग की पहचान और रोकथाम",
                "गेहूं का न्यूनतम समर्थन मूल्य (MSP)"
            ]
        else:
            recommendations = [
                "मुकुट मुळे फुटण्याच्या वेळी (२१ दिवस) आणि फुलोरा अवस्थेत पाणी नियोजन करा.",
                "ओलावा असताना युरियाची दुसरी मात्रा द्या.",
                "गव्हावरील तांबेरा रोगाची नियमित पाहणी करा."
            ]
            prompts = [
                f"{farm_name} गव्हासाठी पाणी व्यवस्थापन",
                "गव्हावरील तांबेरा रोगाची लक्षणे",
                "गव्हाचा ताजा हमीभाव"
            ]

    elif "gram" in crop or "हरभरा" in crop or "चना" in crop:
        if lang == "en":
            recommendations = [
                "Avoid heavy flood irrigation during flowering to prevent flower drop.",
                "Install 5 pheromone traps per hectare for Helicoverpa pod borer monitoring.",
                "Nip apical shoot buds at 30 days to encourage extensive lateral branching."
            ]
            prompts = [
                f"Pod borer control in {farm_name} chickpea",
                "Should I irrigate gram during flowering?",
                "Gram mandi prices today"
            ]
        elif lang == "hi":
            recommendations = [
                "फूल आने के समय अधिक सिंचाई न करें, इससे फूल झड़ने लगते हैं।",
                "घाटे की इल्ली (Pod Borer) की निगरानी हेतु प्रति हेक्टेयर 5 फेरोमोन ट्रैप लगाएं।",
                "अधिक शाखाएं पाने के लिए 30 दिन पर चने के शीर्ष शाखाएं (Nipping) तोड़ें।"
            ]
            prompts = [
                f"{farm_name} में चने की इल्ली नियंत्रण",
                "क्या चने में फूल आने पर पानी देना चाहिए?",
                "चने का ताजा मंडी भाव"
            ]
        else:
            recommendations = [
                "फुलोऱ्याच्या अवस्थेत हरभऱ्याला पाण्याचा अतिरेक करू नका (फुलगळ होते).",
                "घाटे अळीच्या नियंत्रणासाठी हेक्टरी ५ कामगंध सापळे लावा.",
                "पेरणीनंतर २५-३० दिवसांनी हरभऱ्याचे शेंडे खुडा, त्यामुळे फुटवे वाढतात."
            ]
            prompts = [
                f"{farm_name} हरभरा फुलोऱ्यात पाणी द्यावे का?",
                "हरभऱ्यावरील घाटे अळीसाठी जैविक उपाय",
                "हरभऱ्याचा आजचा APMC बाजारभाव"
            ]

    else: # General / other crops
        if lang == "en":
            recommendations = [
                f"Apply balanced NPK nutrition tailored for your {acres} acre parcel.",
                f"Optimize water application using your {irrigation} system based on soil moisture.",
                "Practice regular field scouting for early pest detection and biological control."
            ]
            prompts = [
                f"Today's farming advisory for {farm_name}",
                f"Fertilizer schedule for {crop.capitalize()}",
                "Weather and spraying conditions today"
            ]
        elif lang == "hi":
            recommendations = [
                f"{acres} एकड़ खेत के लिए संतुलित NPK पोषण प्रबंधन अपनाएं।",
                f"{irrigation} प्रणाली द्वारा मिट्टी की नमी अनुसार सिंचाई का नियमन करें।",
                "कीट एवं रोगों की शीघ्र पहचान हेतु नियमित खेत का निरीक्षण करें।"
            ]
            prompts = [
                f"{farm_name} के लिए आज की कृषि सलाह",
                f"{crop} फसल का पोषण एवं जल प्रबंधन",
                "आज का मौसम और छिड़काव की स्थिति"
            ]
        else:
            recommendations = [
                f"{farm_name} मधील {acres} एकर क्षेत्रासाठी संतुलित खतांचा वापर करा.",
                f"{irrigation.capitalize()} सिंचनाद्वारे पाण्याचा कार्यक्षम वापर करा.",
                "कीड व रोगांचा प्रादुर्भाव सुरुवातीच्या टप्प्यातच ओळखून जैविक उपाय योजा."
            ]
            prompts = [
                f"{farm_name} च्या {crop} पिकासाठी आजचा सल्ला",
                f"{crop} पिकाचे खत व पाणी व्यवस्थापन",
                "आजचा कृषी हवामान व फवारणी सल्ला"
            ]

    # Calculate overall farm health score
    farm_score = int(round((soil_score * 0.45) + (85 if risk_level == "low" else 65 if risk_level == "moderate" else 45) * 0.40 + (90 if irrigation == "drip" else 75) * 0.15))
    farm_score = max(35, min(98, farm_score))

    # Condition string localized
    cond_str = current_weather.get("condition", "Clear Sky")
    if lang == "hi":
        cond_str = "साफ आसमान" if "Clear" in cond_str else "धूप और बादल"
    elif lang == "mr":
        cond_str = "निरभ्र आकाश" if "Clear" in cond_str else "अंशतः ढगाळ"

    return {
        "farm_id": profile.farm_id or "farm_default",
        "farm_name": farm_name,
        "district": district,
        "state": profile.state or "Maharashtra",
        "current_crop": crop,
        "crop_stage": stage,
        "language": lang,
        "farm_health_score": farm_score,
        "soil_health_score": soil_score,
        "crop_health_risk": risk_level,
        "weather_summary": {
            "temperature_c": temp_c,
            "wind_speed_kmh": wind_kmh,
            "humidity_pct": current_weather.get("humidity_pct", 50),
            "condition": cond_str,
            "spray_flag": spray_flag,
            "spray_reason": weather_adv.get("spray_reason", "Weather favorable for field work.")
        },
        "personalized_recommendations": recommendations[:3],
        "alerts": alerts[:3],
        "suggested_prompts": prompts[:3],
        "soil_advice": soil_guidance,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
