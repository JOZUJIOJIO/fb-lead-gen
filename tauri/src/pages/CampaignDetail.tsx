import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Play, Pause, StopCircle } from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import { campaignApi } from '../lib/ipc';

interface Lead {
  id: number;
  name: string;
  status: string;
  date: string;
}

interface Campaign {
  id: number;
  name: string;
  platform: string;
  status: string;
  sent: number;
  limit: number;
  created_at: string;
  leads?: Lead[];
}

export default function CampaignDetail() {
  const { id } = useParams<{ id: string }>();
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    if (!id) return;
    campaignApi
      .get(Number(id))
      .then((data: unknown) => {
        setCampaign(data as Campaign);
      })
      .catch(() => {
        // Fallback placeholder
        setCampaign({
          id: Number(id),
          name: '加载中...',
          platform: 'Facebook',
          status: 'draft',
          sent: 0,
          limit: 100,
          created_at: '—',
          leads: [],
        });
      })
      .finally(() => setLoading(false));
  }, [id]);

  const handleAction = async (action: 'start' | 'pause' | 'stop') => {
    if (!id || !campaign) return;
    setActionLoading(true);
    try {
      if (action === 'start') await campaignApi.start(Number(id));
      else if (action === 'pause') await campaignApi.pause(Number(id));
      else await campaignApi.stop(Number(id));
      // Refresh
      const updated = await campaignApi.get(Number(id));
      setCampaign(updated as Campaign);
    } catch {
      // Ignore if sidecar offline
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-sm text-[#86868b]">
        加载中...
      </div>
    );
  }

  if (!campaign) {
    return (
      <div className="py-20 text-center text-sm text-[#86868b]">
        未找到该任务
      </div>
    );
  }

  const progress = Math.round((campaign.sent / campaign.limit) * 100);

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <Link
          to="/campaigns"
          className="mb-4 inline-flex items-center gap-1.5 text-sm text-[#86868b] hover:text-[#1d1d1f]"
        >
          <ArrowLeft className="h-4 w-4" />
          返回任务列表
        </Link>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-[#1d1d1f]">
              {campaign.name}
            </h1>
            <div className="mt-2 flex items-center gap-3">
              <StatusBadge status={campaign.status} />
              <span className="text-sm text-[#86868b]">{campaign.platform}</span>
              <span className="text-sm text-[#86868b]">
                创建于 {campaign.created_at}
              </span>
            </div>
          </div>
          <div className="flex gap-2">
            {campaign.status === 'running' && (
              <>
                <button
                  onClick={() => handleAction('pause')}
                  disabled={actionLoading}
                  className="inline-flex items-center gap-2 rounded-full border border-[#e5e5e7] bg-white px-4 py-2 text-sm font-medium text-[#1d1d1f] transition-colors hover:bg-[#f5f5f7] disabled:opacity-50"
                >
                  <Pause className="h-4 w-4" />
                  暂停
                </button>
                <button
                  onClick={() => handleAction('stop')}
                  disabled={actionLoading}
                  className="inline-flex items-center gap-2 rounded-full border border-red-200 bg-white px-4 py-2 text-sm font-medium text-red-600 transition-colors hover:bg-red-50 disabled:opacity-50"
                >
                  <StopCircle className="h-4 w-4" />
                  停止
                </button>
              </>
            )}
            {(campaign.status === 'paused' || campaign.status === 'draft') && (
              <button
                onClick={() => handleAction('start')}
                disabled={actionLoading}
                className="inline-flex items-center gap-2 rounded-full bg-[#0071e3] px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-[#0077ed] disabled:opacity-50"
              >
                <Play className="h-4 w-4" />
                启动
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Progress card */}
      <div className="mb-6 rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <span className="text-sm font-medium text-[#1d1d1f]">发送进度</span>
          <span className="text-sm text-[#86868b]">
            {campaign.sent} / {campaign.limit}
          </span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-[#f0f0f2]">
          <div
            className="h-full rounded-full bg-[#0071e3] transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
        <p className="mt-2 text-xs text-[#86868b]">{progress}% 完成</p>
      </div>

      {/* Leads table */}
      <div className="rounded-2xl bg-white border border-[#e5e5e7]/60 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-[#e5e5e7]/60">
          <h2 className="text-base font-semibold text-[#1d1d1f]">线索列表</h2>
        </div>
        {campaign.leads && campaign.leads.length > 0 ? (
          <table className="w-full">
            <thead>
              <tr className="border-b border-[#e5e5e7]/60">
                <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">
                  姓名
                </th>
                <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">
                  状态
                </th>
                <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">
                  日期
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#e5e5e7]/40">
              {campaign.leads.map((lead) => (
                <tr key={lead.id} className="hover:bg-[#f5f5f7]/50">
                  <td className="px-6 py-3.5 text-sm font-medium text-[#1d1d1f]">
                    {lead.name}
                  </td>
                  <td className="px-6 py-3.5">
                    <StatusBadge status={lead.status} />
                  </td>
                  <td className="px-6 py-3.5 text-sm text-[#86868b]">
                    {lead.date}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="py-12 text-center text-sm text-[#86868b]">
            暂无线索数据
          </div>
        )}
      </div>
    </div>
  );
}
