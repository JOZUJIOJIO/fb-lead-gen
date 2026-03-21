import React from "react";
import clsx from "clsx";

interface ScoreBadgeProps {
  score: number | null | undefined;
}

export default function ScoreBadge({ score }: ScoreBadgeProps) {
  if (score === null || score === undefined) {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
        未评分
      </span>
    );
  }

  const colorClass =
    score >= 80
      ? "bg-emerald-100 text-emerald-800"
      : score >= 60
      ? "bg-green-100 text-green-800"
      : score >= 40
      ? "bg-yellow-100 text-yellow-800"
      : "bg-red-100 text-red-800";

  return (
    <span
      className={clsx(
        "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold",
        colorClass
      )}
    >
      {score}
    </span>
  );
}
