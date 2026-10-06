/**
 * KisanMitra — frontend/speech.js
 * Browser Web Speech API wrapper for Speech-to-Text (STT) and Text-to-Speech (TTS).
 * Conforms to PRD §9, ARCHITECTURE.md §5, and RULES.md §2.
 */

class KisanSpeech {
  constructor() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition || null;
    this.recognitionClass = SpeechRecognition;
    this.recognition = null;
    this.isListening = false;
    this.synthesis = window.speechSynthesis || null;
    this.currentUtterance = null;
    this.voices = [];

    // Locale mapping for Marathi, Hindi, English, and regional Indian languages
    this.localeMap = {
      mr: 'mr-IN',
      hi: 'hi-IN',
      en: 'en-IN',
      gu: 'gu-IN',
      pa: 'pa-IN',
      kn: 'kn-IN',
      te: 'te-IN',
      ta: 'ta-IN'
    };

    if (this.synthesis) {
      this.loadVoices();
      if (typeof this.synthesis.onvoiceschanged !== 'undefined') {
        this.synthesis.onvoiceschanged = () => this.loadVoices();
      }
    }
  }

  isSTTSupported() {
    return Boolean(this.recognitionClass);
  }

  isTTSSupported() {
    return Boolean(this.synthesis);
  }

  getLocale(langCode) {
    return this.localeMap[langCode] || langCode || 'mr-IN';
  }

  loadVoices() {
    if (!this.synthesis) return [];
    this.voices = this.synthesis.getVoices() || [];
    return this.voices;
  }

  getBestVoice(langCode) {
    if (!this.voices || this.voices.length === 0) {
      this.loadVoices();
    }
    const targetLocale = this.getLocale(langCode).toLowerCase();
    const prefix = targetLocale.split('-')[0];

    // 1. Exact match on locale (e.g. mr-IN, hi-IN)
    let matched = this.voices.find(v => v.lang && v.lang.toLowerCase() === targetLocale);
    if (matched) return matched;

    // 2. Prefix match (e.g. starts with 'mr' or 'hi')
    matched = this.voices.find(v => v.lang && v.lang.toLowerCase().startsWith(prefix));
    if (matched) return matched;

    // 3. Match voice name containing Hindi or Marathi or English India
    if (langCode === 'hi') {
      matched = this.voices.find(v => /hindi|aditi|kajal/i.test(v.name));
      if (matched) return matched;
    }
    if (langCode === 'mr') {
      matched = this.voices.find(v => /marathi/i.test(v.name));
      if (matched) return matched;
    }
    if (langCode === 'en') {
      matched = this.voices.find(v => /india|en-in/i.test(v.name) || /en-in/i.test(v.lang));
      if (matched) return matched;
    }

    // Fallback to default or first voice
    return this.voices.find(v => v.default) || this.voices[0] || null;
  }

  startListening({ lang = 'mr', onStart, onInterim, onFinal, onError, onEnd }) {
    if (!this.isSTTSupported()) {
      if (onError) onError({ error: 'not_supported', message: 'Speech recognition is not supported in this browser.' });
      return false;
    }

    this.stopListening();
    this.stopSpeaking();

    try {
      this.recognition = new this.recognitionClass();
      this.recognition.lang = this.getLocale(lang);
      this.recognition.interimResults = true;
      this.recognition.continuous = false;
      this.recognition.maxAlternatives = 1;

      let finalTranscript = '';

      this.recognition.onstart = () => {
        this.isListening = true;
        if (onStart) onStart();
      };

      this.recognition.onresult = (event) => {
        let interimTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            finalTranscript += transcript;
          } else {
            interimTranscript += transcript;
          }
        }
        if (interimTranscript && onInterim) {
          onInterim(interimTranscript);
        }
        if (finalTranscript && onFinal) {
          onFinal(finalTranscript.trim());
        }
      };

      this.recognition.onerror = (event) => {
        this.isListening = false;
        if (onError) onError(event);
      };

      this.recognition.onend = () => {
        this.isListening = false;
        if (onEnd) onEnd(finalTranscript.trim());
      };

      this.recognition.start();
      return true;
    } catch (err) {
      this.isListening = false;
      if (onError) onError(err);
      return false;
    }
  }

  stopListening() {
    if (this.recognition && this.isListening) {
      try {
        this.recognition.stop();
      } catch (e) {
        // Ignore errors if already stopped
      }
    }
    this.isListening = false;
  }

  speak({ text, lang = 'mr', rate = 0.95, pitch = 1.0, onStart, onEnd, onError }) {
    if (!this.isTTSSupported() || !text) {
      if (onError) onError(new Error('TTS not supported or empty text'));
      return false;
    }

    this.stopSpeaking();

    try {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = this.getLocale(lang);
      utterance.rate = rate; // Slightly slower for low-literacy clarity
      utterance.pitch = pitch;

      const voice = this.getBestVoice(lang);
      if (voice) {
        utterance.voice = voice;
      }

      utterance.onstart = () => {
        this.currentUtterance = utterance;
        if (onStart) onStart();
      };

      utterance.onend = () => {
        this.currentUtterance = null;
        if (onEnd) onEnd();
      };

      utterance.onerror = (event) => {
        this.currentUtterance = null;
        if (onError) onError(event);
      };

      this.currentUtterance = utterance;
      this.synthesis.speak(utterance);
      return true;
    } catch (err) {
      if (onError) onError(err);
      return false;
    }
  }

  stopSpeaking() {
    if (this.synthesis) {
      try {
        this.synthesis.cancel();
      } catch (e) {
        // Ignore
      }
    }
    this.currentUtterance = null;
  }
}

// Attach globally for browser runtime
window.KisanSpeech = KisanSpeech;
