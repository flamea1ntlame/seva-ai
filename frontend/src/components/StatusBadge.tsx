import React from "react";
import { Clock, CheckCircle2, AlertCircle, RefreshCw, AlertTriangle, Send } from "lucide-react";

export function getStatusConfig(status: string, government_status?: string) {
  // If government status exists and SEVA status is SUBMITTED, TRACKING, or COMPLETED, prioritize government status
  const effectiveStatus = government_status || status;
  let label = effectiveStatus.replace("_", " ");
  if (effectiveStatus === "READY_FOR_REVIEW") label = "Review Required";
  else if (effectiveStatus === "SUBMITTED") label = "Submitted";
  else if (effectiveStatus === "TRACKING") label = "Under Review";
  else if (effectiveStatus === "COMPLETED") label = "Completed";

  switch (effectiveStatus) {
    case "COMPLETED":
    case "APPROVED":
    case "VERIFIED":
      return {
        color: "bg-success-50 text-success-700 border-success-200",
        icon: <CheckCircle2 className="h-3 w-3" />,
        label: label,
      };
    case "REJECTED":
      return {
        color: "bg-error-50 text-error-700 border-error-200",
        icon: <AlertCircle className="h-3 w-3" />,
        label: label,
      };
    case "MISSING_INFORMATION":
    case "CONSENT_REQUIRED":
    case "ACTION_REQUIRED":
    case "READY_FOR_REVIEW":
      return {
        color: "bg-warning-50 text-warning-800 border-warning-200",
        icon: <AlertTriangle className="h-3 w-3" />,
        label: label,
      };
    case "SUBMITTING":
    case "SUBMITTED":
      return {
        color: "bg-primary-50 text-primary-700 border-primary-200",
        icon: <Send className="h-3 w-3" />,
        label: label,
      };
    case "UNDER_REVIEW":
    case "TRACKING":
    case "EXTRACTING":
    case "VALIDATING":
      return {
        color: "bg-brand-100 text-brand-700 border-brand-200",
        icon: <RefreshCw className="h-3 w-3 animate-spin" />,
        label: label,
      };
    default:
      return {
        color: "bg-brand-50 text-brand-600 border-brand-200",
        icon: <Clock className="h-3 w-3" />,
        label: label,
      };
  }
}

export default function StatusBadge({
  status,
  government_status,
  className = "",
}: {
  status: string;
  government_status?: string;
  className?: string;
}) {
  const config = getStatusConfig(status, government_status);

  return (
    <span
      className={`inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider border ${config.color} ${className}`}
    >
      {config.icon}
      <span>{config.label}</span>
    </span>
  );
}
