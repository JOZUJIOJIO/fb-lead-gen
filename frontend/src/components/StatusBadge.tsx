'use client';

interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md';
}

const statusConfig: Record<string, { label: string; bg: string; text: string; dot?: string }> = {
  draft: { label: '草稿', bg: 'bg-gray-100', text: 'text-gray-600' },
  running: { label: '运行中', bg: 'bg-emerald-50', text: 'text-emerald-700', dot: 'bg-emerald-500' },
  paused: { label: '已暂停', bg: 'bg-amber-50', text: 'text-amber-700', dot: 'bg-amber-500' },
  completed: { label: '已完成', bg: 'bg-blue-50', text: 'text-blue-700' },
  failed: { label: '失败', bg: 'bg-red-50', text: 'text-red-700' },
  found: { label: '已发现', bg: 'bg-gray-100', text: 'text-gray-600' },
  analyzing: { label: '分析中', bg: 'bg-amber-50', text: 'text-amber-700', dot: 'bg-amber-500' },
  messaged: { label: '已发送', bg: 'bg-blue-50', text: 'text-blue-700' },
  replied: { label: '已回复', bg: 'bg-emerald-50', text: 'text-emerald-700' },
  converted: { label: '已转化', bg: 'bg-purple-50', text: 'text-purple-700' },
  sent: { label: '已发送', bg: 'bg-blue-50', text: 'text-blue-700' },
  interested: { label: '有意向', bg: 'bg-purple-50', text: 'text-purple-700' },
  not_interested: { label: '无意向', bg: 'bg-gray-100', text: 'text-gray-600' },
  pending: { label: '待发送', bg: 'bg-gray-100', text: 'text-gray-600' },
};

export default function StatusBadge({ status, size = 'sm' }: StatusBadgeProps) {
  const config = statusConfig[status] || { label: status, bg: 'bg-gray-100', text: 'text-gray-600' };
  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm';

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-medium ${config.bg} ${config.text} ${sizeClasses}`}>
      {config.dot && (
        <span className={`h-1.5 w-1.5 rounded-full ${config.dot} ${status === 'running' ? 'animate-pulse-dot' : ''}`} />
      )}
      {config.label}
    </span>
  );
}
