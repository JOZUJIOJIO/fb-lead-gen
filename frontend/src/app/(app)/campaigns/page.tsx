'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Plus } from 'lucide-react';
import StatusBadge from '@/components/StatusBadge';

interface Campaign {
  id: string;
  name: string;
  platform: string;
  status: string;
  sent: number;
  limit: number;
  created_at: string;
}

const mockCampaigns: Campaign[] = [
  { id: '1', name: 'Facebook 外贸客户开发', platform: 'Facebook', status: 'running', sent: 145, limit: 200, created_at: '2024-03-15' },
  { id: '2', name: 'SaaS 决策者触达', platform: 'Facebook', status: 'paused', sent: 87, limit: 150, created_at: '2024-03-14' },
  { id: '3', name: '跨境电商卖家联系', platform: 'Facebook', status: 'completed', sent: 200, limit: 200, created_at: '2024-03-10' },
  { id: '4', name: '新能源行业推广', platform: 'Facebook', status: 'draft', sent: 0, limit: 100, created_at: '2024-03-16' },
];

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>(mockCampaigns);

  useEffect(() => {
    // TODO: Fetch real data
    // campaignApi.list().then(res => setCampaigns(res.data));
  }, []);

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
            {campaigns.map((campaign) => (
              <tr
                key={campaign.id}
                className="cursor-pointer transition-colors hover:bg-[#f5f5f7]/50"
              >
                <td className="px-6 py-4">
                  <Link href={`/campaigns/${campaign.id}`} className="text-sm font-medium text-[#1d1d1f] hover:text-[#0071e3]">
                    {campaign.name}
                  </Link>
                </td>
                <td className="px-6 py-4">
                  <span className="text-sm text-[#86868b]">{campaign.platform}</span>
                </td>
                <td className="px-6 py-4">
                  <StatusBadge status={campaign.status} />
                </td>
                <td className="px-6 py-4">
                  <div className="flex items-center gap-3">
                    <div className="h-1.5 w-24 overflow-hidden rounded-full bg-[#f0f0f2]">
                      <div
                        className="h-full rounded-full bg-[#0071e3] transition-all"
                        style={{ width: `${(campaign.sent / campaign.limit) * 100}%` }}
                      />
                    </div>
                    <span className="text-xs text-[#86868b]">
                      {campaign.sent}/{campaign.limit}
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
    </div>
  );
}
