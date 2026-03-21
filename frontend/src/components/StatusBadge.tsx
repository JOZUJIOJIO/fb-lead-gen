import React from "react";
import clsx from "clsx";

const statusConfig: Record<string, { label: string; className: string }> = {
  // Lead statuses
  new: { label: "新线索", className: "bg-blue-100 text-blue-800" },
  analyzed: { label: "已分析", className: "bg-purple-100 text-purple-800" },
  contacted: { label: "已联系", className: "bg-yellow-100 text-yellow-800" },
  replied: { label: "已回复", className: "bg-green-100 text-green-800" },
  converted: { label: "已转化", className: "bg-emerald-100 text-emerald-800" },
  // Campaign statuses
  draft: { label: "草稿", className: "bg-gray-100 text-gray-800" },
  active: { label: "进行中", className: "bg-green-100 text-green-800" },
  paused: { label: "已暂停", className: "bg-yellow-100 text-yellow-800" },
  completed: { label: "已完成", className: "bg-blue-100 text-blue-800" },
  // Message statuses
  pending_approval: { label: "待审核", className: "bg-orange-100 text-orange-800" },
  approved: { label: "已审核", className: "bg-blue-100 text-blue-800" },
  sent: { label: "已发送", className: "bg-indigo-100 text-indigo-800" },
  delivered: { label: "已送达", className: "bg-purple-100 text-purple-800" },
  read: { label: "已读", className: "bg-green-100 text-green-800" },
  failed: { label: "失败", className: "bg-red-100 text-red-800" },
};

interface StatusBadgeProps {
  status: string;
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  const config = statusConfig[status] || {
    label: status,
    className: "bg-gray-100 text-gray-800",
  };

  return (
    <span
      className={clsx(
        "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium",
        config.className
      )}
    >
      {config.label}
    </span>
  );
}
