'use client';

import { Fragment, useEffect, useState } from 'react';
import { Search, ChevronDown, ChevronUp, Download, CheckSquare } from 'lucide-react';
import StatusBadge from '@/components/StatusBadge';
import { leadApi } from '@/lib/api';
import api from '@/lib/api';

const BATCH_STATUS_OPTIONS = [
  { value: 'converted', label: '标记为已转化' },
  { value: 'rejected', label: '标记为已拒绝' },
  { value: 'found', label: '重置为已发现' },
];

interface Lead {
  id: number;
  name: string | null;
  platform: string;
  status: string;
  campaign_id: number;
  bio: string | null;
  profile_url: string | null;
  created_at: string;
}

interface LeadDetail extends Lead {
  messages?: { id: number; direction: string; content: string; ai_generated: boolean; created_at: string }[];
}

const statusOptions = [
  { value: '', label: '全部状态' },
  { value: 'found', label: '已发现' },
  { value: 'analyzing', label: '分析中' },
  { value: 'messaged', label: '已发送' },
  { value: 'replied', label: '已回复' },
  { value: 'converted', label: '已转化' },
  { value: 'failed', label: '失败' },
];

const platformOptions = [
  { value: '', label: '全部平台' },
  { value: 'facebook', label: 'Facebook' },
];

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [platformFilter, setPlatformFilter] = useState('');
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [expandedDetail, setExpandedDetail] = useState<LeadDetail | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [batchLoading, setBatchLoading] = useState(false);

  useEffect(() => {
    const params: Record<string, string> = {};
    if (search) params.search = search;
    if (statusFilter) params.status = statusFilter;
    if (platformFilter) params.platform = platformFilter;

    leadApi.list(params)
      .then(res => setLeads(res.data))
      .catch(err => console.error('Failed to load leads:', err))
      .finally(() => setLoading(false));
  }, [search, statusFilter, platformFilter]);

  const toggleSelect = (id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === leads.length) setSelectedIds(new Set());
    else setSelectedIds(new Set(leads.map(l => l.id)));
  };

  const handleBatchStatus = async (newStatus: string) => {
    if (selectedIds.size === 0) return;
    setBatchLoading(true);
    try {
      await Promise.all(
        Array.from(selectedIds).map(id =>
          api.patch(`/api/leads/${id}/status?new_status=${newStatus}`)
        )
      );
      // Refresh list
      setLeads(prev => prev.map(l =>
        selectedIds.has(l.id) ? { ...l, status: newStatus } : l
      ));
      setSelectedIds(new Set());
    } catch { /* ignore */ }
    setBatchLoading(false);
  };

  const handleExpand = async (leadId: number) => {
    if (expandedId === leadId) {
      setExpandedId(null);
      setExpandedDetail(null);
      return;
    }
    setExpandedId(leadId);
    try {
      const res = await leadApi.get(String(leadId));
      setExpandedDetail(res.data);
    } catch (err) {
      console.error('Failed to load lead detail:', err);
    }
  };

  return (
    <div>
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-[#1d1d1f]">线索数据库</h1>
          <p className="mt-1 text-sm text-[#86868b]">查看和管理所有获取的线索</p>
        </div>
        <button
          onClick={async () => {
            try {
              const params = new URLSearchParams();
              if (statusFilter) params.set('status', statusFilter);
              const res = await api.get(`/api/leads/export/csv?${params}`, { responseType: 'blob' });
              const url = window.URL.createObjectURL(new Blob([res.data]));
              const a = document.createElement('a');
              a.href = url;
              a.download = `leads_${new Date().toISOString().slice(0, 10)}.csv`;
              a.click();
              window.URL.revokeObjectURL(url);
            } catch { alert('导出失败，请检查后端服务'); }
          }}
          className="inline-flex items-center gap-2 rounded-full border border-[#e5e5e7] bg-white px-5 py-2.5 text-sm font-medium text-[#1d1d1f] transition-colors hover:bg-[#f5f5f7]"
        >
          <Download className="h-4 w-4" />
          导出 CSV
        </button>
      </div>

      {/* Filters */}
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#86868b]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索姓名..."
            className="w-full rounded-xl border border-[#e5e5e7] bg-white py-2.5 pl-10 pr-4 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none transition-colors focus:border-[#0071e3]"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-xl border border-[#e5e5e7] bg-white px-4 py-2.5 text-sm text-[#1d1d1f] outline-none transition-colors focus:border-[#0071e3]"
        >
          {statusOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <select
          value={platformFilter}
          onChange={(e) => setPlatformFilter(e.target.value)}
          className="rounded-xl border border-[#e5e5e7] bg-white px-4 py-2.5 text-sm text-[#1d1d1f] outline-none transition-colors focus:border-[#0071e3]"
        >
          {platformOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      {/* Batch Action Bar */}
      {selectedIds.size > 0 && (
        <div className="mb-4 flex items-center gap-3 rounded-xl bg-blue-50 border border-blue-200 px-4 py-2.5">
          <CheckSquare className="h-4 w-4 text-blue-600" />
          <span className="text-sm font-medium text-blue-800">已选 {selectedIds.size} 条</span>
          {BATCH_STATUS_OPTIONS.map(opt => (
            <button
              key={opt.value}
              onClick={() => handleBatchStatus(opt.value)}
              disabled={batchLoading}
              className="rounded-full border border-blue-200 bg-white px-3 py-1 text-xs font-medium text-blue-700 hover:bg-blue-100 disabled:opacity-50"
            >
              {opt.label}
            </button>
          ))}
          <button onClick={() => setSelectedIds(new Set())} className="ml-auto text-xs text-blue-600 hover:underline">取消选择</button>
        </div>
      )}

      {/* Table */}
      <div className="rounded-2xl bg-white border border-[#e5e5e7]/60 shadow-sm overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[#e5e5e7]/60">
              <th className="w-10 px-4 py-3.5">
                <input type="checkbox" checked={leads.length > 0 && selectedIds.size === leads.length} onChange={toggleSelectAll}
                  className="h-4 w-4 rounded border-[#e5e5e7] text-[#0071e3] focus:ring-[#0071e3]" />
              </th>
              <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">姓名</th>
              <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">平台</th>
              <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">状态</th>
              <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">简介</th>
              <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">日期</th>
              <th className="w-10 px-6 py-3.5" />
            </tr>
          </thead>
          <tbody className="divide-y divide-[#e5e5e7]/40">
            {loading && (
              <tr>
                <td colSpan={7} className="px-6 py-12 text-center text-sm text-[#86868b]">加载中...</td>
              </tr>
            )}
            {!loading && leads.length === 0 && (
              <tr>
                <td colSpan={7} className="px-6 py-12 text-center text-sm text-[#86868b]">暂无线索数据</td>
              </tr>
            )}
            {leads.map((lead) => (
              <Fragment key={lead.id}>
                <tr
                  onClick={() => handleExpand(lead.id)}
                  className="cursor-pointer transition-colors hover:bg-[#f5f5f7]/50"
                >
                  <td className="w-10 px-4 py-3.5" onClick={(e) => e.stopPropagation()}>
                    <input type="checkbox" checked={selectedIds.has(lead.id)} onChange={() => toggleSelect(lead.id)}
                      className="h-4 w-4 rounded border-[#e5e5e7] text-[#0071e3] focus:ring-[#0071e3]" />
                  </td>
                  <td className="px-6 py-3.5 text-sm font-medium text-[#1d1d1f]">{lead.name || '未知'}</td>
                  <td className="px-6 py-3.5 text-sm text-[#86868b] capitalize">{lead.platform}</td>
                  <td className="px-6 py-3.5"><StatusBadge status={lead.status} /></td>
                  <td className="max-w-[200px] truncate px-6 py-3.5 text-sm text-[#86868b]">{lead.bio || '-'}</td>
                  <td className="px-6 py-3.5 text-sm text-[#86868b]">{new Date(lead.created_at).toLocaleDateString('zh-CN')}</td>
                  <td className="px-6 py-3.5">
                    {expandedId === lead.id ? (
                      <ChevronUp className="h-4 w-4 text-[#86868b]" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-[#86868b]" />
                    )}
                  </td>
                </tr>
                {expandedId === lead.id && expandedDetail && (
                  <tr>
                    <td colSpan={7} className="bg-[#fafafa] px-6 py-5">
                      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                        {/* Profile */}
                        <div>
                          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-[#86868b]">个人资料</h4>
                          <p className="text-sm text-[#1d1d1f]">{expandedDetail.name || '未知'}</p>
                          {expandedDetail.bio && <p className="mt-1 text-sm text-[#86868b]">{expandedDetail.bio}</p>}
                          {expandedDetail.profile_url && (
                            <a href={expandedDetail.profile_url} target="_blank" rel="noopener noreferrer" className="mt-2 inline-block text-xs text-[#0071e3] hover:underline">
                              查看主页
                            </a>
                          )}
                        </div>
                        {/* Message History */}
                        <div>
                          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-[#86868b]">消息记录</h4>
                          {expandedDetail.messages && expandedDetail.messages.length > 0 ? (
                            <div className="space-y-2">
                              {expandedDetail.messages.map((msg) => (
                                <div key={msg.id} className={`rounded-xl p-3 text-sm ${msg.direction === 'outbound' ? 'bg-blue-50 text-blue-900' : 'bg-white border border-[#e5e5e7] text-[#1d1d1f]'}`}>
                                  <div className="mb-1 flex items-center justify-between">
                                    <span className="text-xs font-medium">{msg.direction === 'outbound' ? 'AI' : '对方'}</span>
                                    <span className="text-xs text-[#86868b]">{new Date(msg.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}</span>
                                  </div>
                                  <p>{msg.content}</p>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className="text-sm text-[#86868b]">暂无消息记录</p>
                          )}
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
