/**
 * localStorage persistence for critical data.
 * Primary store — backend API is secondary/sync target.
 * Guarantees data survives refresh, restart, and backend outages.
 */

const PERSONAS_KEY = 'leadflow_personas';

/* ------------------------------------------------------------------ */
/* Persona store                                                       */
/* ------------------------------------------------------------------ */

export interface LocalPersona {
  id: number;
  name: string;
  company_name: string | null;
  company_description: string | null;
  products: string[] | null;
  salesperson_name: string | null;
  salesperson_title: string | null;
  tone: string | null;
  greeting_rules: { text?: string } | null;
  conversation_rules: { text?: string } | null;
  system_prompt: string | null;
  output_language: string;
  whatsapp_id: string | null;
  telegram_id: string | null;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

let _nextId = Date.now();
function nextId(): number {
  return ++_nextId;
}

function readList(): LocalPersona[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(PERSONAS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeList(data: LocalPersona[]): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(PERSONAS_KEY, JSON.stringify(data));
}

export const personaStore = {
  list(): LocalPersona[] {
    return readList();
  },

  get(id: number): LocalPersona | undefined {
    return readList().find(p => p.id === id);
  },

  create(data: Omit<LocalPersona, 'id' | 'created_at' | 'updated_at'>): LocalPersona {
    const now = new Date().toISOString();
    const persona: LocalPersona = {
      ...data,
      id: nextId(),
      created_at: now,
      updated_at: now,
    };
    const list = readList();
    list.push(persona);
    writeList(list);
    return persona;
  },

  update(id: number, data: Partial<LocalPersona>): LocalPersona | null {
    const list = readList();
    const idx = list.findIndex(p => p.id === id);
    if (idx === -1) return null;
    list[idx] = { ...list[idx], ...data, updated_at: new Date().toISOString() };
    writeList(list);
    return list[idx];
  },

  delete(id: number): boolean {
    const list = readList();
    const filtered = list.filter(p => p.id !== id);
    if (filtered.length === list.length) return false;
    writeList(filtered);
    return true;
  },

  /** Full replace — use when backend is the source of truth */
  replaceFromBackend(backendList: LocalPersona[]): void {
    if (backendList.length > 0) {
      writeList(backendList);
    }
  },

  /** Upsert a single backend persona into local store (by ID) */
  upsertFromBackend(persona: LocalPersona): void {
    const list = readList();
    const idx = list.findIndex(p => p.id === persona.id);
    if (idx >= 0) {
      list[idx] = persona;
    } else {
      list.push(persona);
    }
    writeList(list);
  },

  /** Merge backend data into local (add missing by ID and name, update existing by ID) */
  mergeFromBackend(backendList: LocalPersona[]): void {
    const local = readList();
    const localIds = new Set(local.map(p => p.id));
    const localKeys = new Set(local.map(p => `${p.name}|${p.company_name}`));
    let changed = false;
    for (const bp of backendList) {
      const existIdx = local.findIndex(p => p.id === bp.id);
      if (existIdx >= 0) {
        // Update existing
        local[existIdx] = bp;
        changed = true;
      } else if (!localKeys.has(`${bp.name}|${bp.company_name}`)) {
        local.push(bp);
        localKeys.add(`${bp.name}|${bp.company_name}`);
        changed = true;
      }
    }
    if (changed) writeList(local);
  },
};
