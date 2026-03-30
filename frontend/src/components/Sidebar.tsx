'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  LayoutDashboard,
  Megaphone,
  Users,
  UserCircle,
  Settings,
  Zap,
  LogOut,
} from 'lucide-react';

const navItems = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/campaigns', label: '任务', icon: Megaphone },
  { href: '/leads', label: '线索', icon: Users },
  { href: '/personas', label: '人设', icon: UserCircle },
  { href: '/settings', label: '设置', icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    router.push('/');
  };

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-16 flex-col bg-[#1a1a2e] transition-all duration-200 lg:w-56">
      {/* Logo */}
      <div className="flex h-16 items-center gap-2.5 px-4">
        <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600">
          <Zap className="h-4 w-4 text-white" />
        </div>
        <span className="hidden text-base font-semibold tracking-tight text-white lg:block">
          LeadFlow
        </span>
      </div>

      {/* Navigation */}
      <nav className="mt-4 flex flex-1 flex-col gap-1 px-2">
        {navItems.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(item.href + '/');
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-150 ${
                isActive
                  ? 'bg-white/10 text-white'
                  : 'text-white/50 hover:bg-white/5 hover:text-white/80'
              }`}
            >
              <item.icon className={`h-5 w-5 flex-shrink-0 ${isActive ? 'text-white' : 'text-white/50 group-hover:text-white/80'}`} />
              <span className="hidden lg:block">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Bottom */}
      <div className="border-t border-white/5 p-2">
        <button
          onClick={handleLogout}
          className="group flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-white/50 transition-all duration-150 hover:bg-white/5 hover:text-white/80"
        >
          <LogOut className="h-5 w-5 flex-shrink-0 text-white/50 group-hover:text-white/80" />
          <span className="hidden lg:block">退出登录</span>
        </button>
        <div className="mt-2 hidden items-center gap-2 px-3 lg:flex">
          <div className="h-2 w-2 rounded-full bg-emerald-400" />
          <span className="text-xs text-white/40">系统运行中</span>
        </div>
      </div>
    </aside>
  );
}
