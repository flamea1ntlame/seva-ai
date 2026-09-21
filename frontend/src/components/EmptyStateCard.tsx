import React from "react";
import { LucideIcon } from "lucide-react";

interface EmptyStateProps {
  title: string;
  description: string;
  icon: LucideIcon;
  actionText?: string;
  onAction?: () => void;
}

export default function EmptyStateCard({
  title,
  description,
  icon: Icon,
  actionText,
  onAction,
}: EmptyStateProps) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-8 text-center shadow-xs flex flex-col items-center justify-center">
      <div className="h-12 w-12 rounded-full bg-indigo-50 flex items-center justify-center text-indigo-600 mb-4">
        <Icon className="h-6 w-6" />
      </div>
      <h3 className="text-base font-semibold text-slate-900 mb-1">{title}</h3>
      <p className="text-sm text-slate-500 max-w-sm mb-6">{description}</p>
      {actionText && (
        <button
          onClick={onAction}
          className="inline-flex items-center px-4 py-2 text-xs font-semibold rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 transition"
        >
          {actionText}
        </button>
      )}
    </div>
  );
}
