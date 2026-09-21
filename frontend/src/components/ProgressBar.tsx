import React from "react";

export default function ProgressBar({
  progress,
  className = "",
}: {
  progress: number;
  className?: string;
}) {
  // Ensure progress is between 0 and 100
  const normalizedProgress = Math.min(Math.max(progress, 0), 100);

  let barColor = "bg-primary-500";
  if (normalizedProgress === 100) {
    barColor = "bg-success-500";
  }

  return (
    <div className={`w-full ${className}`}>
      <div className="flex justify-between items-center mb-1.5 text-[10px] font-bold uppercase tracking-wider text-brand-500">
        <span>Progress</span>
        <span>{normalizedProgress}%</span>
      </div>
      <div className="w-full bg-brand-100 rounded-full h-1.5 overflow-hidden border border-brand-200">
        <div
          className={`${barColor} h-1.5 rounded-full transition-all duration-700 ease-out`}
          style={{ width: `${normalizedProgress}%` }}
        ></div>
      </div>
    </div>
  );
}
