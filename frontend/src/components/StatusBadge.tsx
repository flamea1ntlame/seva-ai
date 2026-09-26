"use client";

import React from "react";
import {
  Clock,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  AlertTriangle,
  Send,
  FileCheck2,
  HelpCircle,
} from "lucide-react";
import {
  getApplicationStatusInfo,
  getDocumentStatusInfo,
} from "@/lib/statusMapping";

export function getStatusConfig(status: string, government_status?: string) {
  const info = getApplicationStatusInfo(status, government_status);

  let icon = <Clock className="h-3 w-3" />;
  if (info.label === "Completed" || info.label.includes("Approved")) {
    icon = <CheckCircle2 className="h-3 w-3" />;
  } else if (info.label.includes("Rejected")) {
    icon = <AlertCircle className="h-3 w-3" />;
  } else if (info.actionRequired) {
    icon = <AlertTriangle className="h-3 w-3" />;
  } else if (info.label === "Submitting" || info.label === "Submitted") {
    icon = <Send className="h-3 w-3" />;
  } else if (info.label.includes("Progress") || info.label.includes("Uploaded")) {
    icon = <RefreshCw className="h-3 w-3 animate-spin" />;
  }

  return {
    color: info.badgeClass,
    icon,
    label: info.label,
    stageNumber: info.stageNumber,
    description: info.description,
  };
}

export default function StatusBadge({
  status,
  government_status,
  className = "",
  showStage = false,
}: {
  status: string;
  government_status?: string;
  className?: string;
  showStage?: boolean;
}) {
  const config = getStatusConfig(status, government_status);

  return (
    <span
      className={`inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-md text-xs font-semibold border ${config.color} ${className}`}
      title={config.description}
    >
      {config.icon}
      <span>
        {showStage && config.stageNumber ? `Stage ${config.stageNumber}: ` : ""}
        {config.label}
      </span>
    </span>
  );
}

/**
 * Reusable Document Verification Status Badge
 */
export function DocumentVerificationBadge({
  verification_status,
  verified,
  className = "",
  showExplanation = false,
}: {
  verification_status?: string;
  verified?: boolean;
  className?: string;
  showExplanation?: boolean;
}) {
  const info = getDocumentStatusInfo(verification_status, verified);

  return (
    <div className="inline-flex flex-col">
      <span
        className={`inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-md text-xs font-semibold border ${info.badgeClass} ${className}`}
      >
        <span className="text-xs">{info.symbol}</span>
        <span>{info.label}</span>
      </span>
      {showExplanation && (
        <span className="text-[11px] text-slate-500 mt-0.5">
          {info.citizenExplanation}
        </span>
      )}
    </div>
  );
}
