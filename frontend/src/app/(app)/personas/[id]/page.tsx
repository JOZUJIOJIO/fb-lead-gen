'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, X, Plus, Save, Eye, Star, Trash2 } from 'lucide-react';
import { personaApi } from '@/lib/api';
import { personaStore } from '@/lib/localStore';
import TranslateButton from '@/components/TranslateButton';

interface PersonaData {
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
}

export default function PersonaDetailPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const [loading, setLoading] = useState(true);

  // Company
  const [companyName, setCompanyName] = useState('');
  const [companyDesc, setCompanyDesc] = useState('');
  const [products, setProducts] = useState<string[]>([]);
  const [productInput, setProductInput] = useState('');

  // Salesperson
  const [salesName, setSalesName] = useState('');
  const [salesTitle, setSalesTitle] = useState('');

  // Style
  const [tone, setTone] = useState('professional');
  const [greetingRules, setGreetingRules] = useState('');
  const [conversationRules, setConversationRules] = useState('');

  // Language & Contact
  const [outputLanguage, setOutputLanguage] = useState('auto');
  const [whatsappId, setWhatsappId] = useState('');
  const [telegramId, setTelegramId] = useState('');

  // System prompt
  const [systemPrompt, setSystemPrompt] = useState('');
  const [promptMode, setPromptMode] = useState<'auto' | 'custom'>('auto');

  const [personaName, setPersonaName] = useState('');
  const [isDefault, setIsDefault] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [isDirty, setIsDirty] = useState(false);

  useEffect(() => {
    // 1. Try loading from localStorage first (instant)
    const local = personaStore.get(Number(params.id));
    if (local) {
      setPersonaName(local.name);
      setCompanyName(local.company_name || '');
      setCompanyDesc(local.company_description || '');
      setProducts(Array.isArray(local.products) ? local.products : []);
      setSalesName(local.salesperson_name || '');
      setSalesTitle(local.salesperson_title || '');
      setTone(local.tone || 'professional');
      const gr = local.greeting_rules as { text?: string } | null;
      const cr = local.conversation_rules as { text?: string } | null;
      setGreetingRules(gr?.text || '');
      setConversationRules(cr?.text || '');
      setOutputLanguage(local.output_language || 'auto');
      setWhatsappId(local.whatsapp_id || '');
      setTelegramId(local.telegram_id || '');
      if (local.system_prompt) {
        setSystemPrompt(local.system_prompt);
        setPromptMode('custom');
      }
      setIsDefault(local.is_default ?? false);
      setLoading(false);
    }

    // 2. Background sync from backend API
    personaApi.get(params.id)
      .then(res => {
        const p: PersonaData = res.data;
        setPersonaName(p.name);
        setCompanyName(p.company_name || '');
        setCompanyDesc(p.company_description || '');
        setProducts(Array.isArray(p.products) ? p.products : []);
        setSalesName(p.salesperson_name || '');
        setSalesTitle(p.salesperson_title || '');
        setTone(p.tone || 'professional');
        setGreetingRules(p.greeting_rules?.text || '');
        setConversationRules(p.conversation_rules?.text || '');
        setOutputLanguage(p.output_language || 'auto');
        setWhatsappId(p.whatsapp_id || '');
        setTelegramId(p.telegram_id || '');
        if (p.system_prompt) {
          setSystemPrompt(p.system_prompt);
          setPromptMode('custom');
        }
        setIsDefault(p.is_default);
      })
      .catch(err => {
        if (!local) {
          console.error('Failed to load persona:', err);
          setError('人设不存在');
        }
      })
      .finally(() => setLoading(false));
  }, [params.id]);

  // Warn before leaving with unsaved changes
  useEffect(() => {
    if (!isDirty) return;
    const handler = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [isDirty]);

  const markDirty = () => { if (!isDirty) setIsDirty(true); };

  const addProduct = () => {
    if (productInput.trim() && !products.includes(productInput.trim())) {
      setProducts([...products, productInput.trim()]);
      setProductInput('');
    }
  };

  const removeProduct = (p: string) => {
    setProducts(products.filter((item) => item !== p));
  };

  const handleProductKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addProduct();
    }
  };

  const generatePreview = () => {
    return `你是 ${companyName || '[公司名称]'} 的 ${salesTitle || '[职位]'} ${salesName || '[姓名]'}。

公司简介：${companyDesc || '[公司描述]'}
主要产品/服务：${products.length > 0 ? products.join('、') : '[产品列表]'}

沟通风格：${tone === 'professional' ? '专业正式' : tone === 'friendly' ? '友好亲切' : tone === 'professional_friendly' ? '专业友好' : '轻松随意'}

打招呼规则：
${greetingRules || '[打招呼规则]'}

对话规则：
${conversationRules || '[对话规则]'}`;
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setError('');

    const payload = {
      name: personaName,
      company_name: companyName || null,
      company_description: companyDesc || null,
      products: products.length > 0 ? products : null,
      salesperson_name: salesName || null,
      salesperson_title: salesTitle || null,
      tone,
      greeting_rules: greetingRules ? { text: greetingRules } : null,
      conversation_rules: conversationRules ? { text: conversationRules } : null,
      system_prompt: promptMode === 'custom' ? systemPrompt : generatePreview(),
      output_language: outputLanguage,
      whatsapp_id: whatsappId || null,
      telegram_id: telegramId || null,
      is_default: isDefault,
    };

    // 1. Save to localStorage FIRST
    personaStore.update(Number(params.id), payload);

    // 2. Background sync to backend
    try {
      await personaApi.update(params.id, payload);
    } catch {
      // Backend sync failed — data safe in localStorage
    }

    setIsSubmitting(false);
    router.push('/personas');
  };

  const handleDelete = async () => {
    if (!confirm('确定删除该人设？此操作不可撤销。')) return;
    // 1. Delete from localStorage first
    personaStore.delete(Number(params.id));
    // 2. Background sync to backend
    try { await personaApi.delete(params.id); } catch {}
    router.push('/personas');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <p className="text-sm text-[#86868b]">加载中...</p>
      </div>
    );
  }

  if (error && !personaName) {
    return (
      <div className="text-center py-24">
        <p className="text-sm text-[#86868b]">{error}</p>
        <Link href="/personas" className="mt-4 inline-block text-sm text-[#0071e3] hover:underline">返回人设列表</Link>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-8">
        <Link href="/personas" className="mb-4 inline-flex items-center gap-1.5 text-sm text-[#86868b] hover:text-[#1d1d1f] transition-colors">
          <ArrowLeft className="h-4 w-4" />
          返回人设列表
        </Link>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-[#1d1d1f]">编辑人设</h1>
            <p className="mt-1 text-sm text-[#86868b]">修改 AI 销售代表的配置</p>
          </div>
          <button
            onClick={handleDelete}
            className="inline-flex items-center gap-1.5 rounded-full border border-red-200 bg-red-50 px-4 py-2 text-sm font-medium text-red-700 transition-colors hover:bg-red-100"
          >
            <Trash2 className="h-4 w-4" />
            删除
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-6 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="space-y-6">
        {/* Persona Name + Default */}
        <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
          <h2 className="mb-4 text-base font-semibold text-[#1d1d1f]">人设名称</h2>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={personaName}
              onChange={(e) => { setPersonaName(e.target.value); markDirty(); }}
              placeholder="例如：专业商务顾问"
              className="flex-1 rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
            />
            <TranslateButton text={personaName} onTranslated={(v) => { setPersonaName(v); markDirty(); }} />
          </div>
          <label className="mt-3 inline-flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={isDefault}
              onChange={(e) => setIsDefault(e.target.checked)}
              className="h-4 w-4 rounded border-[#e5e5e7] text-[#0071e3] focus:ring-[#0071e3]"
            />
            <Star className="h-4 w-4 text-amber-500" />
            <span className="text-sm text-[#1d1d1f]">设为默认人设</span>
          </label>
        </div>

        {/* Company Info */}
        <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
          <h2 className="mb-4 text-base font-semibold text-[#1d1d1f]">公司信息</h2>
          <div className="space-y-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">公司名称</label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={companyName}
                  onChange={(e) => { setCompanyName(e.target.value); markDirty(); }}
                  placeholder="例如：TechBridge"
                  className="flex-1 rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
                />
                <TranslateButton text={companyName} onTranslated={(v) => { setCompanyName(v); markDirty(); }} />
              </div>
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">公司描述</label>
              <div>
                <textarea
                  value={companyDesc}
                  onChange={(e) => { setCompanyDesc(e.target.value); markDirty(); }}
                  placeholder="简要描述公司业务和优势..."
                  rows={3}
                  className="w-full resize-none rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
                />
                <div className="mt-1 flex justify-end">
                  <TranslateButton text={companyDesc} onTranslated={(v) => { setCompanyDesc(v); markDirty(); }} />
                </div>
              </div>
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">产品/服务</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={productInput}
                  onChange={(e) => setProductInput(e.target.value)}
                  onKeyDown={handleProductKeyDown}
                  placeholder="输入后按回车添加"
                  className="flex-1 rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
                />
                <button
                  onClick={addProduct}
                  className="rounded-xl border border-[#e5e5e7] px-3 py-3 text-[#86868b] transition-colors hover:bg-[#f5f5f7] hover:text-[#1d1d1f]"
                >
                  <Plus className="h-4 w-4" />
                </button>
              </div>
              {products.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {products.map((p) => (
                    <span key={p} className="inline-flex items-center gap-1 rounded-full bg-[#f5f5f7] px-3 py-1 text-xs font-medium text-[#1d1d1f]">
                      {p}
                      <button onClick={() => removeProduct(p)} className="text-[#86868b] hover:text-red-500">
                        <X className="h-3 w-3" />
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Salesperson Info */}
        <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
          <h2 className="mb-4 text-base font-semibold text-[#1d1d1f]">销售代表信息</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">姓名</label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={salesName}
                  onChange={(e) => { setSalesName(e.target.value); markDirty(); }}
                  placeholder="例如：张伟"
                  className="flex-1 rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
                />
                <TranslateButton text={salesName} onTranslated={(v) => { setSalesName(v); markDirty(); }} />
              </div>
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">职位</label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={salesTitle}
                  onChange={(e) => { setSalesTitle(e.target.value); markDirty(); }}
                  placeholder="例如：商务经理"
                  className="flex-1 rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
                />
                <TranslateButton text={salesTitle} onTranslated={(v) => { setSalesTitle(v); markDirty(); }} />
              </div>
            </div>
          </div>
        </div>

        {/* Style Settings */}
        <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
          <h2 className="mb-4 text-base font-semibold text-[#1d1d1f]">对话风格</h2>
          <div className="space-y-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">语气风格</label>
              <select
                value={tone}
                onChange={(e) => { setTone(e.target.value); markDirty(); }}
                className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
              >
                <option value="professional">专业正式</option>
                <option value="professional_friendly">专业友好</option>
                <option value="friendly">友好亲切</option>
                <option value="casual">轻松随意</option>
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">打招呼规则</label>
              <div>
                <textarea
                  value={greetingRules}
                  onChange={(e) => { setGreetingRules(e.target.value); markDirty(); }}
                  placeholder="定义 AI 如何开始对话..."
                  rows={3}
                  className="w-full resize-none rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
                />
                <div className="mt-1 flex justify-end">
                  <TranslateButton text={greetingRules} onTranslated={(v) => { setGreetingRules(v); markDirty(); }} />
                </div>
              </div>
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">对话规则</label>
              <div>
                <textarea
                  value={conversationRules}
                  onChange={(e) => { setConversationRules(e.target.value); markDirty(); }}
                  placeholder="定义后续对话的规则..."
                  rows={3}
                  className="w-full resize-none rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
                />
                <div className="mt-1 flex justify-end">
                  <TranslateButton text={conversationRules} onTranslated={(v) => { setConversationRules(v); markDirty(); }} />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Output Language */}
        <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
          <h2 className="mb-1 text-base font-semibold text-[#1d1d1f]">输出语言</h2>
          <p className="mb-3 text-xs text-[#86868b]">AI 生成的问候语和回复将使用该语言</p>
          <select
            value={outputLanguage}
            onChange={(e) => { setOutputLanguage(e.target.value); markDirty(); }}
            className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
          >
            <option value="auto">自动检测（根据人设内容判断）</option>
            <option value="en">English</option>
            <option value="zh">中文</option>
          </select>
        </div>

        {/* Private Domain Contact */}
        <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
          <h2 className="mb-1 text-base font-semibold text-[#1d1d1f]">私域联系方式</h2>
          <p className="mb-4 text-xs text-[#86868b]">AI 会在对话中引导对方通过以下方式联系你</p>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">WhatsApp</label>
              <input
                type="text"
                value={whatsappId}
                onChange={(e) => { setWhatsappId(e.target.value); markDirty(); }}
                placeholder="例如：+8613800138000"
                className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">Telegram</label>
              <input
                type="text"
                value={telegramId}
                onChange={(e) => { setTelegramId(e.target.value); markDirty(); }}
                placeholder="例如：@your_username"
                className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
              />
            </div>
          </div>
        </div>

        {/* System Prompt */}
        <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-[#1d1d1f]">系统提示词</h2>
            <div className="flex items-center gap-1 rounded-lg bg-[#f5f5f7] p-0.5">
              <button
                onClick={() => setPromptMode('auto')}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${promptMode === 'auto' ? 'bg-white text-[#1d1d1f] shadow-sm' : 'text-[#86868b] hover:text-[#1d1d1f]'}`}
              >
                自动生成
              </button>
              <button
                onClick={() => { setPromptMode('custom'); if (!systemPrompt) setSystemPrompt(generatePreview()); markDirty(); }}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${promptMode === 'custom' ? 'bg-white text-[#1d1d1f] shadow-sm' : 'text-[#86868b] hover:text-[#1d1d1f]'}`}
              >
                自定义编辑
              </button>
            </div>
          </div>
          {promptMode === 'auto' ? (
            <div className="rounded-xl bg-[#fafafa] border border-[#e5e5e7]/60 p-4">
              <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-[#1d1d1f]">
                {generatePreview()}
              </pre>
              <p className="mt-3 text-xs text-[#86868b]">由上方字段自动拼接生成，切换到「自定义编辑」可直接修改</p>
            </div>
          ) : (
            <div>
              <textarea
                value={systemPrompt}
                onChange={(e) => { setSystemPrompt(e.target.value); markDirty(); }}
                placeholder="输入完整的系统提示词，定义 AI 的身份、行为规则和对话策略..."
                rows={12}
                className="w-full resize-y rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none transition-colors focus:border-[#0071e3] focus:bg-white font-mono leading-relaxed"
              />
              <div className="mt-2 flex items-center justify-between">
                <p className="text-xs text-[#86868b]">完全自定义 AI 的行为，支持任意格式</p>
                <button
                  onClick={() => { setSystemPrompt(generatePreview()); markDirty(); }}
                  className="text-xs text-[#0071e3] hover:underline"
                >
                  从字段重新生成
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Submit */}
        <div className="flex items-center justify-end gap-3 pt-2">
          {isDirty && (
            <span className="text-xs text-amber-600 mr-auto">有未保存的修改</span>
          )}
          <Link
            href="/personas"
            onClick={(e) => { if (isDirty && !confirm('有未保存的修改，确定离开？')) e.preventDefault(); }}
            className="rounded-full border border-[#e5e5e7] px-6 py-2.5 text-sm font-medium text-[#1d1d1f] transition-colors hover:bg-[#f5f5f7]"
          >
            取消
          </Link>
          <button
            onClick={handleSubmit}
            disabled={isSubmitting || !personaName}
            className="inline-flex items-center gap-2 rounded-full bg-[#0071e3] px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#0077ed] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Save className="h-4 w-4" />
            {isSubmitting ? '保存中...' : '保存修改'}
          </button>
        </div>
      </div>
    </div>
  );
}
