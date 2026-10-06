/**
 * KisanMitra — frontend/supabase_client.js
 * Supabase Authentication, Multi-Farm Storage, and Offline Fallback Manager.
 * Enables login, signup, session management, farm switching, and historical storage.
 */

class KisanDataManager {
  constructor() {
    this.supabase = null;
    this.currentUser = null;
    this.activeFarmId = null;
    this.supabaseConfigured = false;

    // Keys for local persistence fallback
    this.STORAGE_KEYS = {
      SESSION: 'km_auth_session',
      FARMS: 'km_user_farms',
      ACTIVE_FARM: 'km_active_farm_id',
      HISTORY: 'km_analysis_history'
    };

    this.init();
  }

  async init() {
    // Check if Supabase SDK is available and credentials provided
    const SUPABASE_URL = window.KM_SUPABASE_URL || '';
    const SUPABASE_ANON_KEY = window.KM_SUPABASE_ANON_KEY || '';

    if (window.supabase && SUPABASE_URL && SUPABASE_ANON_KEY && SUPABASE_URL.startsWith('http')) {
      try {
        this.supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
        this.supabaseConfigured = true;
        const { data } = await this.supabase.auth.getSession();
        if (data && data.session) {
          this.currentUser = data.session.user;
        }
      } catch (err) {
        console.warn('Supabase client init failed, using local offline session:', err);
      }
    }

    // If no Supabase user, check local session storage
    if (!this.currentUser) {
      const localSession = localStorage.getItem(this.STORAGE_KEYS.SESSION);
      if (localSession) {
        try {
          this.currentUser = JSON.parse(localSession);
        } catch (e) {
          this.currentUser = null;
        }
      }
    }

    // Ensure active farm is set if farms exist
    const farms = this.getFarms();
    const savedActiveId = localStorage.getItem(this.STORAGE_KEYS.ACTIVE_FARM);
    if (savedActiveId && farms.some(f => f.id === savedActiveId)) {
      this.activeFarmId = savedActiveId;
    } else if (farms.length > 0) {
      this.activeFarmId = farms[0].id;
      localStorage.setItem(this.STORAGE_KEYS.ACTIVE_FARM, this.activeFarmId);
    }
  }

  /* ---------------- Authentication API ---------------- */

  async signUp(email, password, fullName = 'शेतकरी मित्र') {
    if (this.supabaseConfigured && this.supabase) {
      try {
        const { data, error } = await this.supabase.auth.signUp({
          email,
          password,
          options: { data: { full_name: fullName } }
        });
        if (error) throw error;
        if (data && data.user) {
          this.currentUser = data.user;
          this._saveLocalSession(data.user);
          return { success: true, user: data.user };
        }
      } catch (err) {
        console.warn('Supabase signup error, falling back to local account:', err);
      }
    }

    // Offline / Local Account creation
    const newUser = {
      id: 'usr_' + Date.now(),
      email: email,
      full_name: fullName || email.split('@')[0],
      created_at: new Date().toISOString()
    };
    this.currentUser = newUser;
    this._saveLocalSession(newUser);
    return { success: true, user: newUser };
  }

  async signIn(email, password) {
    if (this.supabaseConfigured && this.supabase) {
      try {
        const { data, error } = await this.supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        if (data && data.user) {
          this.currentUser = data.user;
          this._saveLocalSession(data.user);
          await this._syncFarmsFromSupabase();
          return { success: true, user: data.user };
        }
      } catch (err) {
        console.warn('Supabase signin error, checking local account:', err);
      }
    }

    // Local / Demo Sign In
    const user = {
      id: 'usr_' + Math.abs(this._hashCode(email)),
      email: email,
      full_name: email.split('@')[0] || 'सुनीता पाटील',
      created_at: new Date().toISOString()
    };
    this.currentUser = user;
    this._saveLocalSession(user);

    // If new user has no farms, don't auto-create yet so onboarding survey shows
    return { success: true, user };
  }

  async signInDemo() {
    return this.signIn('sunita.patil@kisanmitra.in', 'demo123');
  }

  async signOut() {
    if (this.supabaseConfigured && this.supabase) {
      try {
        await this.supabase.auth.signOut();
      } catch (e) {
        console.warn('Supabase signOut error:', e);
      }
    }
    this.currentUser = null;
    this.activeFarmId = null;
    localStorage.removeItem(this.STORAGE_KEYS.SESSION);
    localStorage.removeItem(this.STORAGE_KEYS.ACTIVE_FARM);
    return { success: true };
  }

  isAuthenticated() {
    return !!this.currentUser;
  }

  getUser() {
    return this.currentUser;
  }

  _saveLocalSession(user) {
    localStorage.setItem(this.STORAGE_KEYS.SESSION, JSON.stringify(user));
  }

  _hashCode(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = ((hash << 5) - hash) + str.charCodeAt(i);
      hash |= 0;
    }
    return hash;
  }

  /* ---------------- Multi-Farm Management ---------------- */

  getFarms() {
    const raw = localStorage.getItem(this.STORAGE_KEYS.FARMS);
    let farms = [];
    if (raw) {
      try {
        farms = JSON.parse(raw);
      } catch (e) {
        farms = [];
      }
    }

    // Filter farms by current user if logged in
    if (this.currentUser && farms.length > 0) {
      const userFarms = farms.filter(f => !f.user_id || f.user_id === this.currentUser.id);
      if (userFarms.length > 0) return userFarms;
    }
    return farms;
  }

  getActiveFarm() {
    const farms = this.getFarms();
    if (!farms || farms.length === 0) return null;
    const found = farms.find(f => f.id === this.activeFarmId);
    return found || farms[0];
  }

  setActiveFarm(farmId) {
    const farms = this.getFarms();
    const match = farms.find(f => f.id === farmId);
    if (match) {
      this.activeFarmId = farmId;
      localStorage.setItem(this.STORAGE_KEYS.ACTIVE_FARM, farmId);
      return match;
    }
    return null;
  }

  async saveFarm(farmData) {
    const allFarms = this._getAllFarmsRaw();
    const isNew = !farmData.id;
    const farmId = farmData.id || 'farm_' + Date.now();
    const userId = this.currentUser ? this.currentUser.id : 'guest';

    const farmObj = {
      id: farmId,
      user_id: userId,
      name: farmData.name || `Farm ${this.getFarms().length + 1}`,
      state: farmData.state || 'Maharashtra',
      district: (farmData.district || 'nashik').toLowerCase(),
      locality: farmData.locality || '',
      acres: parseFloat(farmData.acres || 3.0),
      soil_type: farmData.soil_type || 'medium_black',
      soil_ph: farmData.soil_ph || '6.8',
      soil_quality: farmData.soil_quality || 'good',
      water_source: farmData.water_source || 'well',
      irrigation_type: farmData.irrigation_type || 'drip',
      current_crop: (farmData.current_crop || 'onion').toLowerCase(),
      crop_stage: (farmData.crop_stage || 'vegetative').toLowerCase(),
      notes: farmData.notes || '',
      updated_at: new Date().toISOString()
    };

    if (isNew) {
      farmObj.created_at = new Date().toISOString();
      allFarms.push(farmObj);
    } else {
      const idx = allFarms.findIndex(f => f.id === farmId);
      if (idx !== -1) {
        allFarms[idx] = { ...allFarms[idx], ...farmObj };
      } else {
        allFarms.push(farmObj);
      }
    }

    localStorage.setItem(this.STORAGE_KEYS.FARMS, JSON.stringify(allFarms));
    this.setActiveFarm(farmId);

    // Sync to Supabase if available
    if (this.supabaseConfigured && this.supabase && this.currentUser) {
      try {
        await this.supabase.from('farms').upsert(farmObj);
      } catch (err) {
        console.warn('Supabase farm upsert error:', err);
      }
    }

    return farmObj;
  }

  deleteFarm(farmId) {
    let allFarms = this._getAllFarmsRaw();
    allFarms = allFarms.filter(f => f.id !== farmId);
    localStorage.setItem(this.STORAGE_KEYS.FARMS, JSON.stringify(allFarms));

    const remaining = this.getFarms();
    if (remaining.length > 0) {
      this.setActiveFarm(remaining[0].id);
    } else {
      this.activeFarmId = null;
      localStorage.removeItem(this.STORAGE_KEYS.ACTIVE_FARM);
    }
  }

  _getAllFarmsRaw() {
    const raw = localStorage.getItem(this.STORAGE_KEYS.FARMS);
    if (!raw) return [];
    try {
      return JSON.parse(raw);
    } catch (e) {
      return [];
    }
  }

  async _syncFarmsFromSupabase() {
    if (!this.supabase || !this.currentUser) return;
    try {
      const { data, error } = await this.supabase
        .from('farms')
        .select('*')
        .eq('user_id', this.currentUser.id);

      if (!error && data && data.length > 0) {
        const localFarms = this._getAllFarmsRaw().filter(f => f.user_id !== this.currentUser.id);
        const combined = [...localFarms, ...data];
        localStorage.setItem(this.STORAGE_KEYS.FARMS, JSON.stringify(combined));
        this.setActiveFarm(data[0].id);
      }
    } catch (e) {
      console.warn('Sync from Supabase failed:', e);
    }
  }

  /* ---------------- History / Previous Analyses ---------------- */

  saveAnalysis(record) {
    const history = this.getHistory();
    const entry = {
      id: 'ana_' + Date.now(),
      farm_id: this.activeFarmId,
      timestamp: new Date().toISOString(),
      ...record
    };
    history.unshift(entry);
    // Keep last 30 analyses
    const trimmed = history.slice(0, 30);
    localStorage.setItem(this.STORAGE_KEYS.HISTORY, JSON.stringify(trimmed));
    return entry;
  }

  getHistory(farmId = null) {
    const raw = localStorage.getItem(this.STORAGE_KEYS.HISTORY);
    let items = [];
    if (raw) {
      try {
        items = JSON.parse(raw);
      } catch (e) {
        items = [];
      }
    }
    if (farmId) {
      return items.filter(i => i.farm_id === farmId);
    }
    return items;
  }
}

// Attach globally
window.kisanData = new KisanDataManager();
