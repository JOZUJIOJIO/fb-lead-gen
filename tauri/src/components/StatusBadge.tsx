interface StatusBadgeProps {
  status: string;
}

const statusConfig: Record<string, { label: string; className: string }> = {
  running: { label: '运行中', className: 'bg-green-100 text-green-700' },
  paused: { label: '已暂停', className: 'bg-yellow-100 text-yellow-700' },
  completed: { label: '已完成', className: 'bg-[#f5f5f7] text-[#86868b]' },
  draft: { label: '草稿', className: 'bg-[#f5f5f7] text-[#86868b]' },
  stopped: { label: '已停止', className: 'bg-red-100 text-red-700' },
  sent: { label: '已发送', className: 'bg-blue-100 text-blue-700' },
  replied: { label: '已回复', className: 'bg-green-100 text-green-700' },
  interested: { label: '有意向', className: 'bg-purple-100 text-purple-700' },
  not_interested: { label: '无意向', className: 'bg-[#f5f5f7] text-[#86868b]' },
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  const config = statusConfig[status] ?? {
    label: status,
    className: 'bg-[#f5f5f7] text-[#86868b]',
  };

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${config.className}`}
    >
      {config.label}
    </span>
  );
}
