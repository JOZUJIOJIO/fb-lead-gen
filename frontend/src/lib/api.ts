import axios from "axios";
import type {
  AnalyticsOverview,
  AuthResponse,
  Campaign,
  CampaignCreateRequest,
  DataSource,
  ImportResult,
  Lead,
  LoginRequest,
  Message,
  MessageStats,
  RegisterRequest,
  Template,
  TemplateCreateRequest,
  User,
} from "./types";

const api = axios.create({
  baseURL: "/api",
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

// Auth
export const authApi = {
  login: async (data: LoginRequest): Promise<AuthResponse> => {
    const res = await api.post("/auth/login", data);
    return res.data;
  },
  register: async (data: RegisterRequest): Promise<User> => {
    const res = await api.post("/auth/register", data);
    return res.data;
  },
  me: async (): Promise<User> => {
    const res = await api.get("/auth/me");
    return res.data;
  },
};

// Leads
export const leadsApi = {
  list: async (params?: {
    page?: number;
    page_size?: number;
    status?: string;
    search?: string;
    sort_by?: string;
    sort_order?: string;
  }): Promise<{ items: Lead[]; total: number; page: number; pages: number }> => {
    const res = await api.get("/leads", { params });
    return res.data;
  },
  get: async (id: number): Promise<Lead> => {
    const res = await api.get(`/leads/${id}`);
    return res.data;
  },
  create: async (data: Partial<Lead>): Promise<Lead> => {
    const res = await api.post("/leads", data);
    return res.data;
  },
  update: async (id: number, data: Partial<Lead>): Promise<Lead> => {
    const res = await api.put(`/leads/${id}`, data);
    return res.data;
  },
  delete: async (id: number): Promise<void> => {
    await api.delete(`/leads/${id}`);
  },
  import: async (file: File): Promise<{ imported: number; errors: string[] }> => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await api.post("/leads/import", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return res.data;
  },
  analyze: async (id: number): Promise<Lead> => {
    const res = await api.post(`/leads/${id}/analyze`);
    return res.data;
  },
  batchAnalyze: async (ids: number[]): Promise<{ analyzed: number }> => {
    const res = await api.post("/leads/batch-analyze", { ids });
    return res.data;
  },
  sources: async (): Promise<DataSource[]> => {
    const res = await api.get("/leads/sources");
    return res.data;
  },
  importFromSource: async (
    source: string,
    file: File,
    showName?: string
  ): Promise<ImportResult> => {
    const formData = new FormData();
    formData.append("file", file);
    if (showName) formData.append("show_name", showName);
    const res = await api.post(`/leads/import/${source}`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return res.data;
  },
};

// Campaigns
export const campaignsApi = {
  list: async (): Promise<Campaign[]> => {
    const res = await api.get("/campaigns");
    return res.data;
  },
  get: async (id: number): Promise<Campaign> => {
    const res = await api.get(`/campaigns/${id}`);
    return res.data;
  },
  create: async (data: CampaignCreateRequest): Promise<Campaign> => {
    const res = await api.post("/campaigns", data);
    return res.data;
  },
  update: async (id: number, data: Partial<CampaignCreateRequest>): Promise<Campaign> => {
    const res = await api.put(`/campaigns/${id}`, data);
    return res.data;
  },
  delete: async (id: number): Promise<void> => {
    await api.delete(`/campaigns/${id}`);
  },
  launch: async (id: number): Promise<Campaign> => {
    const res = await api.post(`/campaigns/${id}/launch`);
    return res.data;
  },
};

// Messages
export const messagesApi = {
  list: async (params?: {
    status?: string;
    campaign_id?: number;
    lead_id?: number;
  }): Promise<Message[]> => {
    const res = await api.get("/messages", { params });
    return res.data.items || res.data;
  },
  approve: async (id: number): Promise<Message> => {
    const res = await api.post(`/messages/${id}/approve`);
    return res.data;
  },
  send: async (id: number): Promise<Message> => {
    const res = await api.post(`/messages/${id}/send`);
    return res.data;
  },
  batchApprove: async (ids: number[]): Promise<{ approved: number }> => {
    const res = await api.post("/messages/batch-approve", { ids });
    return res.data;
  },
  batchSend: async (ids: number[]): Promise<{ sent: number }> => {
    const res = await api.post("/messages/batch-send", { ids });
    return res.data;
  },
  stats: async (): Promise<MessageStats> => {
    const res = await api.get("/messages/stats");
    return res.data;
  },
};

// Templates
export const templatesApi = {
  list: async (): Promise<Template[]> => {
    const res = await api.get("/templates");
    return res.data;
  },
  get: async (id: number): Promise<Template> => {
    const res = await api.get(`/templates/${id}`);
    return res.data;
  },
  create: async (data: TemplateCreateRequest): Promise<Template> => {
    const res = await api.post("/templates", data);
    return res.data;
  },
  update: async (id: number, data: Partial<TemplateCreateRequest>): Promise<Template> => {
    const res = await api.put(`/templates/${id}`, data);
    return res.data;
  },
  delete: async (id: number): Promise<void> => {
    await api.delete(`/templates/${id}`);
  },
};

// Analytics
export const analyticsApi = {
  overview: async (): Promise<AnalyticsOverview> => {
    const res = await api.get("/analytics/overview");
    return res.data;
  },
};

export default api;
