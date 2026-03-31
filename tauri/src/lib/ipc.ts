import { invoke } from '@tauri-apps/api/core';

export async function callSidecar<T = unknown>(
  method: string,
  params: Record<string, unknown> = {},
): Promise<T> {
  const result = await invoke('call_sidecar', { method, params });
  return result as T;
}

// Typed API helpers
export const campaignApi = {
  list: (status?: string) =>
    callSidecar('list_campaigns', status ? { status } : {}),
  get: (id: number) => callSidecar('get_campaign', { campaign_id: id }),
  create: (data: Record<string, unknown>) =>
    callSidecar('create_campaign', data),
  update: (id: number, data: Record<string, unknown>) =>
    callSidecar('update_campaign', { campaign_id: id, ...data }),
  delete: (id: number) =>
    callSidecar('delete_campaign', { campaign_id: id }),
  start: (id: number) => callSidecar('start_campaign', { campaign_id: id }),
  pause: (id: number) => callSidecar('pause_campaign', { campaign_id: id }),
  stop: (id: number) => callSidecar('stop_campaign', { campaign_id: id }),
};

export const leadApi = {
  list: (params?: Record<string, unknown>) =>
    callSidecar('list_leads', params ?? {}),
  get: (id: number) => callSidecar('get_lead', { lead_id: id }),
  getConversation: (id: number) =>
    callSidecar('get_conversation', { lead_id: id }),
};

export const personaApi = {
  list: () => callSidecar('list_personas'),
  get: (id: number) => callSidecar('get_persona', { persona_id: id }),
  create: (data: Record<string, unknown>) =>
    callSidecar('create_persona', data),
  update: (id: number, data: Record<string, unknown>) =>
    callSidecar('update_persona', { persona_id: id, ...data }),
  delete: (id: number) =>
    callSidecar('delete_persona', { persona_id: id }),
};

export const settingsApi = {
  get: (key: string) => callSidecar('get_setting', { key }),
  set: (key: string, value: string) =>
    callSidecar('set_setting', { key, value }),
};

export const systemApi = {
  status: () => callSidecar('get_status'),
  ping: () => callSidecar('ping'),
};
