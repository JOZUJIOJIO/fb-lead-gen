import axios from 'axios';

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for auth token
api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (typeof window !== 'undefined') {
        localStorage.removeItem('auth_token');
      }
    }
    return Promise.reject(error);
  }
);

// Auth APIs
export const authApi = {
  login: (email: string, password: string) =>
    api.post('/api/auth/login', { email, password }),
  me: () => api.get('/api/auth/me'),
};

// Campaign APIs
export const campaignApi = {
  list: () => api.get('/api/campaigns'),
  get: (id: string) => api.get(`/api/campaigns/${id}`),
  create: (data: Record<string, unknown>) => api.post('/api/campaigns', data),
  delete: (id: string) => api.delete(`/api/campaigns/${id}`),
  start: (id: string) => api.post(`/api/campaigns/${id}/start`),
  pause: (id: string) => api.post(`/api/campaigns/${id}/pause`),
  stop: (id: string) => api.post(`/api/campaigns/${id}/stop`),
  stats: () => api.get('/api/campaigns/stats/overview'),
  pending: (id: string) => api.get(`/api/campaigns/${id}/pending`),
  review: (id: string, lead_id: number, action: string) =>
    api.post(`/api/campaigns/${id}/review`, { lead_id, action }),
};

// Lead APIs
export const leadApi = {
  list: (params?: Record<string, string>) => api.get('/api/leads', { params }),
  get: (id: string) => api.get(`/api/leads/${id}`),
};

// Persona APIs
export const personaApi = {
  list: () => api.get('/api/personas'),
  get: (id: string) => api.get(`/api/personas/${id}`),
  create: (data: Record<string, unknown>) => api.post('/api/personas', data),
  update: (id: string, data: Record<string, unknown>) => api.put(`/api/personas/${id}`, data),
  delete: (id: string) => api.delete(`/api/personas/${id}`),
};

// Settings APIs
export const settingsApi = {
  get: () => api.get('/api/settings'),
  update: (data: Record<string, unknown>) => api.patch('/api/settings', data),
};

export default api;
