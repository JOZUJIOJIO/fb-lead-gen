'use client';

interface StatusBadgeProps {
  status: string;
  failureCode?: string | null;
  size?: 'sm' | 'md';
}

const statusConfig: Record<string, { label: string; bg: string; text: string; dot?: string }> = {
  draft: { label: '草稿', bg: 'bg-gray-100', text: 'text-gray-600' },
  running: { label: '运行中', bg: 'bg-emerald-50', text: 'text-emerald-700', dot: 'bg-emerald-500' },
  paused: { label: '已暂停', bg: 'bg-amber-50', text: 'text-amber-700', dot: 'bg-amber-500' },
  completed: { label: '已完成', bg: 'bg-blue-50', text: 'text-blue-700' },
  failed: { label: '失败', bg: 'bg-red-50', text: 'text-red-700' },
  stopped: { label: '已停止', bg: 'bg-gray-100', text: 'text-gray-500' },
  found: { label: '已发现', bg: 'bg-gray-100', text: 'text-gray-600' },
  analyzing: { label: '分析中', bg: 'bg-amber-50', text: 'text-amber-700', dot: 'bg-amber-500' },
  pending_review: { label: '待审核', bg: 'bg-orange-50', text: 'text-orange-700', dot: 'bg-orange-500' },
  messaged: { label: '已发送', bg: 'bg-blue-50', text: 'text-blue-700' },
  replied: { label: '已回复', bg: 'bg-emerald-50', text: 'text-emerald-700' },
  converted: { label: '已转化', bg: 'bg-purple-50', text: 'text-purple-700' },
  rejected: { label: '已拒绝', bg: 'bg-gray-100', text: 'text-gray-600' },
  blacklisted: { label: '已屏蔽', bg: 'bg-slate-100', text: 'text-slate-500' },
  sent: { label: '已发送', bg: 'bg-blue-50', text: 'text-blue-700' },
  interested: { label: '有意向', bg: 'bg-purple-50', text: 'text-purple-700' },
  not_interested: { label: '无意向', bg: 'bg-gray-100', text: 'text-gray-600' },
  pending: { label: '待发送', bg: 'bg-gray-100', text: 'text-gray-600' },
};

// failure_code → 用户友好的短标签（显示在 badge 上）
const failureLabels: Record<string, { label: string; bg: string; text: string }> = {
  // 对方原因（不是我们的问题）
  message_button_not_found:     { label: '无法私信', bg: 'bg-slate-100', text: 'text-slate-500' },
  message_input_not_found:      { label: '无法私信', bg: 'bg-slate-100', text: 'text-slate-500' },
  no_message_button:            { label: '无法私信', bg: 'bg-slate-100', text: 'text-slate-500' },
  user_inactive:                { label: '不活跃', bg: 'bg-gray-100', text: 'text-gray-500' },
  platform_messaging_blocked:   { label: '对方已屏蔽', bg: 'bg-slate-100', text: 'text-slate-500' },
  // 平台限制（风控相关）
  platform_identity_verification: { label: '需验证身份', bg: 'bg-amber-50', text: 'text-amber-700' },
  platform_action_restricted:   { label: '操作受限', bg: 'bg-amber-50', text: 'text-amber-700' },
  platform_feature_blocked:     { label: '功能受限', bg: 'bg-amber-50', text: 'text-amber-700' },
  platform_temporarily_blocked: { label: '暂时封锁', bg: 'bg-red-50', text: 'text-red-600' },
  platform_unusual_activity:    { label: '异常活动', bg: 'bg-red-50', text: 'text-red-600' },
  platform_security_check:      { label: '安全检查', bg: 'bg-amber-50', text: 'text-amber-700' },
  platform_checkpoint_redirect: { label: '安全检查', bg: 'bg-amber-50', text: 'text-amber-700' },
  // 系统/AI 问题
  login_expired:                { label: '登录过期', bg: 'bg-red-50', text: 'text-red-700' },
  greeting_generation_failed:   { label: 'AI 生成失败', bg: 'bg-red-50', text: 'text-red-700' },
  send_exception:               { label: '发送异常', bg: 'bg-red-50', text: 'text-red-700' },
  send_returned_false:          { label: '发送失败', bg: 'bg-red-50', text: 'text-red-700' },
  processing_exception:         { label: '处理异常', bg: 'bg-red-50', text: 'text-red-700' },
  check_error:                  { label: '检查失败', bg: 'bg-red-50', text: 'text-red-700' },
};

export default function StatusBadge({ status, failureCode, size = 'sm' }: StatusBadgeProps) {
  // 如果有 failureCode 且状态是 failed/blacklisted，显示具体原因
  if (failureCode && (status === 'failed' || status === 'blacklisted')) {
    const fc = failureLabels[failureCode];
    if (fc) {
      const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm';
      return (
        <span className={`inline-flex items-center gap-1.5 rounded-full font-medium ${fc.bg} ${fc.text} ${sizeClasses}`}>
          {fc.label}
        </span>
      );
    }
  }

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
