import { useEffect, useState } from 'react';
import { Search, ChevronDown, ChevronUp } from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import { leadApi } from '../lib/ipc';

interface Message {
  role: string;
  content: string;
  timestamp: string;
}

interface Lead {
  id: number;
  name: string;
  platform: string;
  status: string;
  campaign_name: string;
  message_sent: string;
  date: string;
  bio?: string;
  messages?: Message[];
}

const mockLeads: Lead[] = [
  {
    id: 1,
    name: 'John Smith',
    platform: 'Facebook',
    status: 'replied',
    campaign_name: 'Facebook 外贸客户开发',
    message_sent: 'Hi John, I noticed your work in international trade...',
    date: '2024-03-15',
    bio: 'CEO at Global Trade Co. | 15 years in B2B',
    messages: [
      {
        role: 'assistant',
        content: 'Hi John, I noticed your impressive work in international trade.',
        timestamp: '10:45',
      },
      {
        role: 'user',
        content: "Thanks for reaching out! What kind of collaboration are you thinking?",
        timestamp: '11:20',
      },
    ],
  },
  {
    id: 2,
    name: 'Sarah Lee',
    platform: 'Facebook',
    status: 'sent',
    campaign_name: 'Facebook 外贸客户开发',
    message_sent: 'Hello Sarah, your expertise in supply chain...',
    date: '2024-03-15',
    bio: 'Supply Chain Manager | E-commerce',
    messages: [
      {
        role: 'assistant',
        content: 'Hello Sarah, your expertise in supply chain management caught my attention...',
        timestamp: '10:46',
      },
    ],
  },
  {
    id: 3,
    name: 'Emma Wilson',
    platform: 'Facebook',
    status: 'interested',
    campaign_name: 'SaaS 决策者触达',
    message_sent: 'Hi Emma, I came across your profile and...',
    date: '2024-03-14',
    bio: 'VP of Operations at TechCorp',
    messages: [
      {
        role: 'assistant',
        content: 'Hi Emma, I came across your profile...',
        timestamp: '14:30',
      },
      {
        role: 'user',
        content: 'Interesting! Can you send me more details about your solution?',
        timestamp: '15:10',
      },
    ],
  },
];

const statusOptions = [
  { value: '', label: '全部状态' },
  { value: 'sent', label: '已发送' },
  { value: 'replied', label: '已回复' },
  { value: 'interested', label: '有意向' },
  { value: 'not_interested', label: '无意向' },
];

const platformOptions = [
  { value: '', label: '全部平台' },
  { value: 'Facebook', label: 'Facebook' },
  { value: 'Instagram', label: 'Instagram' },
];

export default function Leads() {
  const [leads, setLeads] = useState<Lead[]>(mockLeads);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [platformFilter, setPlatformFilter] = useState('');
  const [expandedId, setExpandedId] = useState<number | null>(null);

  useEffect(() => {
    leadApi
      .list()
      .then((data: unknown) => {
        const list = data as Lead[];
        if (Array.isArray(list) && list.length > 0) {
          setLeads(list);
        }
      })
      .catch(() => {
        // Keep mock data
      })
      .finally(() => setLoading(false));
  }, []);

  const filtered = leads.filter((lead) => {
    const matchSearch =
      !search ||
      lead.name.toLowerCase().includes(search.toLowerCase()) ||
      lead.campaign_name.toLowerCase().includes(search.toLowerCase());
    const matchStatus = !statusFilter || lead.status === statusFilter;
    const matchPlatform = !platformFilter || lead.platform === platformFilter;
    return matchSearch && matchStatus && matchPlatform;
  });

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight text-[#1d1d1f]">
          线索数据库
        </h1>
        <p className="mt-1 text-sm text-[#86868b]">查看和管理所有获取的线索</p>
      </div>

      {loading && (
        <div className="mb-4 rounded-xl bg-yellow-50 px-4 py-2.5 text-sm text-yellow-700">
          正在加载线索数据...
        </div>
      )}

      {/* Filters */}
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <div className="relative min-w-[200px] flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#86868b]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索姓名或任务名..."
            className="w-full rounded-xl border border-[#e5e5e7] bg-white py-2.5 pl-10 pr-4 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none transition-colors focus:border-[#0071e3]"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-xl border border-[#e5e5e7] bg-white px-4 py-2.5 text-sm text-[#1d1d1f] outline-none transition-colors focus:border-[#0071e3]"
        >
          {statusOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <select
          value={platformFilter}
          onChange={(e) => setPlatformFilter(e.target.value)}
          className="rounded-xl border border-[#e5e5e7] bg-white px-4 py-2.5 text-sm text-[#1d1d1f] outline-none transition-colors focus:border-[#0071e3]"
        >
          {platformOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="rounded-2xl bg-white border border-[#e5e5e7]/60 shadow-sm overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[#e5e5e7]/60">
              <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">
                姓名
              </th>
              <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">
                平台
              </th>
              <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">
                状态
              </th>
              <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">
                所属任务
              </th>
              <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">
                发送消息
              </th>
              <th className="px-6 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">
                日期
              </th>
              <th className="w-10 px-6 py-3.5" />
            </tr>
          </thead>
          <tbody className="divide-y divide-[#e5e5e7]/40">
            {filtered.map((lead) => (
              <>
                <tr
                  key={lead.id}
                  onClick={() =>
                    setExpandedId(expandedId === lead.id ? null : lead.id)
                  }
                  className="cursor-pointer transition-colors hover:bg-[#f5f5f7]/50"
                >
                  <td className="px-6 py-3.5 text-sm font-medium text-[#1d1d1f]">
                    {lead.name}
                  </td>
                  <td className="px-6 py-3.5 text-sm text-[#86868b]">
                    {lead.platform}
                  </td>
                  <td className="px-6 py-3.5">
                    <StatusBadge status={lead.status} />
                  </td>
                  <td className="px-6 py-3.5 text-sm text-[#86868b]">
                    {lead.campaign_name}
                  </td>
                  <td className="max-w-[200px] truncate px-6 py-3.5 text-sm text-[#86868b]">
                    {lead.message_sent}
                  </td>
                  <td className="px-6 py-3.5 text-sm text-[#86868b]">
                    {lead.date}
                  </td>
                  <td className="px-6 py-3.5">
                    {expandedId === lead.id ? (
                      <ChevronUp className="h-4 w-4 text-[#86868b]" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-[#86868b]" />
                    )}
                  </td>
                </tr>
                {expandedId === lead.id && (
                  <tr key={`${lead.id}-detail`}>
                    <td colSpan={7} className="bg-[#fafafa] px-6 py-5">
                      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                        <div>
                          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-[#86868b]">
                            个人资料
                          </h4>
                          <p className="text-sm font-medium text-[#1d1d1f]">
                            {lead.name}
                          </p>
                          {lead.bio && (
                            <p className="mt-1 text-sm text-[#86868b]">
                              {lead.bio}
                            </p>
                          )}
                        </div>
                        <div>
                          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-[#86868b]">
                            消息记录
                          </h4>
                          <div className="space-y-2">
                            {lead.messages?.map((msg, i) => (
                              <div
                                key={i}
                                className={`rounded-xl p-3 text-sm ${
                                  msg.role === 'assistant'
                                    ? 'bg-blue-50 text-blue-900'
                                    : 'border border-[#e5e5e7] bg-white text-[#1d1d1f]'
                                }`}
                              >
                                <div className="mb-1 flex items-center justify-between">
                                  <span className="text-xs font-medium">
                                    {msg.role === 'assistant' ? 'AI' : '对方'}
                                  </span>
                                  <span className="text-xs text-[#86868b]">
                                    {msg.timestamp}
                                  </span>
                                </div>
                                <p>{msg.content}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="py-12 text-center text-sm text-[#86868b]">
            暂无匹配的线索数据
          </div>
        )}
      </div>
    </div>
  );
}
