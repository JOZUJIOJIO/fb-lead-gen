/**
 * localStorage-based persistence for critical data (personas, campaigns).
 * Acts as the primary store — sidecar is secondary/sync target.
 * Guarantees data survives refresh, restart, and sidecar outages.
 */

const PERSONAS_KEY = 'leadflow_personas';
const CAMPAIGNS_KEY = 'leadflow_campaigns';

/* ------------------------------------------------------------------ */
/* Generic helpers                                                     */
/* ------------------------------------------------------------------ */

function read<T>(key: string): T[] {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function write<T>(key: string, data: T[]): void {
  localStorage.setItem(key, JSON.stringify(data));
}

/* ------------------------------------------------------------------ */
/* Persona store                                                       */
/* ------------------------------------------------------------------ */

export interface LocalPersona {
  id: number;
  name: string;
  company_name: string | null;
  company_description: string | null;
  products: string | null;
  salesperson_name: string | null;
  salesperson_title: string | null;
  tone: string | null;
  greeting_rules: string | null;
  conversation_rules: string | null;
  system_prompt: string | null;
  created_at: string;
  updated_at: string;
}

let _nextPersonaId = Date.now();
function nextPersonaId(): number {
  return ++_nextPersonaId;
}

export const personaStore = {
  list(): LocalPersona[] {
    return read<LocalPersona>(PERSONAS_KEY);
  },

  get(id: number): LocalPersona | undefined {
    return this.list().find(p => p.id === id);
  },

  create(data: Omit<LocalPersona, 'id' | 'created_at' | 'updated_at'>): LocalPersona {
    const now = new Date().toISOString();
    const persona: LocalPersona = {
      ...data,
      id: nextPersonaId(),
      created_at: now,
      updated_at: now,
    };
    const list = this.list();
    list.push(persona);
    write(PERSONAS_KEY, list);
    return persona;
  },

  update(id: number, data: Partial<LocalPersona>): LocalPersona | null {
    const list = this.list();
    const idx = list.findIndex(p => p.id === id);
    if (idx === -1) return null;
    list[idx] = { ...list[idx], ...data, updated_at: new Date().toISOString() };
    write(PERSONAS_KEY, list);
    return list[idx];
  },

  delete(id: number): boolean {
    const list = this.list();
    const filtered = list.filter(p => p.id !== id);
    if (filtered.length === list.length) return false;
    write(PERSONAS_KEY, filtered);
    return true;
  },

  /** Merge sidecar data into local store (dedup by name+company_name) */
  mergeFromSidecar(sidecarList: LocalPersona[]): void {
    const local = this.list();
    const localKeys = new Set(local.map(p => `${p.name}|${p.company_name}`));
    let changed = false;
    for (const sp of sidecarList) {
      const key = `${sp.name}|${sp.company_name}`;
      if (!localKeys.has(key)) {
        local.push(sp);
        localKeys.add(key);
        changed = true;
      }
    }
    if (changed) write(PERSONAS_KEY, local);
  },
};

/* ------------------------------------------------------------------ */
/* Campaign store                                                      */
/* ------------------------------------------------------------------ */

export interface LocalCampaign {
  id: number;
  name: string;
  platform: string;
  search_keywords: string | null;
  search_region: string | null;
  search_industry: string | null;
  persona_id: number | null;
  send_limit: number;
  max_per_hour: number;
  status: string;
  progress_current: number;
  progress_total: number;
  created_at: string;
  updated_at: string;
}

let _nextCampaignId = Date.now();
function nextCampaignId(): number {
  return ++_nextCampaignId;
}

export const campaignStore = {
  list(): LocalCampaign[] {
    return read<LocalCampaign>(CAMPAIGNS_KEY);
  },

  get(id: number): LocalCampaign | undefined {
    return this.list().find(c => c.id === id);
  },

  create(data: Omit<LocalCampaign, 'id' | 'created_at' | 'updated_at' | 'status' | 'progress_current' | 'progress_total'>): LocalCampaign {
    const now = new Date().toISOString();
    const campaign: LocalCampaign = {
      ...data,
      id: nextCampaignId(),
      status: 'draft',
      progress_current: 0,
      progress_total: 0,
      created_at: now,
      updated_at: now,
    };
    const list = this.list();
    list.push(campaign);
    write(CAMPAIGNS_KEY, list);
    return campaign;
  },

  update(id: number, data: Partial<LocalCampaign>): LocalCampaign | null {
    const list = this.list();
    const idx = list.findIndex(c => c.id === id);
    if (idx === -1) return null;
    list[idx] = { ...list[idx], ...data, updated_at: new Date().toISOString() };
    write(CAMPAIGNS_KEY, list);
    return list[idx];
  },

  delete(id: number): boolean {
    const list = this.list();
    const filtered = list.filter(c => c.id !== id);
    if (filtered.length === list.length) return false;
    write(CAMPAIGNS_KEY, filtered);
    return true;
  },

  /** Sync sidecar state back to local (update status/progress for running campaigns) */
  syncFromSidecar(sidecarList: LocalCampaign[]): void {
    const local = this.list();
    const sidecarMap = new Map(sidecarList.map(c => [c.id, c]));
    let changed = false;
    for (let i = 0; i < local.length; i++) {
      const sc = sidecarMap.get(local[i].id);
      if (sc && (sc.status !== local[i].status || sc.progress_current !== local[i].progress_current)) {
        local[i] = { ...local[i], status: sc.status, progress_current: sc.progress_current, progress_total: sc.progress_total };
        changed = true;
      }
    }
    if (changed) write(CAMPAIGNS_KEY, local);
  },
};
