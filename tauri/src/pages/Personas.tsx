import { useEffect, useState } from 'react';
import {
  Plus, ArrowLeft, Save, Trash2, X, Building2, User, Palette,
} from 'lucide-react';
import { personaApi } from '../lib/ipc';

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

interface PersonaRow {
  id: number;
  name: string;
  company_name: string | null;
  company_description: string | null;
  products: string | null;          // JSON string in SQLite
  salesperson_name: string | null;
  salesperson_title: string | null;
  tone: string | null;
  greeting_rules: string | null;    // JSON string
  conversation_rules: string | null;// JSON string
  system_prompt: string | null;
  created_at: string;
  updated_at: string;
}

const toneLabels: Record<string, string> = {
  professional: '专业正式',
  professional_friendly: '专业友好',
  friendly: '友好亲切',
  casual: '轻松随意',
};

const EMPTY_FORM = {
  name: '',
  company_name: '',
  company_description: '',
  products: [] as string[],
  salesperson_name: '',
  salesperson_title: '',
  tone: 'professional_friendly',
  greeting_rules: '',
  conversation_rules: '',
};

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function parseJsonStringOrNull(val: string | null): string[] {
  if (!val) return [];
  try { const p = JSON.parse(val); return Array.isArray(p) ? p : []; }
  catch { return []; }
}

function parseRulesText(val: string | null): string {
  if (!val) return '';
  try {
    const obj = JSON.parse(val);
    return typeof obj === 'object' && obj?.text ? obj.text : (typeof obj === 'string' ? obj : '');
  } catch { return val; }
}

function rowToForm(p: PersonaRow) {
  return {
    name: p.name || '',
    company_name: p.company_name || '',
    company_description: p.company_description || '',
    products: parseJsonStringOrNull(p.products),
    salesperson_name: p.salesperson_name || '',
    salesperson_title: p.salesperson_title || '',
    tone: p.tone || 'professional_friendly',
    greeting_rules: parseRulesText(p.greeting_rules),
    conversation_rules: parseRulesText(p.conversation_rules),
  };
}

function formToPayload(form: typeof EMPTY_FORM) {
  return {
    name: form.name,
    company_name: form.company_name || null,
    company_description: form.company_description || null,
    products: form.products.length > 0 ? JSON.stringify(form.products) : null,
    salesperson_name: form.salesperson_name || null,
    salesperson_title: form.salesperson_title || null,
    tone: form.tone,
    greeting_rules: form.greeting_rules ? JSON.stringify({ text: form.greeting_rules }) : null,
    conversation_rules: form.conversation_rules ? JSON.stringify({ text: form.conversation_rules }) : null,
    system_prompt: generatePrompt(form),
  };
}

function generatePrompt(f: typeof EMPTY_FORM) {
  const toneName = toneLabels[f.tone] || f.tone;
  return `你是 ${f.company_name || '[公司名称]'} 的 ${f.salesperson_title || '[职位]'} ${f.salesperson_name || '[姓名]'}。

公司简介：${f.company_description || '[公司描述]'}
主要产品/服务：${f.products.length > 0 ? f.products.join('、') : '[产品列表]'}

沟通风格：${toneName}

打招呼规则：
${f.greeting_rules || '[打招呼规则]'}

对话规则：
${f.conversation_rules || '[对话规则]'}`;
}

/* ------------------------------------------------------------------ */
/* Component                                                           */
/* ------------------------------------------------------------------ */

export default function Personas() {
  const [personas, setPersonas] = useState<PersonaRow[]>([]);
  const [loading, setLoading] = useState(true);

  // view: 'list' | 'form'
  const [view, setView] = useState<'list' | 'form'>('list');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [productInput, setProductInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  /* ---- Data loading ---- */
  const loadPersonas = async () => {
    try {
      const data = await personaApi.list();
      const list = data as PersonaRow[];
      if (Array.isArray(list)) setPersonas(list);
    } catch {
      // sidecar unavailable
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadPersonas(); }, []);

  /* ---- Product tags ---- */
  const addProduct = () => {
    const v = productInput.trim();
    if (v && !form.products.includes(v)) {
      setForm({ ...form, products: [...form.products, v] });
      setProductInput('');
    }
  };
  const removeProduct = (p: string) => {
    setForm({ ...form, products: form.products.filter(x => x !== p) });
  };

  /* ---- CRUD actions ---- */
  const openCreate = () => {
    setEditingId(null);
    setForm({ ...EMPTY_FORM });
    setError('');
    setView('form');
  };

  const openEdit = async (id: number) => {
    try {
      const data = await personaApi.get(id) as PersonaRow | null;
      if (!data) { setError('人设不存在'); return; }
      setEditingId(id);
      setForm(rowToForm(data));
      setError('');
      setView('form');
    } catch {
      setError('加载人设失败');
    }
  };

  const handleSave = async () => {
    if (!form.name.trim()) { setError('请输入人设名称'); return; }
    setSaving(true);
    setError('');
    try {
      const payload = formToPayload(form);
      if (editingId) {
        await personaApi.update(editingId, payload);
      } else {
        await personaApi.create(payload);
      }
      await loadPersonas();
      setView('list');
    } catch {
      setError('保存失败，请重试');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('确定删除该人设？')) return;
    try {
      await personaApi.delete(id);
      setPersonas(prev => prev.filter(p => p.id !== id));
      if (editingId === id) setView('list');
    } catch {
      setError('删除失败');
    }
  };

  /* ============================================================== */
  /* RENDER: Form view                                               */
  /* ============================================================== */
  if (view === 'form') {
    return (
      <div>
        <div className="mb-8">
          <button
            onClick={() => setView('list')}
            className="mb-4 inline-flex items-center gap-1.5 text-sm text-[#86868b] hover:text-[#1d1d1f] transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            返回人设列表
          </button>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-[#1d1d1f]">
                {editingId ? '编辑人设' : '创建新人设'}
              </h1>
              <p className="mt-1 text-sm text-[#86868b]">配置 AI 销售代表的身份、公司信息和对话风格</p>
            </div>
            {editingId && (
              <button
                onClick={() => handleDelete(editingId)}
                className="inline-flex items-center gap-1.5 rounded-full border border-red-200 bg-red-50 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-100"
              >
                <Trash2 className="h-4 w-4" />
                删除
              </button>
            )}
          </div>
        </div>

        {error && (
          <div className="mb-6 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{error}</div>
        )}

        <div className="space-y-6">
          {/* Name */}
          <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
            <h2 className="mb-4 text-base font-semibold text-[#1d1d1f]">人设名称</h2>
            <input
              type="text"
              value={form.name}
              onChange={e => setForm({ ...form, name: e.target.value })}
              placeholder="例如：专业商务顾问"
              className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none focus:border-[#0071e3] focus:bg-white"
            />
          </div>

          {/* Company Info */}
          <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
            <h2 className="mb-4 text-base font-semibold text-[#1d1d1f]">公司信息</h2>
            <div className="space-y-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">公司名称</label>
                <input
                  type="text"
                  value={form.company_name}
                  onChange={e => setForm({ ...form, company_name: e.target.value })}
                  placeholder="例如：TechBridge"
                  className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none focus:border-[#0071e3] focus:bg-white"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">公司描述</label>
                <textarea
                  value={form.company_description}
                  onChange={e => setForm({ ...form, company_description: e.target.value })}
                  placeholder="简要描述公司业务和优势..."
                  rows={3}
                  className="w-full resize-none rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none focus:border-[#0071e3] focus:bg-white"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">产品/服务</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={productInput}
                    onChange={e => setProductInput(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addProduct(); } }}
                    placeholder="输入后按回车添加"
                    className="flex-1 rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none focus:border-[#0071e3] focus:bg-white"
                  />
                  <button onClick={addProduct} className="rounded-xl border border-[#e5e5e7] px-3 py-3 text-[#86868b] hover:bg-[#f5f5f7] hover:text-[#1d1d1f]">
                    <Plus className="h-4 w-4" />
                  </button>
                </div>
                {form.products.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {form.products.map(p => (
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

          {/* Salesperson */}
          <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
            <h2 className="mb-4 text-base font-semibold text-[#1d1d1f]">销售代表信息</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">姓名</label>
                <input
                  type="text"
                  value={form.salesperson_name}
                  onChange={e => setForm({ ...form, salesperson_name: e.target.value })}
                  placeholder="例如：张伟"
                  className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none focus:border-[#0071e3] focus:bg-white"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">职位</label>
                <input
                  type="text"
                  value={form.salesperson_title}
                  onChange={e => setForm({ ...form, salesperson_title: e.target.value })}
                  placeholder="例如：商务经理"
                  className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none focus:border-[#0071e3] focus:bg-white"
                />
              </div>
            </div>
          </div>

          {/* Style */}
          <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
            <h2 className="mb-4 text-base font-semibold text-[#1d1d1f]">对话风格</h2>
            <div className="space-y-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">语气风格</label>
                <select
                  value={form.tone}
                  onChange={e => setForm({ ...form, tone: e.target.value })}
                  className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none focus:border-[#0071e3] focus:bg-white"
                >
                  <option value="professional">专业正式</option>
                  <option value="professional_friendly">专业友好</option>
                  <option value="friendly">友好亲切</option>
                  <option value="casual">轻松随意</option>
                </select>
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">打招呼规则</label>
                <textarea
                  value={form.greeting_rules}
                  onChange={e => setForm({ ...form, greeting_rules: e.target.value })}
                  placeholder="定义 AI 如何开始对话，例如：先赞美对方的成就，然后自然引出合作意向..."
                  rows={3}
                  className="w-full resize-none rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none focus:border-[#0071e3] focus:bg-white"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">对话规则</label>
                <textarea
                  value={form.conversation_rules}
                  onChange={e => setForm({ ...form, conversation_rules: e.target.value })}
                  placeholder="定义后续对话的规则，例如：不要过于推销，注重建立关系，适时询问需求..."
                  rows={3}
                  className="w-full resize-none rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none focus:border-[#0071e3] focus:bg-white"
                />
              </div>
            </div>
          </div>

          {/* Submit */}
          <div className="flex justify-end gap-3 pt-2">
            <button
              onClick={() => setView('list')}
              className="rounded-full border border-[#e5e5e7] px-6 py-2.5 text-sm font-medium text-[#1d1d1f] hover:bg-[#f5f5f7]"
            >
              取消
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !form.name.trim()}
              className="inline-flex items-center gap-2 rounded-full bg-[#0071e3] px-6 py-2.5 text-sm font-medium text-white hover:bg-[#0077ed] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Save className="h-4 w-4" />
              {saving ? '保存中...' : editingId ? '保存修改' : '创建人设'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  /* ============================================================== */
  /* RENDER: List view                                               */
  /* ============================================================== */
  return (
    <div>
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-[#1d1d1f]">人设管理</h1>
          <p className="mt-1 text-sm text-[#86868b]">配置 AI 销售代表的人设和对话风格</p>
        </div>
        <button
          onClick={openCreate}
          className="inline-flex items-center gap-2 rounded-full bg-[#0071e3] px-5 py-2.5 text-sm font-medium text-white hover:bg-[#0077ed]"
        >
          <Plus className="h-4 w-4" />
          新建人设
        </button>
      </div>

      {loading && (
        <div className="py-12 text-center text-sm text-[#86868b]">加载中...</div>
      )}

      {!loading && personas.length === 0 && (
        <div className="rounded-2xl bg-white p-12 border border-[#e5e5e7]/60 shadow-sm text-center">
          <User className="mx-auto h-12 w-12 text-[#86868b]/40" />
          <h2 className="mt-4 text-lg font-semibold text-[#1d1d1f]">创建你的第一个 AI 人设</h2>
          <p className="mt-2 text-sm text-[#86868b]">人设定义了 AI 如何与潜在客户沟通</p>
          <button
            onClick={openCreate}
            className="mt-6 inline-flex items-center gap-2 rounded-full bg-[#0071e3] px-5 py-2.5 text-sm font-medium text-white hover:bg-[#0077ed]"
          >
            <Plus className="h-4 w-4" />
            新建人设
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {personas.map(persona => (
          <div
            key={persona.id}
            onClick={() => openEdit(persona.id)}
            className="group relative cursor-pointer rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm transition-all hover:shadow-md"
          >
            <div className="flex items-start justify-between">
              <h3 className="mb-4 text-base font-semibold text-[#1d1d1f] group-hover:text-[#0071e3] transition-colors">
                {persona.name}
              </h3>
              <button
                onClick={e => { e.stopPropagation(); handleDelete(persona.id); }}
                className="opacity-0 group-hover:opacity-100 p-1 rounded-lg text-[#86868b] hover:text-red-500 hover:bg-red-50 transition-all"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
            <div className="space-y-2.5">
              <div className="flex items-center gap-2">
                <Building2 className="h-4 w-4 text-[#86868b]" />
                <span className="text-sm text-[#86868b]">{persona.company_name || '-'}</span>
              </div>
              <div className="flex items-center gap-2">
                <User className="h-4 w-4 text-[#86868b]" />
                <span className="text-sm text-[#86868b]">{persona.salesperson_name || '-'}</span>
              </div>
              <div className="flex items-center gap-2">
                <Palette className="h-4 w-4 text-[#86868b]" />
                <span className="inline-flex rounded-full bg-[#f5f5f7] px-2.5 py-0.5 text-xs font-medium text-[#86868b]">
                  {toneLabels[persona.tone || ''] || persona.tone || '-'}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
