"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";

interface Persona {
  company: {
    name: string; name_en: string; description: string;
    products: string; advantages: string[]; website: string;
  };
  salesperson: {
    name: string; title: string; personality: string; whatsapp: string;
  };
  conversation_style: {
    tone: string; max_message_length: number; emoji_usage: string;
    opening_rules: string[]; conversation_rules: string[]; whatsapp_push_rules: string[];
  };
}

const TONE_OPTIONS = [
  { value: "professional_friendly", label: "专业友好（推荐）" },
  { value: "casual_warm", label: "轻松温暖" },
  { value: "formal_business", label: "正式商务" },
];
const EMOJI_OPTIONS = [
  { value: "none", label: "不使用" },
  { value: "moderate", label: "适度（推荐）" },
  { value: "frequent", label: "经常使用" },
];

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const [persona, setPersona] = useState<Persona | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [tab, setTab] = useState<"persona" | "account">("persona");

  useEffect(() => {
    if (!user) return;
    fetch("/api/persona", {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
    }).then(r => r.ok ? r.json() : null).then(d => { if (d) setPersona(d); }).finally(() => setLoading(false));
  }, [user]);

  const save = async () => {
    if (!persona) return;
    setSaving(true); setSaved(false);
    try {
      await fetch("/api/persona", {
        method: "PUT",
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}`, "Content-Type": "application/json" },
        body: JSON.stringify(persona),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch {} finally { setSaving(false); }
  };

  if (!user || loading) return <div className="flex items-center justify-center h-64 text-gray-400">加载中...</div>;

  const inputClass = "w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary focus:border-primary outline-none";
  const labelClass = "block text-sm font-medium text-gray-700 mb-1";

  const updateC = (k: string, v: string | string[]) => setPersona(p => p ? { ...p, company: { ...p.company, [k]: v } } : p);
  const updateS = (k: string, v: string) => setPersona(p => p ? { ...p, salesperson: { ...p.salesperson, [k]: v } } : p);
  const updateSt = (k: string, v: string | number | string[]) => setPersona(p => p ? { ...p, conversation_style: { ...p.conversation_style, [k]: v } } : p);

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">设置</h1>
        {tab === "persona" && (
          <button onClick={save} disabled={saving}
            className="px-6 py-2.5 text-sm font-medium text-white bg-primary hover:bg-blue-700 rounded-lg disabled:opacity-50">
            {saving ? "保存中..." : saved ? "已保存" : "保存设置"}
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200">
        <button onClick={() => setTab("persona")}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${tab === "persona" ? "border-primary text-primary" : "border-transparent text-gray-500 hover:text-gray-700"}`}>
          AI 人设
        </button>
        <button onClick={() => setTab("account")}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${tab === "account" ? "border-primary text-primary" : "border-transparent text-gray-500 hover:text-gray-700"}`}>
          账户
        </button>
      </div>

      {tab === "persona" && persona && (
        <>
          {/* 公司信息 */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">公司信息</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>公司名称</label>
                <input className={inputClass} value={persona.company.name}
                  onChange={e => updateC("name", e.target.value)} placeholder="深圳光明科技有限公司" />
              </div>
              <div>
                <label className={labelClass}>英文名称</label>
                <input className={inputClass} value={persona.company.name_en}
                  onChange={e => updateC("name_en", e.target.value)} placeholder="Bright Tech Co., Ltd." />
              </div>
              <div className="col-span-2">
                <label className={labelClass}>产品/服务</label>
                <input className={inputClass} value={persona.company.products}
                  onChange={e => updateC("products", e.target.value)} placeholder="LED灯具、太阳能路灯" />
              </div>
              <div className="col-span-2">
                <label className={labelClass}>公司优势（每行一条）</label>
                <textarea className={inputClass + " resize-none"} rows={3}
                  value={(persona.company.advantages || []).join("\n")}
                  onChange={e => updateC("advantages", e.target.value.split("\n").filter(Boolean))}
                  placeholder={"15年行业经验\nISO9001认证\n支持OEM/ODM"} />
              </div>
              <div>
                <label className={labelClass}>公司网站</label>
                <input className={inputClass} value={persona.company.website}
                  onChange={e => updateC("website", e.target.value)} placeholder="https://example.com" />
              </div>
              <div>
                <label className={labelClass}>一句话简介</label>
                <input className={inputClass} value={persona.company.description}
                  onChange={e => updateC("description", e.target.value)} placeholder="专业LED灯具制造商" />
              </div>
            </div>
          </div>

          {/* 销售人设 */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">销售人设</h2>
            <p className="text-xs text-gray-400 mb-4">AI 会以这个身份和客户对话</p>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>姓名</label>
                <input className={inputClass} value={persona.salesperson.name}
                  onChange={e => updateS("name", e.target.value)} placeholder="Alex" />
              </div>
              <div>
                <label className={labelClass}>职位</label>
                <input className={inputClass} value={persona.salesperson.title}
                  onChange={e => updateS("title", e.target.value)} placeholder="Sales Manager" />
              </div>
              <div>
                <label className={labelClass}>WhatsApp 号码</label>
                <input className={inputClass} value={persona.salesperson.whatsapp}
                  onChange={e => updateS("whatsapp", e.target.value)} placeholder="+8613800138000" />
              </div>
              <div className="col-span-2">
                <label className={labelClass}>性格特征</label>
                <textarea className={inputClass + " resize-none"} rows={2}
                  value={persona.salesperson.personality}
                  onChange={e => updateS("personality", e.target.value)}
                  placeholder="专业但友好，善于倾听，不急于推销" />
              </div>
            </div>
          </div>

          {/* 对话风格 */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">对话策略</h2>
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div>
                <label className={labelClass}>语气风格</label>
                <select className={inputClass} value={persona.conversation_style.tone}
                  onChange={e => updateSt("tone", e.target.value)}>
                  {TONE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
              <div>
                <label className={labelClass}>消息字数上限</label>
                <input type="number" className={inputClass} value={persona.conversation_style.max_message_length}
                  onChange={e => updateSt("max_message_length", parseInt(e.target.value) || 200)} />
              </div>
              <div>
                <label className={labelClass}>Emoji</label>
                <select className={inputClass} value={persona.conversation_style.emoji_usage}
                  onChange={e => updateSt("emoji_usage", e.target.value)}>
                  {EMOJI_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
            </div>
            <div className="space-y-4">
              <div>
                <label className={labelClass}>打招呼规则（每行一条）</label>
                <textarea className={inputClass + " resize-none"} rows={3}
                  value={(persona.conversation_style.opening_rules || []).join("\n")}
                  onChange={e => updateSt("opening_rules", e.target.value.split("\n").filter(Boolean))}
                  placeholder={"不超过3句话\n以问题结尾\n不提WhatsApp"} />
              </div>
              <div>
                <label className={labelClass}>对话规则（每行一条）</label>
                <textarea className={inputClass + " resize-none"} rows={4}
                  value={(persona.conversation_style.conversation_rules || []).join("\n")}
                  onChange={e => updateSt("conversation_rules", e.target.value.split("\n").filter(Boolean))}
                  placeholder={"每条消息只问一个问题\n先了解需求再介绍产品"} />
              </div>
              <div>
                <label className={labelClass}>推 WhatsApp 规则（每行一条）</label>
                <textarea className={inputClass + " resize-none"} rows={3}
                  value={(persona.conversation_style.whatsapp_push_rules || []).join("\n")}
                  onChange={e => updateSt("whatsapp_push_rules", e.target.value.split("\n").filter(Boolean))}
                  placeholder={"至少3轮后才推\n客户有采购意向才推"} />
              </div>
            </div>
          </div>

          <div className="flex justify-end pb-8">
            <button onClick={save} disabled={saving}
              className="px-8 py-3 text-sm font-medium text-white bg-primary hover:bg-blue-700 rounded-lg disabled:opacity-50">
              {saving ? "保存中..." : saved ? "已保存" : "保存所有设置"}
            </button>
          </div>
        </>
      )}

      {tab === "account" && (
        <>
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 max-w-2xl">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">账户信息</h2>
            <dl className="space-y-3">
              <div className="flex justify-between py-2 border-b border-gray-50">
                <dt className="text-sm text-gray-500">邮箱</dt>
                <dd className="text-sm font-medium">{user.email}</dd>
              </div>
              <div className="flex justify-between py-2 border-b border-gray-50">
                <dt className="text-sm text-gray-500">公司</dt>
                <dd className="text-sm font-medium">{user.company_name || "-"}</dd>
              </div>
            </dl>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 max-w-2xl">
            <button onClick={logout}
              className="px-4 py-2 text-sm font-medium text-red-600 bg-red-50 hover:bg-red-100 rounded-lg">
              退出登录
            </button>
          </div>
        </>
      )}
    </div>
  );
}
