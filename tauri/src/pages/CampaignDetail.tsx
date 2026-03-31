import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Play, Pause, StopCircle, Pencil, Save, X } from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import { campaignApi, personaApi } from '../lib/ipc';

/* ------------------------------------------------------------------ */
/* Country list (same as NewCampaign)                                  */
/* ------------------------------------------------------------------ */
const COUNTRIES = [
  { value: '', label: '全部国家/地区' },
  { value: 'United States', label: '美国' },
  { value: 'Canada', label: '加拿大' },
  { value: 'Mexico', label: '墨西哥' },
  { value: 'United Kingdom', label: '英国' },
  { value: 'Germany', label: '德国' },
  { value: 'France', label: '法国' },
  { value: 'Italy', label: '意大利' },
  { value: 'Spain', label: '西班牙' },
  { value: 'Netherlands', label: '荷兰' },
  { value: 'Poland', label: '波兰' },
  { value: 'Sweden', label: '瑞典' },
  { value: 'Switzerland', label: '瑞士' },
  { value: 'Turkey', label: '土耳其' },
  { value: 'Russia', label: '俄罗斯' },
  { value: 'Japan', label: '日本' },
  { value: 'South Korea', label: '韩国' },
  { value: 'India', label: '印度' },
  { value: 'Thailand', label: '泰国' },
  { value: 'Vietnam', label: '越南' },
  { value: 'Philippines', label: '菲律宾' },
  { value: 'Indonesia', label: '印度尼西亚' },
  { value: 'Malaysia', label: '马来西亚' },
  { value: 'Singapore', label: '新加坡' },
  { value: 'Australia', label: '澳大利亚' },
  { value: 'New Zealand', label: '新西兰' },
  { value: 'Pakistan', label: '巴基斯坦' },
  { value: 'Bangladesh', label: '孟加拉国' },
  { value: 'Saudi Arabia', label: '沙特阿拉伯' },
  { value: 'United Arab Emirates', label: '阿联酋' },
  { value: 'Israel', label: '以色列' },
  { value: 'Egypt', label: '埃及' },
  { value: 'Brazil', label: '巴西' },
  { value: 'Argentina', label: '阿根廷' },
  { value: 'Colombia', label: '哥伦比亚' },
  { value: 'Chile', label: '智利' },
  { value: 'South Africa', label: '南非' },
  { value: 'Nigeria', label: '尼日利亚' },
  { value: 'Kenya', label: '肯尼亚' },
];

function countryLabel(value: string): string {
  const found = COUNTRIES.find(c => c.value === value);
  return found ? found.label : value || '全部';
}

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

interface Lead {
  id: number;
  name: string;
  status: string;
  created_at: string;
}

interface Campaign {
  id: number;
  name: string;
  platform: string;
  status: string;
  search_keywords: string | null;
  search_region: string | null;
  search_industry: string | null;
  persona_id: number | null;
  send_limit: number;
  max_per_hour: number;
  progress_current: number;
  progress_total: number;
  created_at: string;
  updated_at: string;
  leads?: Lead[];
}

interface PersonaOption {
  id: number;
  name: string;
  company_name: string | null;
}

/* ------------------------------------------------------------------ */
/* Component                                                           */
/* ------------------------------------------------------------------ */

export default function CampaignDetail() {
  const { id } = useParams<{ id: string }>();
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  // Edit mode
  const [editing, setEditing] = useState(false);
  const [editKeywords, setEditKeywords] = useState('');
  const [editRegion, setEditRegion] = useState('');
  const [editIndustry, setEditIndustry] = useState('');
  const [editPersonaId, setEditPersonaId] = useState('');
  const [editSendLimit, setEditSendLimit] = useState(20);
  const [editMaxPerHour, setEditMaxPerHour] = useState(10);
  const [saving, setSaving] = useState(false);
  const [personas, setPersonas] = useState<PersonaOption[]>([]);

  const canEdit = campaign && (campaign.status === 'draft' || campaign.status === 'paused');

  const fetchCampaign = async () => {
    if (!id) return;
    try {
      const data = await campaignApi.get(Number(id)) as Campaign | null;
      if (data) setCampaign(data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchCampaign(); }, [id]);

  // Poll when running
  useEffect(() => {
    if (!campaign || campaign.status !== 'running') return;
    const interval = setInterval(fetchCampaign, 5000);
    return () => clearInterval(interval);
  }, [campaign?.status]);

  const startEdit = async () => {
    if (!campaign) return;
    setEditKeywords(campaign.search_keywords || '');
    setEditRegion(campaign.search_region || '');
    setEditIndustry(campaign.search_industry || '');
    setEditPersonaId(campaign.persona_id ? String(campaign.persona_id) : '');
    setEditSendLimit(campaign.send_limit);
    setEditMaxPerHour(campaign.max_per_hour || 10);
    // Load personas for dropdown
    try {
      const data = await personaApi.list();
      const list = data as PersonaOption[];
      if (Array.isArray(list)) setPersonas(list);
    } catch {}
    setEditing(true);
  };

  const saveEdit = async () => {
    if (!campaign) return;
    setSaving(true);
    try {
      await campaignApi.update(campaign.id, {
        search_keywords: editKeywords,
        search_region: editRegion,
        search_industry: editIndustry,
        persona_id: editPersonaId ? Number(editPersonaId) : null,
        send_limit: editSendLimit,
        max_per_hour: editMaxPerHour,
      });
      await fetchCampaign();
      setEditing(false);
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  };

  const handleAction = async (action: 'start' | 'pause' | 'stop') => {
    if (!id || !campaign) return;
    setActionLoading(true);
    try {
      if (action === 'start') await campaignApi.start(Number(id));
      else if (action === 'pause') await campaignApi.pause(Number(id));
      else await campaignApi.stop(Number(id));
      await fetchCampaign();
    } catch {} finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center py-20 text-sm text-[#86868b]">加载中...</div>;
  }

  if (!campaign) {
    return (
      <div className="py-20 text-center text-sm text-[#86868b]">
        未找到该任务
        <br />
        <Link to="/campaigns" className="mt-4 inline-block text-[#0071e3] hover:underline">返回任务列表</Link>
      </div>
    );
  }

  const progress = campaign.send_limit > 0
    ? Math.round((campaign.progress_current / campaign.send_limit) * 100)
    : 0;

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <Link to="/campaigns" className="mb-4 inline-flex items-center gap-1.5 text-sm text-[#86868b] hover:text-[#1d1d1f]">
          <ArrowLeft className="h-4 w-4" />
          返回任务列表
        </Link>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-[#1d1d1f]">
              {campaign.name || campaign.search_keywords || '未命名任务'}
            </h1>
            <div className="mt-2 flex items-center gap-3">
              <StatusBadge status={campaign.status} />
              <span className="text-sm text-[#86868b] capitalize">{campaign.platform}</span>
              <span className="text-sm text-[#86868b]">创建于 {campaign.created_at}</span>
            </div>
          </div>
          <div className="flex gap-2">
            {canEdit && !editing && (
              <button
                onClick={startEdit}
                className="inline-flex items-center gap-2 rounded-full border border-[#e5e5e7] bg-white px-4 py-2 text-sm font-medium text-[#1d1d1f] hover:bg-[#f5f5f7]"
              >
                <Pencil className="h-4 w-4" />
                编辑
              </button>
            )}
            {campaign.status === 'running' && (
              <>
                <button onClick={() => handleAction('pause')} disabled={actionLoading}
                  className="inline-flex items-center gap-2 rounded-full border border-[#e5e5e7] bg-white px-4 py-2 text-sm font-medium text-[#1d1d1f] hover:bg-[#f5f5f7] disabled:opacity-50">
                  <Pause className="h-4 w-4" /> 暂停
                </button>
                <button onClick={() => handleAction('stop')} disabled={actionLoading}
                  className="inline-flex items-center gap-2 rounded-full border border-red-200 bg-white px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50">
                  <StopCircle className="h-4 w-4" /> 停止
                </button>
              </>
            )}
            {(campaign.status === 'paused' || campaign.status === 'draft') && (
              <button onClick={() => handleAction('start')} disabled={actionLoading}
                className="inline-flex items-center gap-2 rounded-full bg-[#0071e3] px-5 py-2 text-sm font-medium text-white hover:bg-[#0077ed] disabled:opacity-50">
                <Play className="h-4 w-4" /> 启动
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Campaign Info — view or edit */}
      {editing ? (
        <div className="mb-6 rounded-2xl bg-white p-6 border border-[#0071e3]/30 shadow-sm space-y-4">
          <h2 className="text-base font-semibold text-[#1d1d1f]">编辑任务参数</h2>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">关键词</label>
            <input type="text" value={editKeywords} onChange={e => setEditKeywords(e.target.value)}
              className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm outline-none focus:border-[#0071e3] focus:bg-white" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">国家/地区</label>
              <select value={editRegion} onChange={e => setEditRegion(e.target.value)}
                className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm outline-none focus:border-[#0071e3] focus:bg-white">
                {COUNTRIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">行业</label>
              <input type="text" value={editIndustry} onChange={e => setEditIndustry(e.target.value)}
                placeholder="例如：电子商务"
                className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm outline-none focus:border-[#0071e3] focus:bg-white" />
            </div>
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">人设</label>
            <select value={editPersonaId} onChange={e => setEditPersonaId(e.target.value)}
              className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm outline-none focus:border-[#0071e3] focus:bg-white">
              <option value="">无</option>
              {personas.map(p => (
                <option key={p.id} value={p.id}>{p.name}{p.company_name ? ` - ${p.company_name}` : ''}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">每小时最多打招呼</label>
              <div className="flex items-center gap-2">
                <input type="number" min={1} max={60} value={editMaxPerHour} onChange={e => setEditMaxPerHour(Number(e.target.value))}
                  className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm outline-none focus:border-[#0071e3] focus:bg-white" />
              </div>
              <p className="mt-1 text-xs text-[#86868b]">消息随机分散在每小时内发送</p>
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">总发送上限</label>
              <input type="number" min={1} max={500} value={editSendLimit} onChange={e => setEditSendLimit(Number(e.target.value))}
                className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm outline-none focus:border-[#0071e3] focus:bg-white" />
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button onClick={() => setEditing(false)}
              className="inline-flex items-center gap-1.5 rounded-full border border-[#e5e5e7] px-5 py-2 text-sm font-medium text-[#1d1d1f] hover:bg-[#f5f5f7]">
              <X className="h-4 w-4" /> 取消
            </button>
            <button onClick={saveEdit} disabled={saving}
              className="inline-flex items-center gap-1.5 rounded-full bg-[#0071e3] px-5 py-2 text-sm font-medium text-white hover:bg-[#0077ed] disabled:opacity-50">
              <Save className="h-4 w-4" /> {saving ? '保存中...' : '保存'}
            </button>
          </div>
        </div>
      ) : (
        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-5">
          <div className="rounded-2xl bg-white p-4 border border-[#e5e5e7]/60 shadow-sm">
            <p className="text-xs text-[#86868b]">平台</p>
            <p className="mt-1 text-sm font-medium text-[#1d1d1f] capitalize">{campaign.platform}</p>
          </div>
          <div className="rounded-2xl bg-white p-4 border border-[#e5e5e7]/60 shadow-sm">
            <p className="text-xs text-[#86868b]">关键词</p>
            <p className="mt-1 text-sm font-medium text-[#1d1d1f]">{campaign.search_keywords || '-'}</p>
          </div>
          <div className="rounded-2xl bg-white p-4 border border-[#e5e5e7]/60 shadow-sm">
            <p className="text-xs text-[#86868b]">国家/地区</p>
            <p className="mt-1 text-sm font-medium text-[#1d1d1f]">{countryLabel(campaign.search_region || '')}</p>
          </div>
          <div className="rounded-2xl bg-white p-4 border border-[#e5e5e7]/60 shadow-sm">
            <p className="text-xs text-[#86868b]">行业</p>
            <p className="mt-1 text-sm font-medium text-[#1d1d1f]">{campaign.search_industry || '全部'}</p>
          </div>
          <div className="rounded-2xl bg-white p-4 border border-[#e5e5e7]/60 shadow-sm">
            <p className="text-xs text-[#86868b]">发送频率</p>
            <p className="mt-1 text-sm font-medium text-[#1d1d1f]">{campaign.max_per_hour || 10} 人/小时</p>
          </div>
        </div>
      )}

      {/* Progress */}
      <div className="mb-6 rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <span className="text-sm font-medium text-[#1d1d1f]">发送进度</span>
          <span className="text-sm text-[#86868b]">{campaign.progress_current} / {campaign.send_limit}</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-[#f0f0f2]">
          <div className="h-full rounded-full bg-[#0071e3] transition-all" style={{ width: `${progress}%` }} />
        </div>
        <p className="mt-2 text-xs text-[#86868b]">{progress}% 完成</p>
      </div>

      {/* Leads table */}
      <div className="rounded-2xl bg-white border border-[#e5e5e7]/60 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-[#e5e5e7]/60">
          <h2 className="text-base font-semibold text-[#1d1d1f]">
            线索列表 ({campaign.leads?.length || 0})
          </h2>
        </div>
        {campaign.leads && campaign.leads.length > 0 ? (
          <table className="w-full">
            <thead>
              <tr className="border-b border-[#e5e5e7]/60">
                <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">姓名</th>
                <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">状态</th>
                <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">时间</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#e5e5e7]/40">
              {campaign.leads.map(lead => (
                <tr key={lead.id} className="hover:bg-[#f5f5f7]/50">
                  <td className="px-6 py-3.5 text-sm font-medium text-[#1d1d1f]">{lead.name || '未知'}</td>
                  <td className="px-6 py-3.5"><StatusBadge status={lead.status} /></td>
                  <td className="px-6 py-3.5 text-sm text-[#86868b]">{lead.created_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="py-12 text-center text-sm text-[#86868b]">暂无线索数据</div>
        )}
      </div>
    </div>
  );
}
