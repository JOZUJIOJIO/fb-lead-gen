import { LucideIcon } from 'lucide-react';

interface StatsCardProps {
  icon: LucideIcon;
  label: string;
  value: string | number;
  trend?: { value: string; positive: boolean };
}

export default function StatsCard({ icon: Icon, label, value, trend }: StatsCardProps) {
  return (
    <div className="rounded-2xl bg-white p-5 border border-[#e5e5e7]/60 shadow-sm">
      <div className="flex items-start justify-between">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#f5f5f7]">
          <Icon className="h-5 w-5 text-[#0071e3]" />
        </div>
        {trend && (
          <span
            className={`text-xs font-medium ${
              trend.positive ? 'text-green-600' : 'text-red-500'
            }`}
          >
            {trend.positive ? '+' : '-'}{trend.value}
          </span>
        )}
      </div>
      <div className="mt-3">
        <p className="text-2xl font-semibold text-[#1d1d1f]">{value}</p>
        <p className="mt-0.5 text-sm text-[#86868b]">{label}</p>
      </div>
    </div>
  );
}
