/**
 * KisanMitra — frontend/app.js
 * Enhanced UI State Controller & Multi-Agent Bridge per PRD and User Requirements.
 * Manages Auth, Multi-Farm Lifecycle, Live Farm Intelligence, Voice AI, Plant Doctor, and Dynamic Regional Locales.
 */

class KisanApp {
  constructor() {
    this.currentLanguage = 'en';
    this.activeTab = 'voice'; // Primary Home Page is Mic Advisor
    this.speech = new KisanSpeech();
    this.dataManager = window.kisanData;
    this.i18nData = {};
    this.regionsData = { districts: [], state_languages: {} };
    this.currentCard = null;
    this.autoSendTimer = null;
    this.isListening = false;
    this.isPlayingAudio = false;
    this.selectedImageBase64 = null;
    this.currentSurveyStep = 1;
    this.authMode = 'signin'; // 'signin' or 'signup'
    this.selectedWelcomeLangCode = 'en';

    // Mock cards fallback
    this.mockFiles = {
      what_to_grow: 'mock/what_to_grow_mr.json',
      weather_today: 'mock/weather_today_mr.json',
      prices: 'mock/prices_mr.json',
      how_to_grow: 'mock/how_to_grow_mr.json'
    };

    this.init();
  }

  async init() {
    await this.loadAllI18n();
    await this.loadRegions();
    this.setupSpeechEvents();

    // Check saved language or default to English
    const savedLang = localStorage.getItem('km_user_language');
    if (savedLang && this.i18nData[savedLang]) {
      this.currentLanguage = savedLang;
      this.selectedWelcomeLangCode = savedLang;
    } else {
      this.currentLanguage = 'en';
      this.selectedWelcomeLangCode = 'en';
    }

    // Check if farms exist in dataManager
    let farms = this.dataManager.getFarms();
    if (farms.length === 0) {
      // Seed default initial farm (Sunita Patil - Nashik Onion)
      await this.dataManager.saveFarm({
        name: "Sunita Patil's Farm",
        state: 'Maharashtra',
        district: 'nashik',
        locality: 'Niphad, Gat No. 42',
        acres: 3.0,
        soil_type: 'medium_black',
        drainage: 'balanced',
        soil_ph: '6.8',
        soil_quality: 'good',
        water_source: 'well',
        irrigation_type: 'drip',
        current_crop: 'onion',
        crop_stage: 'vegetative',
        fertilizer_history: 'organic_mixed'
      });
      farms = this.dataManager.getFarms();
    }

    this.updateUserAuthUI();
    this.updateActiveFarmUI();
    this.setLanguage(this.currentLanguage);
    await this.refreshFarmIntelligence();
    this.switchTab('voice');

    // Per user requirement: Always start with Auth & Survey gateway on launch
    setTimeout(() => {
      this.openModal('auth-modal');
    }, 300);
  }

  /* ---------------- Regional & I18N Data ---------------- */

  async loadAllI18n() {
    const langs = ['en', 'hi', 'mr', 'gu', 'pa', 'kn', 'te', 'ta'];
    for (const lang of langs) {
      try {
        const res = await fetch(`i18n/${lang}.json`);
        if (res.ok) {
          this.i18nData[lang] = await res.json();
        }
      } catch (err) {
        console.warn(`Could not load i18n for ${lang}:`, err);
      }
    }
  }

  async loadRegions() {
    try {
      const res = await fetch('/api/regions');
      if (res.ok) {
        this.regionsData = await res.json();
      }
    } catch (e) {
      console.warn('Could not load /api/regions:', e);
    }
  }

  /* ---------------- Dynamic 3rd Language Selector ---------------- */

  updateDynamicLanguageButton() {
    const farm = this.dataManager.getActiveFarm() || {};
    const state = farm.state || 'Maharashtra';
    const stateLangs = this.regionsData.state_languages || {};
    const langInfo = stateLangs[state] || { code: 'mr', label: 'मराठी' };

    const dynamicBtn = document.getElementById('dynamic-lang-btn');
    if (dynamicBtn) {
      if (this.currentLanguage !== 'en' && this.currentLanguage !== 'hi') {
        const nativeLabels = {
          mr: 'मराठी', gu: 'ગુજરાતી', pa: 'ਪੰਜਾਬੀ', kn: 'ಕನ್ನಡ', te: 'తెలుగు', ta: 'தமிழ்'
        };
        dynamicBtn.setAttribute('data-lang', this.currentLanguage);
        dynamicBtn.innerText = nativeLabels[this.currentLanguage] || langInfo.label;
      } else {
        dynamicBtn.setAttribute('data-lang', langInfo.code);
        dynamicBtn.innerText = langInfo.label;
      }
    }
  }

  setLanguage(lang) {
    this.currentLanguage = lang;
    localStorage.setItem('km_user_language', lang);
    this.speech.stopSpeaking();
    this.speech.stopListening();
    this.resetMicUI();

    this.updateDynamicLanguageButton();

    document.querySelectorAll('.lang-btn').forEach(btn => {
      if (btn.getAttribute('data-lang') === lang) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    this.applyLanguage(lang);
    this.refreshFarmIntelligence();
  }

  /* ---------------- First Launch Language Modal Helpers ---------------- */

  selectWelcomeLang(el) {
    document.querySelectorAll('.lang-choice-card').forEach(c => c.classList.remove('selected'));
    if (el) {
      el.classList.add('selected');
      this.selectedWelcomeLangCode = el.getAttribute('data-code');
    }
  }

  confirmWelcomeLanguage() {
    const lang = this.selectedWelcomeLangCode || 'en';
    this.setLanguage(lang);
    this.closeModal('first-launch-lang-modal');
  }

  /* ---------------- Comprehensive DOM Internationalization ---------------- */

  _setText(id, text) {
    const el = document.getElementById(id);
    if (el && text !== undefined && text !== null) {
      el.innerText = text;
    }
  }

  _t(path, defVal = '') {
    const dict = this.i18nData[this.currentLanguage] || this.i18nData['en'] || {};
    const fallback = this.i18nData['en'] || {};

    const resolve = (obj, p) => {
      const keys = p.split('.');
      let cur = obj;
      for (const k of keys) {
        if (cur && cur[k] !== undefined) cur = cur[k];
        else return null;
      }
      return cur;
    };

    const val = resolve(dict, path);
    if (val !== null && val !== undefined) return val;
    const fbVal = resolve(fallback, path);
    return fbVal !== null && fbVal !== undefined ? fbVal : defVal;
  }

  applyLanguage(lang) {
    const t = (p, def) => this._t(p, def);

    // Header & App Brand
    this._setText('app-title', t('app_title', 'KisanMitra'));
    this._setText('app-subtitle', t('app_subtitle', 'Your Trusted AI Farming Companion'));

    // Navigation Tabs
    this._setText('nav-hub-text', t('nav.hub', 'Farm Hub'));
    this._setText('nav-voice-text', t('nav.voice', 'AI Advisor'));
    this._setText('nav-doctor-text', t('nav.doctor', 'Plant Doctor'));
    this._setText('nav-farms-text', t('nav.farms', 'My Farms'));

    // Top Profile Button
    this.updateUserAuthUI();

    // Tab 1: Farm Hub Labels
    this._setText('hub-health-badge-lbl', t('hub.health_label', 'HEALTH'));
    this._setText('hub-soil-score-lbl', t('hub.soil_score_label', 'Soil Health'));
    this._setText('hub-crop-risk-lbl', t('hub.crop_risk_label', 'Crop Risk'));
    this._setText('hub-irrigation-lbl', t('hub.irrigation_label', 'Irrigation'));
    this._setText('hub-alerts-heading', t('hub.alerts_title', '⚠️ Priority Alerts'));
    this._setText('hub-recommendations-heading', t('hub.recommendations_title', "💡 Today's Tailored Actions"));
    this._setText('hub-soil-advice-heading', t('hub.soil_advice_title', '🌱 Soil & Nutrient Guidance:'));
    this._setText('hub-profile-heading', t('hub.profile_heading', 'Farmer Soil & Field Diagnosis'));
    this._setText('hub-retake-survey-btn', t('hub.retake_survey_btn', 'Edit Soil Survey'));
    this._setText('hub-diy-ribbon-lbl', t('hub.diy_ribbon_lbl', '🏺 Soil Texture (Ribbon)'));
    this._setText('hub-diy-drainage-lbl', t('hub.diy_drainage_lbl', '💧 Infiltration / Drainage'));
    this._setText('hub-diy-water-lbl', t('hub.diy_water_lbl', '🚰 Water Source'));
    this._setText('hub-diy-manure-lbl', t('hub.diy_manure_lbl', '🌿 Fertilizer Practice'));

    // Tab 2: Voice & Assistant
    this._setText('mic-status-text', this.isListening ? t('mic_listening_label', 'Listening... Speak now!') : t('mic_idle_label', 'Speak, we are listening...'));
    this._setText('mic-blocked-alert', t('mic_blocked_warning', 'Microphone not active. Please type your query or tap an action card below.'));
    this._setText('speech-heard-label', t('mic_heard_label', 'We heard:'));
    this._setText('cancel-speech-btn', t('cancel_speech', 'Cancel'));

    const chatInput = document.getElementById('chat-input-field');
    if (chatInput) chatInput.placeholder = t('chat_placeholder', 'Ask anything about your farm, crops, or weather...');

    this._setText('chips-title', t('prompts_title', '💡 Try asking:'));
    this._setText('think-weather', t('thinking.weather', 'Checking live weather and wind speed...'));
    this._setText('think-soil', t('thinking.soil', 'Analyzing soil and crop stage profile...'));
    this._setText('think-market', t('thinking.market', 'Querying APMC mandi rates...'));

    // 2x2 Feature Grid
    this._setText('feat-grow-title', t('feature_grid.grow_title', 'What to Grow'));
    this._setText('feat-grow-sub', t('feature_grid.grow_sub', 'Rabi Crop Planning'));
    this._setText('feat-weather-title', t('feature_grid.weather_title', 'Weather Today'));
    this._setText('feat-weather-sub', t('feature_grid.weather_sub', 'Spray Advisory'));
    this._setText('feat-price-title', t('feature_grid.price_title', 'Mandi Rates'));
    this._setText('feat-price-sub', t('feature_grid.price_sub', 'Onion, Gram Prices'));
    this._setText('feat-guide-title', t('feature_grid.guide_title', 'Crop Handbook'));
    this._setText('feat-guide-sub', t('feature_grid.guide_sub', 'POP & Best Practices'));

    // Tab 3: Crop Doctor (Plant Diagnosis)
    this._setText('doctor-title', t('doctor.title', '🌿 Crop Doctor (AI Plant Diagnosis)'));
    this._setText('doctor-subtitle', t('doctor.subtitle', 'Upload a photo of your leaf or crop. AI will analyze diseases, pests, and certified treatments.'));
    this._setText('upload-title-text', t('doctor.upload_title', 'Choose Photo or Open Camera'));
    this._setText('upload-subtitle-text', t('doctor.upload_subtitle', 'Upload JPG, PNG or WebP image'));
    this._setText('remove-img-btn', t('doctor.remove_img', '✕ Remove'));
    const analyzeBtnSpan = document.querySelector('#analyze-image-btn span');
    if (analyzeBtnSpan) analyzeBtnSpan.innerText = t('doctor.analyze_btn', '🔍 Diagnose Crop Health');
    this._setText('diag-symptoms-heading', t('doctor.symptoms_title', 'Symptoms Observed:'));
    this._setText('diag-actions-heading', t('doctor.actions_title', 'Recommended Treatment & POP:'));
    this._setText('diag-call-kvk-link', t('doctor.call_kvk', '📞 Call KVK Expert'));
    this._setText('diag-disclaimer-text', t('doctor.disclaimer', 'Indicative diagnostic advisory based on visible image symptoms. Consult nearest KVK for lab confirmation.'));

    // Tab 4: My Farms & History
    this._setText('farms-tab-title', t('farms.title', '🚜 My Registered Farms'));
    const addFarmBtnSpan = document.querySelector('#btn-open-add-farm span');
    if (addFarmBtnSpan) addFarmBtnSpan.innerText = t('farms.add_btn', '➕ Add New Farm');
    this._setText('history-tab-title', t('farms.history_title', '📜 Previous Advisories & History'));

    // Location Chooser Modal
    this._setText('loc-modal-title', t('location_modal.title', '📍 Select Your Farm Location'));
    this._setText('loc-modal-sub', t('location_modal.subtitle', 'Language and weather forecast will automatically calibrate according to your state.'));
    this._setText('loc-state-lbl', t('location_modal.state_label', 'State:'));
    this._setText('loc-district-lbl', t('location_modal.district_label', 'District:'));
    this._setText('loc-save-btn', t('location_modal.save_btn', 'Confirm & Save Location'));

    // Farm Switcher Modal
    this._setText('switcher-title', t('farm_switcher.title', '🌾 Select Active Farm'));
    this._setText('switcher-sub', t('farm_switcher.subtitle', 'Tap to switch active farm or create a new parcel:'));
    this._setText('switcher-change-loc-btn', t('farm_switcher.change_loc_btn', '📍 Change Location'));
    this._setText('switcher-add-btn', t('farm_switcher.add_farm_btn', '➕ Add New Farm'));

    // Farm Survey Wizard Modal (100% translated)
    this._setText('survey-wizard-title', t('survey.title', '🌾 Farm Profile Survey'));
    this.showSurveyStep(this.currentSurveyStep);
    this._setText('survey-farm-name-lbl', t('survey.farm_name_label', 'Farm Name:'));
    const farmNameInput = document.getElementById('survey-farm-name');
    if (farmNameInput) farmNameInput.placeholder = t('survey.farm_name_placeholder', 'Farm 1');
    this._setText('survey-state-lbl', t('survey.state_label', 'State:'));
    this._setText('survey-district-lbl', t('survey.district_label', 'District:'));
    this._setText('survey-locality-lbl', t('survey.locality_label', 'Village / Locality / Survey No. (Optional):'));
    const locInput = document.getElementById('survey-locality');
    if (locInput) locInput.placeholder = t('survey.locality_placeholder', 'e.g. Niphad, Gat No. 42');
    this._setText('survey-acres-lbl', t('survey.acres_label', 'Land Parcel Size (in Acres):'));
    this._setText('survey-next-1-btn', t('survey.next_btn', 'Next Step ➔'));
    this._setText('survey-soil-lbl', t('survey.soil_label', 'Select Soil Type:'));
    this._setText('lbl-soil-medium-black', t('survey.soil_medium_black', 'Medium Black'));
    this._setText('lbl-soil-deep-black', t('survey.soil_deep_black', 'Deep Black Clay'));
    this._setText('lbl-soil-red', t('survey.soil_red', 'Red Soil'));
    this._setText('lbl-soil-alluvial', t('survey.soil_alluvial', 'Alluvial Loam'));
    this._setText('lbl-soil-sandy', t('survey.soil_sandy', 'Sandy Loam'));
    this._setText('lbl-soil-unknown', t('survey.soil_unknown', "Don't Know"));
    this._setText('survey-soil-helper', t('survey.soil_helper', '💡 If moist soil rolls easily into a ribbon, it is black/clay soil; if it crumbles, it is sandy/light soil.'));
    this._setText('survey-ph-lbl', t('survey.ph_label', 'Soil Quality & pH Status:'));
    this._setText('lbl-ph-normal', t('survey.ph_normal', 'Normal (6.5 - 7.5 pH)'));
    this._setText('lbl-ph-acidic', t('survey.ph_acidic', 'Acidic (< 6.5 pH)'));
    this._setText('lbl-ph-alkaline', t('survey.ph_alkaline', 'Alkaline (> 7.5 pH)'));
    this._setText('lbl-ph-unknown', t('survey.ph_unknown', 'Soil Not Tested Yet'));
    this._setText('survey-ph-helper', t('survey.ph_helper', "💡 Select 'Not Tested' if unsure."));
    this._setText('survey-water-lbl', t('survey.water_label', 'Primary Water Source:'));
    this._setText('lbl-water-well', t('survey.water_well', 'Open Well'));
    this._setText('lbl-water-borewell', t('survey.water_borewell', 'Borewell'));
    this._setText('lbl-water-canal', t('survey.water_canal', 'Canal / River'));
    this._setText('lbl-water-rainfed', t('survey.water_rainfed', 'Rainfed (Dryland)'));
    this._setText('survey-irrigation-lbl', t('survey.irrigation_label', 'Irrigation Method:'));
    this._setText('opt-irr-drip', t('survey.irr_drip', 'Drip Irrigation'));
    this._setText('opt-irr-sprinkler', t('survey.irr_sprinkler', 'Sprinkler'));
    this._setText('opt-irr-flood', t('survey.irr_flood', 'Flood / Furrow'));
    this._setText('opt-irr-rainfed', t('survey.irr_rainfed', 'Rainfed Only'));
    this._setText('survey-back-2-btn', t('survey.back_btn', '⬅️ Back'));
    this._setText('survey-next-2-btn', t('survey.next_btn', 'Next Step ➔'));
    this._setText('survey-crop-lbl', t('survey.crop_label', 'Current Crop Sown:'));
    this._setText('lbl-crop-onion', t('survey.crop_onion', 'Onion'));
    this._setText('lbl-crop-wheat', t('survey.crop_wheat', 'Wheat'));
    this._setText('lbl-crop-gram', t('survey.crop_gram', 'Gram / Chickpea'));
    this._setText('lbl-crop-tomato', t('survey.crop_tomato', 'Tomato'));
    this._setText('lbl-crop-cotton', t('survey.crop_cotton', 'Cotton'));
    this._setText('lbl-crop-fallow', t('survey.crop_fallow', 'Fallow / Preparing Land'));
    this._setText('survey-stage-lbl', t('survey.stage_label', 'Crop Phenological Stage:'));
    this._setText('lbl-stage-sowing', t('survey.stage_sowing', 'Sowing / Nursery'));
    this._setText('lbl-stage-vegetative', t('survey.stage_vegetative', 'Vegetative Growth'));
    this._setText('lbl-stage-flowering', t('survey.stage_flowering', 'Flowering Stage'));
    this._setText('lbl-stage-fruiting', t('survey.stage_fruiting', 'Fruiting / Bulb Sizing'));
    this._setText('lbl-stage-harvesting', t('survey.stage_harvesting', 'Maturing / Harvesting'));
    this._setText('lbl-stage-fallow', t('survey.stage_fallow', 'Field Preparation'));
    this._setText('survey-back-3-btn', t('survey.back_btn', '⬅️ Back'));
    this._setText('survey-submit-btn', t('survey.submit_btn', '✅ Complete & Save Farm Profile'));

    // Auth Modal
    this._setText('auth-modal-title', t('auth.title', '🔐 Farmer Account Sign In'));
    this._setText('auth-modal-sub', t('auth.subtitle', 'Sign in to protect and sync your farms across devices:'));
    this._setText('auth-email-lbl', t('auth.email_label', 'Email Address:'));
    this._setText('auth-password-lbl', t('auth.password_label', 'Password:'));
    this._setText('btn-auth-demo', t('auth.demo_btn', '👨‍🌾 1-Click Demo Farmer Login'));
    this._setText('btn-auth-action', this.authMode === 'signup' ? t('auth.signup_btn', 'Create Account') : t('auth.signin_btn', 'Sign In'));
    this._setText('auth-toggle-mode', this.authMode === 'signup' ? t('auth.toggle_to_signin', 'Already have an account? Sign In') : t('auth.toggle_to_signup', 'New farmer? Create a free account (Sign Up)'));

    // Result Bottom Sheet
    this._setText('steps-header', t('result.steps_title', 'Key Actionable Steps:'));
    const btnKvk = document.getElementById('btn-call-kvk');
    if (btnKvk && btnKvk.querySelector('span')) btnKvk.querySelector('span').innerText = t('result.call_kvk', '📞 Call KVK');
    const btnAsk = document.getElementById('btn-ask-another');
    if (btnAsk && btnAsk.querySelector('span')) btnAsk.querySelector('span').innerText = t('result.ask_another', '🎙️ Ask Another Question');
    const btnListen = document.getElementById('listen-again-btn');
    if (btnListen && btnListen.querySelector('span')) btnListen.querySelector('span').innerText = t('result.listen_again', '🔊 Listen Again');

    this.updateActiveFarmUI();
    if (this.activeTab === 'farms') {
      this.renderFarmsListTab();
    }
  }

  speakWelcomeGreeting() {
    const dict = this.i18nData[this.currentLanguage] || this.i18nData['en'] || {};
    if (dict && dict.welcome_greeting) {
      this.speech.speak({
        text: dict.welcome_greeting,
        lang: this.currentLanguage,
        onStart: () => this.setAudioPlaying(true),
        onEnd: () => this.setAudioPlaying(false),
        onError: () => this.setAudioPlaying(false)
      });
    }
  }

  /* ---------------- Navigation Tabs ---------------- */

  switchTab(tabKey) {
    this.activeTab = tabKey;
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-tab-btn').forEach(el => el.classList.remove('active'));

    const targetView = document.getElementById(`tab-view-${tabKey}`);
    const targetNav = document.getElementById(`tab-nav-${tabKey}`);
    if (targetView) targetView.classList.add('active');
    if (targetNav) targetNav.classList.add('active');

    if (tabKey === 'farms') {
      this.renderFarmsListTab();
    }
  }

  /* ---------------- Active Farm & Dashboard Intelligence ---------------- */

  updateActiveFarmUI() {
    const farm = this.dataManager.getActiveFarm();
    if (!farm) return;

    this.updateDynamicLanguageButton();

    const t = (p, def) => this._t(p, def);
    const cropKey = farm.current_crop || 'onion';
    const cropLabel = t(`survey.crop_${cropKey}`, cropKey.toUpperCase());
    const stageKey = farm.crop_stage || 'vegetative';
    const stageLabel = t(`survey.stage_${stageKey}`, stageKey);

    const pillLabel = document.getElementById('active-farm-label');
    if (pillLabel) {
      pillLabel.innerText = `🌾 ${farm.name} (${farm.district.toUpperCase()}, ${cropLabel}) ▾`;
    }

    // Update Hub Card Header
    const nameEl = document.getElementById('hub-farm-name');
    if (nameEl) nameEl.innerText = farm.name;

    const metaEl = document.getElementById('hub-farm-meta');
    if (metaEl) {
      const soilKey = farm.soil_type || 'medium_black';
      const soilLabel = t(`survey.soil_${soilKey}`, soilKey.replace('_', ' '));
      const acresUnit = this.currentLanguage === 'en' ? 'Acres' : this.currentLanguage === 'hi' ? 'एकड़' : 'एकर';
      metaEl.innerText = `${farm.district.toUpperCase()}, ${farm.state} • ${farm.acres} ${acresUnit} • ${soilLabel}`;
    }

    const cropMetaEl = document.getElementById('hub-crop-meta');
    if (cropMetaEl) {
      const cropPrefix = this.currentLanguage === 'en' ? 'Crop' : this.currentLanguage === 'hi' ? 'फसल' : 'पीक';
      const stagePrefix = this.currentLanguage === 'en' ? 'Stage' : this.currentLanguage === 'hi' ? 'अवस्था' : 'अवस्था';
      cropMetaEl.innerText = `${cropPrefix}: ${cropLabel} • ${stagePrefix}: ${stageLabel}`;
    }

    // Update Farmer Soil & Field Diagnosis Card Values
    const diySoilEl = document.getElementById('hub-diy-soil-val');
    if (diySoilEl) {
      const sKey = farm.soil_type || 'medium_black';
      diySoilEl.innerText = t(`survey.soil_${sKey}`, sKey.replace('_', ' '));
    }
    const diyDrainageEl = document.getElementById('hub-diy-drainage-val');
    if (diyDrainageEl) {
      const dKey = farm.drainage || 'balanced';
      diyDrainageEl.innerText = t(`survey.drainage_${dKey}`, dKey.replace('_', ' '));
    }
    const diyWaterEl = document.getElementById('hub-diy-water-val');
    if (diyWaterEl) {
      const wKey = farm.water_source || 'well';
      diyWaterEl.innerText = t(`survey.water_${wKey}`, wKey);
    }
    const diyManureEl = document.getElementById('hub-diy-manure-val');
    if (diyManureEl) {
      const fKey = farm.fertilizer_history || 'organic_mixed';
      diyManureEl.innerText = t(`survey.fertilizer_${fKey}`, fKey.replace('_', ' '));
    }
  }

  async refreshFarmIntelligence() {
    const farm = this.dataManager.getActiveFarm();
    if (!farm) return;

    try {
      const res = await fetch('/api/farm-intelligence', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          farm_id: farm.id,
          farm_name: farm.name,
          state: farm.state,
          district: farm.district,
          locality: farm.locality,
          acres: farm.acres,
          soil_type: farm.soil_type,
          soil_ph: farm.soil_ph,
          soil_quality: farm.soil_quality,
          water_source: farm.water_source,
          irrigation_type: farm.irrigation_type,
          current_crop: farm.current_crop,
          crop_stage: farm.crop_stage,
          language: this.currentLanguage
        })
      });

      if (res.ok) {
        const intel = await res.json();
        this.renderFarmIntelligence(intel);
      }
    } catch (e) {
      console.warn('Farm intelligence fetch failed:', e);
    }
  }

  renderFarmIntelligence(intel) {
    if (!intel) return;
    const t = (p, def) => this._t(p, def);

    // Scores
    const healthEl = document.getElementById('hub-health-score');
    if (healthEl) healthEl.innerText = intel.farm_health_score || '88';

    const soilEl = document.getElementById('hub-soil-score');
    if (soilEl) soilEl.innerText = `${intel.soil_health_score || 82}%`;

    const riskEl = document.getElementById('hub-risk-level');
    if (riskEl) {
      const risk = (intel.crop_health_risk || 'low').toLowerCase();
      const riskText = risk === 'high' ? t('hub.risk_high', 'High Risk') : risk === 'moderate' ? t('hub.risk_moderate', 'Moderate Risk') : t('hub.risk_low', 'Low Risk');
      riskEl.innerText = riskText;
      riskEl.style.color = risk === 'high' ? 'var(--accent-clay)' : risk === 'moderate' ? 'var(--accent-ochre)' : '#059669';
    }

    const waterStatusEl = document.getElementById('hub-water-status');
    const farm = this.dataManager.getActiveFarm() || {};
    if (waterStatusEl) {
      const irrKey = farm.irrigation_type || 'drip';
      waterStatusEl.innerText = t(`survey.irr_${irrKey}`, irrKey);
    }

    // Weather
    const w = intel.weather_summary || {};
    const tempEl = document.getElementById('hub-weather-temp');
    if (tempEl) tempEl.innerText = `${w.temperature_c || 29}°C`;

    const condEl = document.getElementById('hub-weather-cond');
    if (condEl) {
      const cond = w.condition || (this.currentLanguage === 'en' ? 'Clear Sky' : this.currentLanguage === 'hi' ? 'साफ आसमान' : 'स्वच्छ आकाश');
      const windLbl = t('hub.weather_wind', 'Wind');
      const kmhUnit = this.currentLanguage === 'en' ? 'km/h' : this.currentLanguage === 'hi' ? 'किमी/घंटा' : 'किमी/तास';
      condEl.innerText = `${cond} • ${windLbl} ${w.wind_speed_kmh || 9} ${kmhUnit}`;
    }

    const sprayBadge = document.getElementById('hub-spray-badge');
    if (sprayBadge) {
      const flag = w.spray_flag || 'green';
      sprayBadge.className = `spray-badge spray-${flag}`;
      const sprayText = flag === 'green' ? t('hub.spray_green', '✅ Safe to Spray') : flag === 'amber' ? t('hub.spray_amber', '⚠️ Spray Caution') : t('hub.spray_red', '⛔ Do Not Spray');
      sprayBadge.innerHTML = `<span>${sprayText}</span>`;
    }

    // Alerts
    const alertsContainer = document.getElementById('hub-alerts-container');
    if (alertsContainer) {
      alertsContainer.innerHTML = '';
      (intel.alerts || []).forEach(a => {
        const item = document.createElement('div');
        item.className = `alert-item alert-${a.level || 'low'}`;
        item.innerHTML = `
          <div>
            <div class="alert-title">${a.title}</div>
            <div class="alert-desc">${a.message}</div>
          </div>
        `;
        alertsContainer.appendChild(item);
      });
    }

    // Recommendations
    const recList = document.getElementById('hub-recommendations-list');
    if (recList) {
      recList.innerHTML = '';
      (intel.personalized_recommendations || []).forEach((r, idx) => {
        const item = document.createElement('div');
        item.className = 'recommendation-item';
        item.innerHTML = `
          <div class="rec-bullet">${idx + 1}</div>
          <div>${r}</div>
        `;
        recList.appendChild(item);
      });
    }

    // Soil Advice
    const soilAdviceEl = document.getElementById('hub-soil-advice-text');
    if (soilAdviceEl) {
      soilAdviceEl.innerText = intel.soil_advice || t('hub.soil_advice_title', 'Soil pH is in balanced range. Continue organic composting.');
    }

    // Dynamic Prompt Chips for Assistant Tab
    const chipsContainer = document.getElementById('chips-container');
    if (chipsContainer && intel.suggested_prompts) {
      chipsContainer.innerHTML = '';
      intel.suggested_prompts.forEach(p => {
        const chip = document.createElement('div');
        chip.className = 'prompt-chip';
        chip.innerText = p;
        chip.onclick = () => {
          this.switchTab('voice');
          this.sendQuery(p);
        };
        chipsContainer.appendChild(chip);
      });
    }
  }

  /* ---------------- Multi-Farm Switcher & Survey ---------------- */

  openFarmSwitcherModal() {
    const listEl = document.getElementById('switcher-farms-list');
    if (!listEl) return;
    listEl.innerHTML = '';

    const farms = this.dataManager.getFarms();
    const activeFarm = this.dataManager.getActiveFarm() || {};
    const t = (p, def) => this._t(p, def);
    const acresUnit = this.currentLanguage === 'en' ? 'Acres' : this.currentLanguage === 'hi' ? 'एकड़' : 'एकर';

    farms.forEach(f => {
      const card = document.createElement('div');
      card.className = `farm-manage-card ${f.id === activeFarm.id ? 'active-farm-highlight' : ''}`;
      card.onclick = () => {
        this.dataManager.setActiveFarm(f.id);
        this.updateActiveFarmUI();
        this.refreshFarmIntelligence();
        this.closeModal('farm-switcher-modal');
      };
      const cropLbl = t(`survey.crop_${f.current_crop || 'onion'}`, f.current_crop || 'Onion');
      card.innerHTML = `
        <div class="farm-card-left">
          <h4>🌾 ${f.name} ${f.id === activeFarm.id ? '✅' : ''}</h4>
          <p>${f.district.toUpperCase()}, ${f.state} • ${f.acres} ${acresUnit} • ${cropLbl}</p>
        </div>
        <div style="font-size: 13px; font-weight: 700; color: var(--accent-forest);">
          ${f.id === activeFarm.id ? t('farms.active_badge', 'Active') : t('farms.activate_btn', 'Select ➔')}
        </div>
      `;
      listEl.appendChild(card);
    });

    this.openModal('farm-switcher-modal');
  }

  renderFarmsListTab() {
    const container = document.getElementById('farms-list-container');
    if (!container) return;
    container.innerHTML = '';

    const farms = this.dataManager.getFarms();
    const activeFarm = this.dataManager.getActiveFarm() || {};
    const t = (p, def) => this._t(p, def);
    const acresUnit = this.currentLanguage === 'en' ? 'Acres' : this.currentLanguage === 'hi' ? 'एकड़' : 'एकर';

    farms.forEach(f => {
      const card = document.createElement('div');
      card.className = `farm-manage-card ${f.id === activeFarm.id ? 'active-farm-highlight' : ''}`;
      const cropLbl = t(`survey.crop_${f.current_crop || 'onion'}`, f.current_crop || 'Crop');
      const stageLbl = t(`survey.stage_${f.crop_stage || 'vegetative'}`, f.crop_stage || 'Growth');
      const soilLbl = t(`survey.soil_${f.soil_type || 'medium_black'}`, f.soil_type || 'Soil');

      card.innerHTML = `
        <div class="farm-card-left">
          <h4>🌾 ${f.name}</h4>
          <p>${f.district.toUpperCase()}, ${f.state} • ${f.acres} ${acresUnit} • ${soilLbl}</p>
          <p style="color: var(--accent-forest); font-weight: 600;">${cropLbl} (${stageLbl})</p>
        </div>
        <div>
          ${f.id === activeFarm.id 
            ? `<span style="color: var(--accent-forest); font-weight: 800; font-size: 13px;">${t('farms.active_badge', '✅ Active Farm')}</span>`
            : `<button class="btn-secondary" onclick="app.selectActiveFarm('${f.id}')" style="padding: 6px 12px; font-size: 12px;">${t('farms.activate_btn', 'Set Active')}</button>`
          }
        </div>
      `;
      container.appendChild(card);
    });

    // Render History
    const historyList = document.getElementById('farm-history-list');
    if (historyList) {
      historyList.innerHTML = '';
      const history = this.dataManager.getHistory(activeFarm.id);
      if (history.length === 0) {
        historyList.innerHTML = `<div style="font-size: 13px; color: var(--text-muted); padding: 8px;">${t('farms.no_history', 'No previous advisory recorded for this farm yet. Ask a question to get started.')}</div>`;
      } else {
        history.slice(0, 10).forEach(h => {
          const item = document.createElement('div');
          item.className = 'history-card';
          item.innerHTML = `
            <div style="font-weight: 700; color: var(--accent-forest);">${h.title || 'Advisory'}</div>
            <div>${h.summary || ''}</div>
            <div class="history-timestamp">⏱️ ${new Date(h.timestamp).toLocaleString()}</div>
          `;
          historyList.appendChild(item);
        });
      }
    }
  }

  selectActiveFarm(farmId) {
    this.dataManager.setActiveFarm(farmId);
    this.updateActiveFarmUI();
    this.refreshFarmIntelligence();
    this.renderFarmsListTab();
  }

  /* ---------------- Farm Onboarding Survey Wizard ---------------- */

  openNewFarmSurvey(forceLock = false) {
    this.currentSurveyStep = 1;
    this.showSurveyStep(1);

    const closeBtn = document.getElementById('survey-close-btn');
    if (closeBtn) {
      closeBtn.style.display = forceLock ? 'none' : 'flex';
    }

    const nextFarmNum = this.dataManager.getFarms().length + 1;
    const nameInput = document.getElementById('survey-farm-name');
    if (nameInput) nameInput.value = `Farm ${nextFarmNum}`;

    this.openModal('survey-modal');
  }

  surveyNextStep(step) {
    this.currentSurveyStep = step;
    this.showSurveyStep(step);
  }

  showSurveyStep(step) {
    for (let i = 1; i <= 3; i++) {
      const el = document.getElementById(`survey-step-${i}`);
      if (el) el.style.display = i === step ? 'block' : 'none';
    }
    const indicator = document.getElementById('survey-step-indicator');
    const t = (p, def) => this._t(p, def);
    if (indicator) {
      indicator.innerText = t(`survey.step_${step}`, step === 1 ? 'Step 1 of 3: Location & Land' : step === 2 ? 'Step 2 of 3: Soil & Water' : 'Step 3 of 3: Current Crop & Stage');
    }
  }

  selectSurveyChoice(containerId, clickedEl) {
    const parent = document.getElementById(containerId);
    if (!parent) return;
    parent.querySelectorAll('.choice-card-item').forEach(el => el.classList.remove('selected'));
    clickedEl.classList.add('selected');
  }

  getSurveyChoiceValue(containerId, defaultValue = '') {
    const parent = document.getElementById(containerId);
    if (!parent) return defaultValue;
    const selected = parent.querySelector('.choice-card-item.selected');
    return selected ? selected.getAttribute('data-value') : defaultValue;
  }

  async submitFarmSurvey() {
    const name = (document.getElementById('survey-farm-name') ? document.getElementById('survey-farm-name').value.trim() : '') || 'Farm 1';
    const state = document.getElementById('survey-state') ? document.getElementById('survey-state').value : 'Maharashtra';
    const district = document.getElementById('survey-district') ? document.getElementById('survey-district').value : 'nashik';
    const locality = document.getElementById('survey-locality') ? document.getElementById('survey-locality').value.trim() : '';
    const acres = parseFloat((document.getElementById('survey-acres') ? document.getElementById('survey-acres').value : '') || 3.0);

    const soilType = this.getSurveyChoiceValue('survey-soil-grid', 'medium_black');
    const drainage = this.getSurveyChoiceValue('survey-drainage-grid', 'balanced');
    const waterSource = this.getSurveyChoiceValue('survey-water-grid', 'well');
    const irrigation = document.getElementById('survey-irrigation') ? document.getElementById('survey-irrigation').value : 'drip';

    const crop = this.getSurveyChoiceValue('survey-crop-grid', 'onion');
    const stage = this.getSurveyChoiceValue('survey-stage-grid', 'vegetative');
    const fertilizer = document.getElementById('survey-fertilizer') ? document.getElementById('survey-fertilizer').value : 'organic_mixed';

    // Calculate DIY Soil Diagnostic Score & Agronomic Recommendations
    let soilScore = 85;
    let soilAdvice = "Balanced soil condition. Continue applying decomposed compost.";

    if (soilType === 'medium_black') {
      soilScore = drainage === 'balanced' ? 88 : drainage === 'slow_pooling' ? 78 : 82;
      soilAdvice = "Black Cotton Soil: High natural moisture retention. Ideal for Rabi Onion & Gram. Maintain 3-day drip interval.";
    } else if (soilType === 'alluvial_clay') {
      soilScore = 92;
      soilAdvice = "Fertile Alluvial Loam: Excellent balanced root aeration. High nutrient uptake for Wheat & Vegetables.";
    } else if (soilType === 'sandy_loam') {
      soilScore = 76;
      soilAdvice = "Sandy / Light Soil: Fast drainage. Add cow dung manure and mulch to prevent rapid moisture loss.";
    } else if (soilType === 'red') {
      soilScore = 82;
      soilAdvice = "Red Gravelly Soil: Good aeration, moderate fertility. Supplement with organic compost and balanced NPK.";
    }

    if (drainage === 'slow_pooling') {
      soilAdvice += " Note: Water pooling observed — use raised beds (गादी वाफा) to avoid root rot.";
    }

    await this.dataManager.saveFarm({
      name,
      state,
      district,
      locality,
      acres,
      soil_type: soilType,
      drainage: drainage,
      soil_ph: '6.8',
      soil_quality: 'good',
      soil_score: soilScore,
      soil_advice: soilAdvice,
      water_source: waterSource,
      irrigation_type: irrigation,
      current_crop: crop,
      crop_stage: stage,
      fertilizer_history: fertilizer
    });

    this.closeModal('survey-modal');
    this.updateActiveFarmUI();
    await this.refreshFarmIntelligence();
    // Per requirement: Lands farmer directly on Mic Advisor Home Page
    this.switchTab('voice');
  }

  updateSurveyDistricts(state) {
    const distSelect = document.getElementById('survey-district');
    if (!distSelect) return;
    distSelect.innerHTML = '';

    const districts = (this.regionsData.districts || []).filter(d => (d.state || '').toLowerCase() === state.toLowerCase());
    if (districts.length === 0) {
      distSelect.innerHTML = '<option value="nashik">Nashik</option><option value="pune">Pune</option>';
      return;
    }
    districts.forEach(d => {
      const opt = document.createElement('option');
      opt.value = d.id;
      const localizedName = (d.name && d.name[this.currentLanguage]) || d.name?.en || d.id;
      opt.innerText = `${localizedName} (${d.name?.en || d.id})`;
      distSelect.appendChild(opt);
    });
  }

  /* ---------------- Location Chooser Modal ---------------- */

  openLocationModal() {
    this.handleStateChange(document.getElementById('loc-state-select').value);
    this.openModal('location-modal');
  }

  handleStateChange(state) {
    const grid = document.getElementById('loc-districts-grid');
    if (!grid) return;
    grid.innerHTML = '';

    const districts = (this.regionsData.districts || []).filter(d => (d.state || '').toLowerCase() === state.toLowerCase());
    const listToRender = districts.length > 0 ? districts : [
      { id: 'nashik', name: { mr: 'नाशिक', hi: 'नासिक', en: 'Nashik' } },
      { id: 'pune', name: { mr: 'पुणे', hi: 'पुणे', en: 'Pune' } },
      { id: 'solapur', name: { mr: 'सोलापूर', hi: 'सोलापुर', en: 'Solapur' } },
      { id: 'ahmednagar', name: { mr: 'अहिल्यानगर', hi: 'अहमदनगर', en: 'Ahmednagar' } }
    ];

    listToRender.forEach((d, idx) => {
      const item = document.createElement('div');
      item.className = `choice-card-item ${idx === 0 ? 'selected' : ''}`;
      item.setAttribute('data-value', d.id);
      item.onclick = () => this.selectSurveyChoice('loc-districts-grid', item);
      const localizedDistrict = (d.name && d.name[this.currentLanguage]) || d.name?.en || d.id;
      item.innerHTML = `
        <div class="choice-card-icon">📍</div>
        <div class="choice-card-label">${localizedDistrict}</div>
      `;
      grid.appendChild(item);
    });
  }

  async applyLocationSelection() {
    const state = document.getElementById('loc-state-select').value;
    const district = this.getSurveyChoiceValue('loc-districts-grid', 'nashik');
    const farm = this.dataManager.getActiveFarm();

    if (farm) {
      farm.state = state;
      farm.district = district;
      await this.dataManager.saveFarm(farm);
      this.updateActiveFarmUI();
      await this.refreshFarmIntelligence();
    }

    this.closeModal('location-modal');
  }

  /* ---------------- Authentication Manager ---------------- */

  handleAuthButtonClick() {
    const t = (p, def) => this._t(p, def);
    if (this.dataManager.isAuthenticated()) {
      const confirmMsg = this.currentLanguage === 'en' 
        ? 'Do you want to log out?' 
        : this.currentLanguage === 'hi' 
        ? 'क्या आप लॉगआउट करना चाहते हैं?' 
        : 'लॉगआउट करायचे आहे का?';
      if (confirm(confirmMsg)) {
        this.dataManager.signOut();
        this.updateUserAuthUI();
      }
    } else {
      this.openModal('auth-modal');
    }
  }

  updateUserAuthUI() {
    const btn = document.getElementById('user-profile-btn');
    const label = document.getElementById('user-display-name');
    const user = this.dataManager.getUser();
    const t = (p, def) => this._t(p, def);

    if (user && label) {
      label.innerText = `👤 ${user.full_name || t('user_profile', 'Farmer')} 🚪`;
    } else if (label) {
      label.innerText = t('user_login', '👤 Sign In');
    }
  }

  setAuthTab(mode) {
    this.authMode = mode;
    const btnIn = document.getElementById('auth-tab-signin');
    const btnUp = document.getElementById('auth-tab-signup');
    const nameGroup = document.getElementById('auth-name-group');
    const actionBtn = document.getElementById('btn-auth-action');
    const t = (p, def) => this._t(p, def);

    if (mode === 'signup') {
      if (btnUp) btnUp.classList.add('active');
      if (btnIn) btnIn.classList.remove('active');
      if (nameGroup) nameGroup.style.display = 'block';
      if (actionBtn) actionBtn.innerText = t('auth.signup_btn', 'Create Account & Start Survey ➔');
    } else {
      if (btnIn) btnIn.classList.add('active');
      if (btnUp) btnUp.classList.remove('active');
      if (nameGroup) nameGroup.style.display = 'none';
      if (actionBtn) actionBtn.innerText = t('auth.signin_btn', 'Continue with Supabase Auth ➔');
    }
  }

  toggleAuthMode(e) {
    if (e) e.preventDefault();
    this.setAuthTab(this.authMode === 'signin' ? 'signup' : 'signin');
  }

  async handleAuthSubmit() {
    const email = document.getElementById('auth-email').value.trim();
    const password = document.getElementById('auth-password').value;
    const fullName = document.getElementById('auth-full-name') ? document.getElementById('auth-full-name').value.trim() : '';
    if (!email || !password) return;

    if (this.authMode === 'signup') {
      await this.dataManager.signUp(email, password, fullName || 'Farmer');
    } else {
      await this.dataManager.signIn(email, password);
    }

    this.closeModal('auth-modal');
    this.updateUserAuthUI();
    this.updateActiveFarmUI();
    await this.refreshFarmIntelligence();

    // After auth: Open comprehensive soil & land survey
    this.openNewFarmSurvey(false);
  }

  async quickDemoLogin() {
    await this.dataManager.signInDemo();
    this.closeModal('auth-modal');
    this.updateUserAuthUI();
    this.updateActiveFarmUI();
    await this.refreshFarmIntelligence();

    // After demo bypass: Launch survey for farmer
    this.openNewFarmSurvey(false);
  }

  /* ---------------- Plant Doctor (Crop Image Diagnosis) ---------------- */

  handleImageSelected(e) {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      this.selectedImageBase64 = event.target.result;
      const previewTag = document.getElementById('preview-img-tag');
      const previewBox = document.getElementById('image-preview-box');
      const uploadZone = document.getElementById('upload-zone-card');
      const analyzeBtn = document.getElementById('analyze-image-btn');

      if (previewTag && previewBox) {
        previewTag.src = this.selectedImageBase64;
        previewBox.style.display = 'block';
        if (uploadZone) uploadZone.style.display = 'none';
        if (analyzeBtn) analyzeBtn.style.display = 'flex';
      }
    };
    reader.readAsDataURL(file);
  }

  clearSelectedImage(e) {
    if (e) e.stopPropagation();
    this.selectedImageBase64 = null;
    document.getElementById('crop-image-input').value = '';
    document.getElementById('image-preview-box').style.display = 'none';
    document.getElementById('upload-zone-card').style.display = 'block';
    document.getElementById('analyze-image-btn').style.display = 'none';
    document.getElementById('diagnosis-result-card').style.display = 'none';
  }

  async runCropImageDiagnosis() {
    if (!this.selectedImageBase64) return;
    const farm = this.dataManager.getActiveFarm() || {};
    const analyzeBtn = document.getElementById('analyze-image-btn');
    const t = (p, def) => this._t(p, def);

    try {
      if (analyzeBtn) {
        analyzeBtn.innerHTML = `<span>${t('doctor.analyzing_btn', '⏳ AI Diagnosing Plant Leaf...')}</span>`;
        analyzeBtn.disabled = true;
      }

      // Extract raw base64 data
      const b64Data = this.selectedImageBase64.includes(',') 
        ? this.selectedImageBase64.split(',')[1] 
        : this.selectedImageBase64;

      const res = await fetch('/api/crop-image-analysis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image: b64Data,
          mime_type: 'image/jpeg',
          farm_context: {
            current_crop: farm.current_crop || 'onion',
            crop_stage: farm.crop_stage || 'vegetative',
            district: farm.district || 'nashik',
            farm_name: farm.name
          }
        })
      });

      if (res.ok) {
        const diag = await res.json();
        this.renderDiagnosisCard(diag);
        // Save to history
        this.dataManager.saveAnalysis({
          title: `Crop Diagnosis: ${diag.condition || 'Health Check'}`,
          summary: `Risk: ${diag.risk_level} • Confidence: ${diag.confidence_pct}%`
        });
      }
    } catch (err) {
      console.warn('Crop image analysis failed:', err);
    } finally {
      if (analyzeBtn) {
        analyzeBtn.innerHTML = `<span>${t('doctor.analyze_btn', '🔍 Diagnose Crop Health')}</span>`;
        analyzeBtn.disabled = false;
      }
    }
  }

  renderDiagnosisCard(diag) {
    const card = document.getElementById('diagnosis-result-card');
    if (!card) return;
    const t = (p, def) => this._t(p, def);

    document.getElementById('diag-crop-name').innerText = diag.crop_name || 'Crop';
    document.getElementById('diag-condition-text').innerText = diag.condition || 'Diagnosis';

    const riskBadge = document.getElementById('diag-risk-badge');
    const risk = (diag.risk_level || 'low').toLowerCase();
    riskBadge.innerText = risk === 'high' ? t('hub.risk_high', 'High Risk') : risk === 'moderate' ? t('hub.risk_moderate', 'Moderate Risk') : t('hub.risk_low', 'Low Risk');
    riskBadge.style.background = risk === 'high' ? '#FEE2E2' : risk === 'moderate' ? '#FEF3C7' : '#DCFCE7';
    riskBadge.style.color = risk === 'high' ? '#991B1B' : risk === 'moderate' ? '#92400E' : '#14532D';

    // Symptoms
    const symList = document.getElementById('diag-symptoms-list');
    symList.innerHTML = '';
    (diag.symptoms || []).forEach(s => {
      const li = document.createElement('li');
      li.innerText = s;
      symList.appendChild(li);
    });

    // Actions
    const actList = document.getElementById('diag-actions-list');
    actList.innerHTML = '';
    (diag.recommended_actions || []).forEach(a => {
      const p = document.createElement('p');
      p.style.marginBottom = '6px';
      p.innerText = a;
      actList.appendChild(p);
    });

    document.getElementById('diag-confidence-text').innerText = `${diag.confidence_pct || 85}%`;
    document.getElementById('diag-disclaimer-text').innerText = diag.disclaimer || t('doctor.disclaimer', 'Indicative diagnostic advisory based on visible image symptoms.');

    card.style.display = 'block';
    card.scrollIntoView({ behavior: 'smooth' });
  }

  /* ---------------- Voice Interaction ---------------- */

  setupSpeechEvents() {
    if (!this.speech.isSTTSupported()) {
      const alertEl = document.getElementById('mic-blocked-alert');
      if (alertEl) alertEl.style.display = 'block';
    }
  }

  handleMicToggle() {
    if (this.isListening) {
      this.stopListening();
    } else {
      this.startListening();
    }
  }

  startListening() {
    this.speech.stopSpeaking();
    this.clearAutoSend();

    const started = this.speech.startListening({
      lang: this.currentLanguage,
      onStart: () => {
        this.isListening = true;
        this.setMicListeningUI(true);
      },
      onInterim: (text) => {
        this.showSpeechPreview(text, false);
      },
      onFinal: (text) => {
        this.showSpeechPreview(text, true);
        this.startAutoSendCountdown(text);
      },
      onError: (err) => {
        this.isListening = false;
        this.setMicListeningUI(false);
        const alertEl = document.getElementById('mic-blocked-alert');
        if (alertEl) {
          alertEl.style.display = 'block';
          setTimeout(() => { alertEl.style.display = 'none'; }, 5000);
        }
      },
      onEnd: (final) => {
        this.isListening = false;
        this.setMicListeningUI(false);
        if (final && !this.autoSendTimer) {
          this.startAutoSendCountdown(final);
        }
      }
    });

    if (!started) {
      const alertEl = document.getElementById('mic-blocked-alert');
      if (alertEl) alertEl.style.display = 'block';
    }
  }

  stopListening() {
    this.speech.stopListening();
    this.isListening = false;
    this.setMicListeningUI(false);
  }

  setMicListeningUI(isListening) {
    const boundary = document.getElementById('mic-boundary');
    const micBtn = document.getElementById('hero-mic-btn');
    const statusText = document.getElementById('mic-status-text');
    const t = (p, def) => this._t(p, def);

    if (isListening) {
      if (boundary) boundary.classList.add('is-listening');
      if (micBtn) micBtn.classList.remove('idle');
      if (statusText) statusText.innerText = t('mic_listening_label', 'Listening... Speak now!');
    } else {
      if (boundary) boundary.classList.remove('is-listening');
      if (micBtn) micBtn.classList.add('idle');
      if (statusText) statusText.innerText = t('mic_idle_label', 'Speak, we are listening...');
    }
  }

  resetMicUI() {
    this.setMicListeningUI(false);
    this.clearAutoSend();
    const preview = document.getElementById('speech-preview-card');
    if (preview) preview.style.display = 'none';
  }

  showSpeechPreview(text, isFinal) {
    const preview = document.getElementById('speech-preview-card');
    const transcriptEl = document.getElementById('live-transcript-text');
    if (preview && transcriptEl) {
      preview.style.display = 'block';
      transcriptEl.innerText = text;
    }
  }

  startAutoSendCountdown(text) {
    this.clearAutoSend();
    const progressBar = document.getElementById('auto-send-progress');
    if (progressBar) {
      progressBar.style.width = '0%';
      requestAnimationFrame(() => { progressBar.style.width = '100%'; });
    }
    this.autoSendTimer = setTimeout(() => {
      this.clearAutoSend();
      this.sendQuery(text);
    }, 1500);
  }

  cancelSpeechInput() {
    this.clearAutoSend();
    this.stopListening();
    const preview = document.getElementById('speech-preview-card');
    if (preview) preview.style.display = 'none';
  }

  clearAutoSend() {
    if (this.autoSendTimer) {
      clearTimeout(this.autoSendTimer);
      this.autoSendTimer = null;
    }
    const progressBar = document.getElementById('auto-send-progress');
    if (progressBar) progressBar.style.width = '0%';
  }

  /* ---------------- Chat Dispatch & Results ---------------- */

  handleChatSubmit() {
    const input = document.getElementById('chat-input-field');
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    this.sendQuery(text);
  }

  async triggerFlow(intentKey) {
    this.showThinkingState(true);
    const farm = this.dataManager.getActiveFarm() || {};

    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          intent: intentKey,
          language: this.currentLanguage,
          district: farm.district || 'nashik',
          acres: farm.acres || 3.0,
          water_source: farm.water_source || 'well',
          soil_type: farm.soil_type || 'medium_black',
          soil_ph: farm.soil_ph || '6.8',
          irrigation_type: farm.irrigation_type || 'drip',
          current_crop: farm.current_crop,
          crop_stage: farm.crop_stage,
          farm_name: farm.name
        })
      });

      if (res.ok) {
        const card = await res.json();
        this.renderResultCard(card);
      } else {
        const mockCard = await this.loadMockCard(intentKey);
        this.renderResultCard(mockCard);
      }
    } catch (e) {
      console.warn('API error, falling back to mock card:', e);
      const mockCard = await this.loadMockCard(intentKey);
      this.renderResultCard(mockCard);
    } finally {
      this.showThinkingState(false);
    }
  }

  async sendQuery(queryText) {
    this.resetMicUI();
    this.showThinkingState(true);
    const farm = this.dataManager.getActiveFarm() || {};

    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: queryText,
          language: this.currentLanguage,
          district: farm.district || 'nashik',
          acres: farm.acres || 3.0,
          water_source: farm.water_source || 'well',
          soil_type: farm.soil_type || 'medium_black',
          soil_ph: farm.soil_ph || '6.8',
          irrigation_type: farm.irrigation_type || 'drip',
          current_crop: farm.current_crop,
          crop_stage: farm.crop_stage,
          farm_name: farm.name
        })
      });

      if (res.ok) {
        const card = await res.json();
        this.renderResultCard(card);
        // Save to farm history
        this.dataManager.saveAnalysis({
          title: card.title || 'Advisory',
          summary: card.summary_lines ? card.summary_lines[0] : queryText
        });
      } else {
        const mockCard = await this.loadMockCard('what_to_grow');
        this.renderResultCard(mockCard);
      }
    } catch (err) {
      console.warn('Chat request failed, loading mock response:', err);
      const mockCard = await this.loadMockCard('what_to_grow');
      this.renderResultCard(mockCard);
    } finally {
      this.showThinkingState(false);
    }
  }

  async loadMockCard(flowName) {
    const filename = `mock/${flowName}_mr.json`;
    try {
      const res = await fetch(filename);
      if (res.ok) {
        const data = await res.json();
        data.language = this.currentLanguage;
        return data;
      }
    } catch (e) {
      console.warn(`Could not load ${filename}:`, e);
    }
    return null;
  }

  showThinkingState(show) {
    const banner = document.getElementById('thinking-banner');
    if (banner) banner.style.display = show ? 'block' : 'none';
  }

  renderResultCard(card) {
    if (!card) return;
    this.currentCard = card;

    document.getElementById('card-title').innerText = card.title || 'Agricultural Advisory';

    // Metrics Row
    const metricsRow = document.getElementById('card-metrics-row');
    metricsRow.innerHTML = '';
    const metrics = card.metrics || [
      { label: 'Duration', value: '110 Days' },
      { label: 'Estimated Yield', value: '₹1,40,000' },
      { label: 'Market Trend', value: '↗ Stable' }
    ];
    metrics.slice(0, 3).forEach(m => {
      const badge = document.createElement('div');
      badge.className = 'metric-badge';
      badge.innerHTML = `
        <div class="metric-label">${m.label}</div>
        <div class="metric-value">${m.value}</div>
      `;
      metricsRow.appendChild(badge);
    });

    // Summary Lines
    const summaryBox = document.getElementById('card-summary-lines');
    summaryBox.innerHTML = '';
    (card.summary_lines || []).slice(0, 3).forEach(line => {
      const p = document.createElement('div');
      p.className = 'summary-line';
      p.innerText = line;
      summaryBox.appendChild(p);
    });

    // Steps
    const stepsList = document.getElementById('card-steps-list');
    stepsList.innerHTML = '';
    (card.steps || []).slice(0, 3).forEach((stepText, idx) => {
      const item = document.createElement('div');
      item.className = 'step-item';
      item.innerHTML = `
        <div class="step-num">${idx + 1}</div>
        <div>${stepText.replace(/^[0-9]+[.\-]\s*/, '')}</div>
      `;
      stepsList.appendChild(item);
    });

    // Honesty Tag
    const honestyTag = document.getElementById('card-honesty-tag');
    const sourcesStr = (card.sources || []).join(', ');
    const labelsStr = (card.labels || []).join(' | ');
    honestyTag.innerText = `Source: ${sourcesStr || 'Agricultural Extension / KVK'} | ${labelsStr || 'Indicative Package of Practices'}`;

    // Open Bottom-Sheet
    const overlay = document.getElementById('result-overlay');
    if (overlay) overlay.classList.add('active');

    // Auto Read-Aloud
    if (card.speak_text) {
      setTimeout(() => {
        this.speech.speak({
          text: card.speak_text,
          lang: card.language || this.currentLanguage,
          onStart: () => this.setAudioPlaying(true),
          onEnd: () => this.setAudioPlaying(false),
          onError: () => this.setAudioPlaying(false)
        });
      }, 350);
    }
  }

  replayAudio() {
    if (this.isPlayingAudio) {
      this.speech.stopSpeaking();
      this.setAudioPlaying(false);
      return;
    }
    if (this.currentCard && this.currentCard.speak_text) {
      this.speech.speak({
        text: this.currentCard.speak_text,
        lang: this.currentCard.language || this.currentLanguage,
        onStart: () => this.setAudioPlaying(true),
        onEnd: () => this.setAudioPlaying(false),
        onError: () => this.setAudioPlaying(false)
      });
    }
  }

  setAudioPlaying(isPlaying) {
    this.isPlayingAudio = isPlaying;
    const waveAnim = document.getElementById('audio-wave-anim');
    const btnSpan = document.getElementById('listen-again-btn').querySelector('span');
    const t = (p, def) => this._t(p, def);

    if (isPlaying) {
      if (waveAnim) waveAnim.classList.add('is-playing');
      if (btnSpan) btnSpan.innerText = t('result.stop_audio', '⏹️ Stop Audio');
    } else {
      if (waveAnim) waveAnim.classList.remove('is-playing');
      if (btnSpan) btnSpan.innerText = t('result.listen_again', '🔊 Listen Again');
    }
  }

  closeResultAndAskAgain() {
    this.speech.stopSpeaking();
    this.setAudioPlaying(false);
    const overlay = document.getElementById('result-overlay');
    if (overlay) overlay.classList.remove('active');
    setTimeout(() => { this.startListening(); }, 200);
  }

  handleOverlayClick(e) {
    if (e.target.id === 'result-overlay') {
      this.speech.stopSpeaking();
      this.setAudioPlaying(false);
      document.getElementById('result-overlay').classList.remove('active');
    }
  }

  /* ---------------- Generic Modal Helpers ---------------- */

  openModal(modalId) {
    const el = document.getElementById(modalId);
    if (el) el.classList.add('active');
  }

  closeModal(modalId) {
    const el = document.getElementById(modalId);
    if (el) el.classList.remove('active');
  }

  handleModalBackdropClick(e, modalId) {
    if (e.target.id === modalId) {
      this.closeModal(modalId);
    }
  }
}

// Global instantiation
window.addEventListener('DOMContentLoaded', () => {
  window.app = new KisanApp();
});
