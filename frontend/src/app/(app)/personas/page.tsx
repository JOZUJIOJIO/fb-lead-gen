'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Plus, Star, Building2, User, Palette, Trash2, MessageSquare, CheckCircle } from 'lucide-react';
import { personaApi } from '@/lib/api';
import { personaStore, type LocalPersona } from '@/lib/localStore';

interface Persona {
  id: number;
  name: string;
  company_name: string | null;
  salesperson_name: string | null;
  tone: string | null;
  greeting_rules: { text?: string } | null;
  conversation_rules: { text?: string } | null;
  is_default: boolean;
}

const toneLabels: Record<string, string> = {
  professional: '专业正式',
  professional_friendly: '专业友好',
  friendly: '友好亲切',
  casual: '轻松随意',
};

export default function PersonasPage() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchPersonas = () => {
    // 1. Load from localStorage FIRST (instant, always available)
    const local = personaStore.list();
    if (local.length > 0) {
      setPersonas(local as Persona[]);
    }

    // 2. Background sync from backend API
    personaApi.list()
      .then(res => {
        const backendList = res.data as LocalPersona[];
        if (Array.isArray(backendList) && backendList.length > 0) {
          // Backend has data — use it as source of truth and update localStorage
          personaStore.replaceFromBackend(backendList);
          setPersonas(backendList as Persona[]);
        }
      })
      .catch(() => {
        // Backend unavailable — localStorage data already shown
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchPersonas();
  }, []);

  const handleDelete = async (e: React.MouseEvent, id: number) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm('确定删除该人设？')) return;
    // 1. Delete from localStorage first
    personaStore.delete(id);
    setPersonas(personaStore.list() as Persona[]);
    // 2. Background sync to backend
    try {
      await personaApi.delete(String(id));
    } catch (err) {
      console.error('Failed to delete persona from backend:', err);
    }
  };

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

      {loading && (
        <div className="py-12 text-center text-sm text-[#86868b]">加载中...</div>
      )}

      {!loading && personas.length === 0 && (
        <div className="rounded-2xl bg-white p-12 border border-[#e5e5e7]/60 shadow-sm text-center">
          <User className="mx-auto h-12 w-12 text-[#86868b]/40" />
          <h2 className="mt-4 text-lg font-semibold text-[#1d1d1f]">创建你的第一个 AI 人设</h2>
          <p className="mt-2 text-sm text-[#86868b]">人设定义了 AI 如何与潜在客户沟通</p>
        </div>
      )}

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
            <div className="flex items-start justify-between">
              <h3 className="mb-4 text-base font-semibold text-[#1d1d1f] group-hover:text-[#0071e3] transition-colors">
                {persona.name}
              </h3>
              <button
                onClick={(e) => handleDelete(e, persona.id)}
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
              {/* Rules status */}
              <div className="flex items-center gap-2">
                <MessageSquare className="h-4 w-4 text-[#86868b]" />
                <div className="flex items-center gap-1.5">
                  {persona.greeting_rules?.text ? (
                    <span className="inline-flex items-center gap-0.5 text-xs text-emerald-600"><CheckCircle className="h-3 w-3" />打招呼</span>
                  ) : (
                    <span className="text-xs text-[#c1c1c4]">打招呼未配</span>
                  )}
                  <span className="text-[#e5e5e7]">·</span>
                  {persona.conversation_rules?.text ? (
                    <span className="inline-flex items-center gap-0.5 text-xs text-emerald-600"><CheckCircle className="h-3 w-3" />对话</span>
                  ) : (
                    <span className="text-xs text-[#c1c1c4]">对话未配</span>
                  )}
                </div>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
