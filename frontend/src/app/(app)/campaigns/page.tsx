'use client';

import { useEffect, useState, useMemo } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Plus, Search, ArrowUpDown } from 'lucide-react';
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
  const router = useRouter();

  useEffect(() => {
    campaignApi.list()
      .then(res => setCampaigns(res.data))
      .catch(err => console.error('Failed to load campaigns:', err))
      .finally(() => setLoading(false));
  }, []);

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

      <div className="rounded-2xl bg-white border border-[#e5e5e7]/60 shadow-sm overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[#e5e5e7]/60">
              <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">任务名称</th>
              <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">平台</th>
              <th className="px-6 py-3.5 text-left"><SortBtn k="status" label="状态" /></th>
              <th className="px-6 py-3.5 text-left"><SortBtn k="progress" label="进度" /></th>
              <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">频率</th>
              <th className="px-6 py-3.5 text-left"><SortBtn k="created_at" label="创建时间" /></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#e5e5e7]/40">
            {loading && (
              <tr><td colSpan={6} className="px-6 py-12 text-center text-sm text-[#86868b]">加载中...</td></tr>
            )}
            {!loading && filtered.length === 0 && (
              <tr><td colSpan={6} className="px-6 py-12 text-center text-sm text-[#86868b]">
                {campaigns.length === 0 ? '暂无任务，点击「新建任务」开始' : '没有匹配的任务'}
              </td></tr>
            )}
            {filtered.map((campaign) => (
              <tr
                key={campaign.id}
                onClick={() => router.push(`/campaigns/${campaign.id}`)}
                className="cursor-pointer transition-colors hover:bg-[#f5f5f7]/50"
              >
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
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
