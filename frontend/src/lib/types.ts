export interface User {
  id: number;
  email: string;
  company_name: string;
  is_active: boolean;
  created_at: string;
}

export interface Lead {
  id: number;
  user_id: number;
  name: string;
  company: string;
  phone: string;
  email?: string;
  whatsapp_number?: string;
  facebook_profile?: string;
  source: string;
  language: string;
  country?: string;
  industry?: string;
  notes?: string;
  status: LeadStatus;
  score?: number;
  analysis_result?: string;
  created_at: string;
  updated_at: string;
}

export type LeadStatus =
  | "new"
  | "analyzed"
  | "contacted"
  | "replied"
  | "converted";

export interface Campaign {
  id: number;
  user_id: number;
  name: string;
  description?: string;
  status: CampaignStatus;
  template_id?: number;
  target_score_min?: number;
  target_score_max?: number;
  target_status?: string;
  leads_count: number;
  messages_sent: number;
  replies_count: number;
  created_at: string;
  updated_at: string;
}

export type CampaignStatus = "draft" | "active" | "paused" | "completed";

export interface Message {
  id: number;
  user_id: number;
  lead_id: number;
  campaign_id?: number;
  lead_name?: string;
  lead_phone?: string;
  content: string;
  whatsapp_link?: string;
  status: MessageStatus;
  sent_at?: string;
  delivered_at?: string;
  read_at?: string;
  replied_at?: string;
  created_at: string;
}

export type MessageStatus =
  | "pending_approval"
  | "approved"
  | "sent"
  | "delivered"
  | "read"
  | "replied"
  | "failed";

export interface Template {
  id: number;
  user_id: number;
  name: string;
  language: string;
  body: string;
  variables: string[];
  created_at: string;
  updated_at: string;
}

export interface MessageStats {
  total: number;
  pending_approval: number;
  approved: number;
  sent: number;
  delivered: number;
  read: number;
  replied: number;
  failed: number;
}

export interface DashboardStats {
  total_leads: number;
  active_campaigns: number;
  messages_sent: number;
  reply_rate: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  company_name: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
}

export interface CampaignCreateRequest {
  name: string;
  description?: string;
  template_id?: number;
  target_score_min?: number;
  target_score_max?: number;
  target_status?: string;
}

export interface TemplateCreateRequest {
  name: string;
  language: string;
  body: string;
}
