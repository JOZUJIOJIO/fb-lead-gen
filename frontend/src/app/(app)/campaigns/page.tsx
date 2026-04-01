'use client';

import { useEffect, useState, useMemo } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Plus, Search, ArrowUpDown, Copy, Trash2 } from 'lucide-react';
import StatusBadge from '@/components/StatusBadge';
import { campaignApi } from '@/lib/api';

interface Campaign {
  id: number;
  name: string | null;
  platform: string;
  status: string;
  search_keywords: string | null;
  progress_current: number;
  send_limit: number;
  max_per_hour: number;
  created_at: string;
  updated_at: string;
}

const STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'draft', label: '草稿' },
  { value: 'running', label: '运行中' },
  { value: 'paused', label: '已暂停' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '失败' },
];

type SortKey = 'created_at' | 'status' | 'progress';

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('created_at');
  const [sortAsc, setSortAsc] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [deleting, setDeleting] = useState(false);
  const router = useRouter();

  const refreshCampaigns = () => {
    campaignApi.list()
      .then(res => setCampaigns(res.data))
      .catch(err => console.error('Failed to load campaigns:', err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    refreshCampaigns();
  }, []);

  const handleDuplicate = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    try {
      await campaignApi.duplicate(id);
      refreshCampaigns();
    } catch (err) {
      console.error('Failed to duplicate campaign:', err);
    }
  };

  const handleDelete = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    if (!confirm('确定删除该任务？关联的线索和消息也会被删除。')) return;
    try {
      await campaignApi.delete(String(id));
      setSelected(prev => { const s = new Set(prev); s.delete(id); return s; });
      refreshCampaigns();
    } catch (err) {
      console.error('Failed to delete campaign:', err);
    }
  };

  const handleBatchDelete = async () => {
    if (selected.size === 0) return;
    if (!confirm(`确定删除选中的 ${selected.size} 个任务？关联的线索和消息也会被删除。`)) return;
    setDeleting(true);
    try {
      await Promise.all(Array.from(selected).map(id => campaignApi.delete(String(id))));
      setSelected(new Set());
      refreshCampaigns();
    } catch (err) {
      console.error('Failed to batch delete:', err);
    } finally {
      setDeleting(false);
    }
  };

  const toggleSelect = (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    setSelected(prev => {
      const s = new Set(prev);
      if (s.has(id)) s.delete(id); else s.add(id);
      return s;
    });
  };

  const toggleSelectAll = () => {
    if (selected.size === filtered.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(filtered.map(c => c.id)));
    }
  };

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(false); }
  };

  const filtered = useMemo(() => {
    let list = [...campaigns];
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(c =>
        (c.name || '').toLowerCase().includes(q) ||
        (c.search_keywords || '').toLowerCase().includes(q)
      );
    }
    if (statusFilter) {
      list = list.filter(c => c.status === statusFilter);
    }
    list.sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'created_at') {
        cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      } else if (sortKey === 'status') {
        cmp = a.status.localeCompare(b.status);
      } else if (sortKey === 'progress') {
        const pa = a.send_limit > 0 ? a.progress_current / a.send_limit : 0;
        const pb = b.send_limit > 0 ? b.progress_current / b.send_limit : 0;
        cmp = pa - pb;
      }
      return sortAsc ? cmp : -cmp;
    });
    return list;
  }, [campaigns, search, statusFilter, sortKey, sortAsc]);

  const SortBtn = ({ k, label }: { k: SortKey; label: string }) => (
    <button onClick={() => toggleSort(k)} className="inline-flex items-center gap-1 text-xs font-medium uppercase tracking-wider text-[#86868b] hover:text-[#1d1d1f]">
      {label}
      <ArrowUpDown className={`h-3 w-3 ${sortKey === k ? 'text-[#0071e3]' : ''}`} />
    </button>
  );

  return (
    <div>
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-[#1d1d1f]">任务管理</h1>
          <p className="mt-1 text-sm text-[#86868b]">管理和监控获客任务</p>
        </div>
        <Link
          href="/campaigns/new"
          className="inline-flex items-center gap-2 rounded-full bg-[#0071e3] px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#0077ed]"
        >
          <Plus className="h-4 w-4" />
          新建任务
        </Link>
      </div>

      {/* Filters */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#86868b]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索任务名称或关键词..."
            className="w-full rounded-xl border border-[#e5e5e7] bg-white py-2.5 pl-10 pr-4 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none focus:border-[#0071e3]"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-xl border border-[#e5e5e7] bg-white px-4 py-2.5 text-sm text-[#1d1d1f] outline-none focus:border-[#0071e3]"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      {/* Batch actions bar */}
      {selected.size > 0 && (
        <div className="mb-4 flex items-center gap-3 rounded-xl bg-[#f5f5f7] px-4 py-2.5 border border-[#e5e5e7]/60">
          <span className="text-sm text-[#1d1d1f]">已选中 <strong>{selected.size}</strong> 个任务</span>
          <button
            onClick={handleBatchDelete}
            disabled={deleting}
            className="inline-flex items-center gap-1.5 rounded-lg bg-red-500 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-red-600 disabled:opacity-50"
          >
            <Trash2 className="h-3.5 w-3.5" />
            {deleting ? '删除中...' : '批量删除'}
          </button>
          <button
            onClick={() => setSelected(new Set())}
            className="text-xs text-[#86868b] hover:text-[#1d1d1f]"
          >
            取消选择
          </button>
        </div>
      )}

      <div className="rounded-2xl bg-white border border-[#e5e5e7]/60 shadow-sm overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[#e5e5e7]/60">
              <th className="w-10 px-3 py-3.5">
                <input
                  type="checkbox"
                  checked={filtered.length > 0 && selected.size === filtered.length}
                  onChange={toggleSelectAll}
                  className="h-4 w-4 rounded border-[#e5e5e7] text-[#0071e3] focus:ring-[#0071e3]"
                />
              </th>
              <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">任务名称</th>
              <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">平台</th>
              <th className="px-6 py-3.5 text-left"><SortBtn k="status" label="状态" /></th>
              <th className="px-6 py-3.5 text-left"><SortBtn k="progress" label="进度" /></th>
              <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">频率</th>
              <th className="px-6 py-3.5 text-left"><SortBtn k="created_at" label="创建时间" /></th>
              <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#e5e5e7]/40">
            {loading && (
              <tr><td colSpan={8} className="px-6 py-12 text-center text-sm text-[#86868b]">加载中...</td></tr>
            )}
            {!loading && filtered.length === 0 && (
              <tr><td colSpan={8} className="px-6 py-12 text-center text-sm text-[#86868b]">
                {campaigns.length === 0 ? '暂无任务，点击「新建任务」开始' : '没有匹配的任务'}
              </td></tr>
            )}
            {filtered.map((campaign) => (
              <tr
                key={campaign.id}
                onClick={() => router.push(`/campaigns/${campaign.id}`)}
                className={`cursor-pointer transition-colors hover:bg-[#f5f5f7]/50 ${selected.has(campaign.id) ? 'bg-blue-50/50' : ''}`}
              >
                <td className="w-10 px-3 py-4" onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={selected.has(campaign.id)}
                    onChange={(e) => toggleSelect(e as unknown as React.MouseEvent, campaign.id)}
                    className="h-4 w-4 rounded border-[#e5e5e7] text-[#0071e3] focus:ring-[#0071e3]"
                  />
                </td>
                <td className="px-6 py-4">
                  <Link href={`/campaigns/${campaign.id}`} className="text-sm font-medium text-[#1d1d1f] hover:text-[#0071e3]">
                    {campaign.name || campaign.search_keywords || '未命名任务'}
                  </Link>
                </td>
                <td className="px-6 py-4">
                  <span className="text-sm text-[#86868b] capitalize">{campaign.platform}</span>
                </td>
                <td className="px-6 py-4"><StatusBadge status={campaign.status} /></td>
                <td className="px-6 py-4">
                  <div className="flex items-center gap-3">
                    <div className="h-1.5 w-24 overflow-hidden rounded-full bg-[#f0f0f2]">
                      <div
                        className="h-full rounded-full bg-[#0071e3] transition-all"
                        style={{ width: `${campaign.send_limit > 0 ? (campaign.progress_current / campaign.send_limit) * 100 : 0}%` }}
                      />
                    </div>
                    <span className="text-xs text-[#86868b]">{campaign.progress_current}/{campaign.send_limit}</span>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <span className="text-xs text-[#86868b]">{campaign.max_per_hour || 10}/小时</span>
                </td>
                <td className="px-6 py-4">
                  <span className="text-sm text-[#86868b]">{new Date(campaign.created_at).toLocaleDateString('zh-CN')}</span>
                </td>
                <td className="px-6 py-4">
                  <div className="flex items-center gap-1">
                    <button
                      onClick={(e) => handleDuplicate(e, campaign.id)}
                      title="复制任务"
                      className="rounded-lg p-1.5 text-[#86868b] transition-colors hover:bg-[#f5f5f7] hover:text-[#1d1d1f]"
                    >
                      <Copy className="h-4 w-4" />
                    </button>
                    <button
                      onClick={(e) => handleDelete(e, campaign.id)}
                      title="删除任务"
                      className="rounded-lg p-1.5 text-[#86868b] transition-colors hover:bg-red-50 hover:text-red-500"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
