import { useEffect, useState } from 'react';
import { Plus, Star, Building2, User, Palette } from 'lucide-react';
import { personaApi } from '../lib/ipc';

interface Persona {
  id: number;
  name: string;
  company: string;
  salesperson_name: string;
  tone: string;
  is_default: boolean;
}

const mockPersonas: Persona[] = [
  {
    id: 1,
    name: '专业商务顾问',
    company: 'TechBridge',
    salesperson_name: '张伟',
    tone: 'professional',
    is_default: true,
  },
  {
    id: 2,
    name: '友好销售代表',
    company: 'LeadFlow',
    salesperson_name: '李明',
    tone: 'friendly',
    is_default: false,
  },
  {
    id: 3,
    name: '行业专家',
    company: 'AI Solutions',
    salesperson_name: 'Alex Chen',
    tone: 'casual',
    is_default: false,
  },
];

const toneLabels: Record<string, string> = {
  professional: '专业正式',
  friendly: '友好亲切',
  casual: '轻松随意',
};

export default function Personas() {
  const [personas, setPersonas] = useState<Persona[]>(mockPersonas);
  const [loading, setLoading] = useState(true);
  const [showNewForm, setShowNewForm] = useState(false);
  const [newName, setNewName] = useState('');
  const [newCompany, setNewCompany] = useState('');
  const [newSalesperson, setNewSalesperson] = useState('');
  const [newTone, setNewTone] = useState('professional');

  useEffect(() => {
    personaApi
      .list()
      .then((data: unknown) => {
        const list = data as Persona[];
        if (Array.isArray(list) && list.length > 0) {
          setPersonas(list);
        }
      })
      .catch(() => {
        // Keep mock data
      })
      .finally(() => setLoading(false));
  }, []);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    try {
      await personaApi.create({
        name: newName,
        company: newCompany,
        salesperson_name: newSalesperson,
        tone: newTone,
      });
      // Refresh
      const updated = await personaApi.list();
      const list = updated as Persona[];
      if (Array.isArray(list)) setPersonas(list);
    } catch {
      // Add optimistically
      setPersonas((prev) => [
        ...prev,
        {
          id: Date.now(),
          name: newName,
          company: newCompany,
          salesperson_name: newSalesperson,
          tone: newTone,
          is_default: false,
        },
      ]);
    }
    setNewName('');
    setNewCompany('');
    setNewSalesperson('');
    setNewTone('professional');
    setShowNewForm(false);
  };

  return (
    <div>
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-[#1d1d1f]">
            人设管理
          </h1>
          <p className="mt-1 text-sm text-[#86868b]">
            配置 AI 销售代表的人设和对话风格
          </p>
        </div>
        <button
          onClick={() => setShowNewForm(true)}
          className="inline-flex items-center gap-2 rounded-full bg-[#0071e3] px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#0077ed]"
        >
          <Plus className="h-4 w-4" />
          新建人设
        </button>
      </div>

      {loading && (
        <div className="mb-4 rounded-xl bg-yellow-50 px-4 py-2.5 text-sm text-yellow-700">
          正在加载人设数据...
        </div>
      )}

      {/* New persona form */}
      {showNewForm && (
        <div className="mb-6 rounded-2xl bg-white p-6 border border-[#0071e3]/30 shadow-sm">
          <h3 className="mb-4 text-base font-semibold text-[#1d1d1f]">
            新建人设
          </h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">
                人设名称
              </label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="例：专业商务顾问"
                className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-2.5 text-sm outline-none focus:border-[#0071e3] focus:bg-white"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">
                公司
              </label>
              <input
                type="text"
                value={newCompany}
                onChange={(e) => setNewCompany(e.target.value)}
                placeholder="公司名称"
                className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-2.5 text-sm outline-none focus:border-[#0071e3] focus:bg-white"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">
                销售代表姓名
              </label>
              <input
                type="text"
                value={newSalesperson}
                onChange={(e) => setNewSalesperson(e.target.value)}
                placeholder="姓名"
                className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-2.5 text-sm outline-none focus:border-[#0071e3] focus:bg-white"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">
                对话风格
              </label>
              <select
                value={newTone}
                onChange={(e) => setNewTone(e.target.value)}
                className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-2.5 text-sm outline-none focus:border-[#0071e3] focus:bg-white"
              >
                <option value="professional">专业正式</option>
                <option value="friendly">友好亲切</option>
                <option value="casual">轻松随意</option>
              </select>
            </div>
          </div>
          <div className="mt-4 flex gap-3">
            <button
              onClick={handleCreate}
              className="rounded-full bg-[#0071e3] px-5 py-2 text-sm font-medium text-white hover:bg-[#0077ed]"
            >
              创建
            </button>
            <button
              onClick={() => setShowNewForm(false)}
              className="rounded-full border border-[#e5e5e7] px-5 py-2 text-sm font-medium text-[#1d1d1f] hover:bg-[#f5f5f7]"
            >
              取消
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {personas.map((persona) => (
          <div
            key={persona.id}
            className={`relative rounded-2xl bg-white p-6 border shadow-sm transition-shadow hover:shadow-md ${
              persona.is_default
                ? 'border-[#0071e3]/40 ring-1 ring-[#0071e3]/20'
                : 'border-[#e5e5e7]/60'
            }`}
          >
            {persona.is_default && (
              <div className="absolute -top-2 right-4 flex items-center gap-1 rounded-full bg-[#0071e3] px-2.5 py-0.5 text-[10px] font-semibold text-white">
                <Star className="h-3 w-3" />
                默认
              </div>
            )}
            <h3 className="mb-4 text-base font-semibold text-[#1d1d1f]">
              {persona.name}
            </h3>
            <div className="space-y-2.5">
              <div className="flex items-center gap-2">
                <Building2 className="h-4 w-4 text-[#86868b]" />
                <span className="text-sm text-[#86868b]">{persona.company}</span>
              </div>
              <div className="flex items-center gap-2">
                <User className="h-4 w-4 text-[#86868b]" />
                <span className="text-sm text-[#86868b]">
                  {persona.salesperson_name}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Palette className="h-4 w-4 text-[#86868b]" />
                <span className="inline-flex rounded-full bg-[#f5f5f7] px-2.5 py-0.5 text-xs font-medium text-[#86868b]">
                  {toneLabels[persona.tone] ?? persona.tone}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
