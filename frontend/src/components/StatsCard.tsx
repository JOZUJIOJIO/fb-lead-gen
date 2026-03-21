import React from "react";
import clsx from "clsx";

interface StatsCardProps {
  icon: React.ElementType;
  value: string | number;
  label: string;
  trend?: { value: number; positive: boolean };
  color?: string;
}

export default function StatsCard({
  icon: Icon,
  value,
  label,
  trend,
  color = "bg-primary",
}: StatsCardProps) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 flex items-start gap-4">
      <div className={clsx("p-3 rounded-lg text-white", color)}>
        <Icon className="h-6 w-6" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        <p className="text-sm text-gray-500 mt-1">{label}</p>
        {trend && (
          <p
            className={clsx(
              "text-xs mt-1 font-medium",
              trend.positive ? "text-green-600" : "text-red-600"
            )}
          >
            {trend.positive ? "+" : ""}
            {trend.value}% 较上周
          </p>
        )}
      </div>
    </div>
  );
}
