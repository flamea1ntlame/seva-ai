import React from "react";
import Link from "next/link";
import StatusBadge from "./StatusBadge";
import ProgressBar from "./ProgressBar";
import { FileText, ChevronRight, AlertTriangle } from "lucide-react";

export default function ApplicationCard({ application }: { application: any }) {
  const hasMissingInfo = application.status === "MISSING_INFORMATION";
  const needsConsent = application.status === "CONSENT_REQUIRED";
  const actionRequired = hasMissingInfo || needsConsent;

  return (
    <div className="bg-white rounded-2xl border border-brand-200 shadow-xs hover:shadow-md transition-shadow duration-200 p-5 flex flex-col h-full group">
      <div className="flex justify-between items-start mb-4">
        <div className="flex items-center space-x-3">
          <div className="h-10 w-10 bg-primary-50 rounded-xl flex items-center justify-center border border-primary-100">
            <FileText className="h-5 w-5 text-primary-600" />
          </div>
          <div>
            <h3 className="font-bold text-sm text-brand-900 group-hover:text-primary-600 transition-colors">
              {application.service?.title || "Service Request"}
            </h3>
            <span className="text-[11px] font-medium text-brand-500 uppercase tracking-wide">
              {application.service?.department || "Government"} Dept
            </span>
          </div>
        </div>
      </div>

      <div className="space-y-3 mb-6">
        <div className="flex flex-col space-y-1.5">
          <div className="flex justify-between items-center text-xs">
            <span className="text-brand-500">Reference No.</span>
            <span className="font-mono font-bold text-brand-900 bg-brand-50 px-2 py-0.5 rounded">
              {application.government_reference || application.application_number}
            </span>
          </div>
          <div className="flex justify-between items-center text-xs">
            <span className="text-brand-500">SEVA Status</span>
            <StatusBadge status={application.status} />
          </div>
          {application.government_status && (
            <div className="flex justify-between items-center text-xs">
              <span className="text-brand-500">Govt Status</span>
              <StatusBadge status={application.status} government_status={application.government_status} />
            </div>
          )}
        </div>
      </div>

      {actionRequired && (
        <div className="mb-4 bg-warning-50 border border-warning-200 rounded-lg p-3 flex items-start space-x-2">
          <AlertTriangle className="h-4 w-4 text-warning-600 shrink-0 mt-0.5" />
          <div className="text-xs text-warning-800">
            <span className="font-bold block mb-0.5">Action Required</span>
            {hasMissingInfo ? "Additional information is needed." : "Consent approval required."}
          </div>
        </div>
      )}

      <div className="mt-auto pt-4 border-t border-brand-100">
        <ProgressBar progress={application.progress_percentage || 0} className="mb-4" />
        <Link
          href={`/applications/${application.id}`}
          className="w-full flex items-center justify-center space-x-2 bg-brand-50 hover:bg-brand-100 text-brand-700 text-xs font-bold uppercase tracking-wider py-2.5 rounded-xl transition-colors border border-brand-200"
        >
          <span>View Details</span>
          <ChevronRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}
