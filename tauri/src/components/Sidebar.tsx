import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Target,
  Users,
  UserCircle,
  Settings,
} from 'lucide-react';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: '看板' },
  { to: '/campaigns', icon: Target, label: '任务' },
  { to: '/leads', icon: Users, label: '线索' },
  { to: '/personas', icon: UserCircle, label: '人设' },
  { to: '/settings', icon: Settings, label: '设置' },
];

export default function Sidebar() {
  return (
    <aside className="flex h-screen w-56 flex-col bg-white border-r border-[#e5e5e7]/60">
      {/* Logo */}
      <div className="flex h-14 items-center px-5 border-b border-[#e5e5e7]/60">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#0071e3]">
            <Target className="h-4 w-4 text-white" />
          </div>
          <span className="text-sm font-semibold text-[#1d1d1f]">LeadFlow</span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-0.5 px-3 py-4">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-[#0071e3]/10 text-[#0071e3]'
                  : 'text-[#424245] hover:bg-[#f5f5f7] hover:text-[#1d1d1f]'
              }`
            }
          >
            <Icon className="h-4 w-4 flex-shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Version */}
      <div className="px-5 pb-4">
        <p className="text-xs text-[#86868b]">v0.1.0</p>
      </div>
    </aside>
  );
}
