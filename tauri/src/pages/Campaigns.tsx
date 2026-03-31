import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Search } from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import { campaignApi } from '../lib/ipc';

interface Campaign {
  id: number;
  name: string;
  platform: string;
  status: string;
  send_limit: number;
  progress_current: number;
  progress_total: number;
  created_at: string;
}

export default function Campaigns() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    campaignApi
      .list()
      .then((data: unknown) => {
        const list = data as Campaign[];
        if (Array.isArray(list)) setCampaigns(list);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-[#1d1d1f]">
            任务管理
          </h1>
          <p className="mt-1 text-sm text-[#86868b]">管理和监控获客任务</p>
        </div>
        <Link
          to="/campaigns/new"
          className="inline-flex items-center gap-2 rounded-full bg-[#0071e3] px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#0077ed]"
        >
          <Plus className="h-4 w-4" />
          新建任务
        </Link>
      </div>

      {loading && (
        <div className="py-12 text-center text-sm text-[#86868b]">加载中...</div>
      )}

      {!loading && campaigns.length === 0 && (
        <div className="rounded-2xl bg-white p-12 border border-[#e5e5e7]/60 shadow-sm text-center">
          <Search className="mx-auto h-12 w-12 text-[#86868b]/40" />
          <h2 className="mt-4 text-lg font-semibold text-[#1d1d1f]">创建你的第一个获客任务</h2>
          <p className="mt-2 text-sm text-[#86868b]">配置搜索条件和人设，开始自动获客</p>
          <Link
            to="/campaigns/new"
            className="mt-6 inline-flex items-center gap-2 rounded-full bg-[#0071e3] px-5 py-2.5 text-sm font-medium text-white hover:bg-[#0077ed]"
          >
            <Plus className="h-4 w-4" />
            新建任务
          </Link>
        </div>
      )}

      {campaigns.length > 0 && (
        <div className="rounded-2xl bg-white border border-[#e5e5e7]/60 shadow-sm overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[#e5e5e7]/60">
                <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">任务名称</th>
                <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">平台</th>
                <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">状态</th>
                <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">进度</th>
                <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">创建时间</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#e5e5e7]/40">
              {campaigns.map(campaign => (
                <tr key={campaign.id} className="cursor-pointer transition-colors hover:bg-[#f5f5f7]/50">
                  <td className="px-6 py-4">
                    <Link to={`/campaigns/${campaign.id}`} className="text-sm font-medium text-[#1d1d1f] hover:text-[#0071e3]">
                      {campaign.name || '未命名任务'}
                    </Link>
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-sm text-[#86868b] capitalize">{campaign.platform}</span>
                  </td>
                  <td className="px-6 py-4">
                    <StatusBadge status={campaign.status} />
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-[#f0f0f2]">
                        <div
                          className="h-full rounded-full bg-[#0071e3] transition-all"
                          style={{ width: `${campaign.send_limit > 0 ? (campaign.progress_current / campaign.send_limit) * 100 : 0}%` }}
                        />
                      </div>
                      <span className="text-xs text-[#86868b]">
                        {campaign.progress_current}/{campaign.send_limit}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-sm text-[#86868b]">{campaign.created_at}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
