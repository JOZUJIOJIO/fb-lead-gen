'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Plus, Star, Building2, User, Palette } from 'lucide-react';

interface Persona {
  id: string;
  name: string;
  company: string;
  salesperson_name: string;
  tone: string;
  is_default: boolean;
}

const mockPersonas: Persona[] = [
  { id: '1', name: '专业商务顾问', company: 'TechBridge', salesperson_name: '张伟', tone: 'professional', is_default: true },
  { id: '2', name: '友好销售代表', company: 'LeadFlow', salesperson_name: '李明', tone: 'friendly', is_default: false },
  { id: '3', name: '行业专家', company: 'AI Solutions', salesperson_name: 'Alex Chen', tone: 'casual', is_default: false },
];

const toneLabels: Record<string, string> = {
  professional: '专业正式',
  friendly: '友好亲切',
  casual: '轻松随意',
};

export default function PersonasPage() {
  const [personas, setPersonas] = useState<Persona[]>(mockPersonas);

  useEffect(() => {
    // TODO: Fetch real data
    // personaApi.list().then(res => setPersonas(res.data));
  }, []);

  return (
    <div>
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-[#1d1d1f]">人设管理</h1>
          <p className="mt-1 text-sm text-[#86868b]">配置 AI 销售代表的人设和对话风格</p>
        </div>
        <Link
          href="/personas/new"
          className="inline-flex items-center gap-2 rounded-full bg-[#0071e3] px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#0077ed]"
        >
          <Plus className="h-4 w-4" />
          新建人设
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {personas.map((persona) => (
          <Link
            key={persona.id}
            href={`/personas/${persona.id}`}
            className={`group relative rounded-2xl bg-white p-6 border shadow-sm transition-all hover:shadow-md ${
              persona.is_default ? 'border-[#0071e3]/40 ring-1 ring-[#0071e3]/20' : 'border-[#e5e5e7]/60'
            }`}
          >
            {persona.is_default && (
              <div className="absolute -top-2 right-4 flex items-center gap-1 rounded-full bg-[#0071e3] px-2.5 py-0.5 text-[10px] font-semibold text-white">
                <Star className="h-3 w-3" />
                默认
              </div>
            )}
            <h3 className="mb-4 text-base font-semibold text-[#1d1d1f] group-hover:text-[#0071e3] transition-colors">
              {persona.name}
            </h3>
            <div className="space-y-2.5">
              <div className="flex items-center gap-2">
                <Building2 className="h-4 w-4 text-[#86868b]" />
                <span className="text-sm text-[#86868b]">{persona.company}</span>
              </div>
              <div className="flex items-center gap-2">
                <User className="h-4 w-4 text-[#86868b]" />
                <span className="text-sm text-[#86868b]">{persona.salesperson_name}</span>
              </div>
              <div className="flex items-center gap-2">
                <Palette className="h-4 w-4 text-[#86868b]" />
                <span className="inline-flex rounded-full bg-[#f5f5f7] px-2.5 py-0.5 text-xs font-medium text-[#86868b]">
                  {toneLabels[persona.tone] || persona.tone}
                </span>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
