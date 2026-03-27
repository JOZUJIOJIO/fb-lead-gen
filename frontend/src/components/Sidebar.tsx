"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import {
  BoltIcon,
  ChartBarIcon,
  ChartPieIcon,
  UsersIcon,
  MegaphoneIcon,
  ChatBubbleLeftRightIcon,
  ChatBubbleOvalLeftEllipsisIcon,
  DocumentTextIcon,
  Cog6ToothIcon,
  ArrowRightOnRectangleIcon,
} from "@heroicons/react/24/outline";
import { useAuth } from "@/lib/auth";

const navItems = [
  { href: "/", label: "仪表盘", icon: ChartBarIcon },
  { href: "/automation", label: "自动化", icon: BoltIcon },
  { href: "/leads", label: "线索管理", icon: UsersIcon },
  { href: "/conversations", label: "对话管理", icon: ChatBubbleOvalLeftEllipsisIcon },
  { href: "/campaigns", label: "营销活动", icon: MegaphoneIcon },
  { href: "/messages", label: "消息中心", icon: ChatBubbleLeftRightIcon },
  { href: "/templates", label: "模板管理", icon: DocumentTextIcon },
  { href: "/analytics", label: "数据分析", icon: ChartPieIcon },
  { href: "/settings", label: "设置", icon: Cog6ToothIcon },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <aside className="fixed left-0 top-0 h-full w-64 bg-sidebar text-white flex flex-col z-40">
      <div className="p-6 border-b border-slate-700">
        <h1 className="text-xl font-bold tracking-tight">
          <span className="text-primary">LeadFlow</span> AI
        </h1>
        <p className="text-xs text-slate-400 mt-1">智能外贸获客平台</p>
      </div>

      <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-white"
                  : "text-slate-300 hover:bg-slate-700 hover:text-white"
              )}
            >
              <item.icon className="h-5 w-5 flex-shrink-0" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-slate-700">
        {user && (
          <div className="flex items-center justify-between">
            <div className="min-w-0">
              <p className="text-sm font-medium truncate">{user.company_name || user.email}</p>
              <p className="text-xs text-slate-400 truncate">{user.email}</p>
            </div>
            <button
              onClick={logout}
              className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-700 transition-colors"
              title="退出登录"
            >
              <ArrowRightOnRectangleIcon className="h-5 w-5" />
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
