"use client";

import React from "react";
import Link from "next/link";
import StatusBadge from "./StatusBadge";
import ProgressBar from "./ProgressBar";
import { FileText, ChevronRight, AlertTriangle, ArrowRight } from "lucide-react";
import { getApplicationStatusInfo, humanizeKey } from "@/lib/statusMapping";

export default function ApplicationCard({ application }: { application: any }) {
  const statusInfo = getApplicationStatusInfo(application.status, application.government_status);
  const actionRequired = statusInfo.actionRequired;

  // Calculate milestone percentage from stage number (1 to 9)
  const progressPercent = Math.round((statusInfo.stageNumber / 9) * 100);

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-xs hover:shadow-md transition-shadow duration-200 p-5 flex flex-col h-full group">
      <div className="flex justify-between items-start mb-3">
        <div className="flex items-center space-x-3">
          <div className="h-10 w-10 bg-indigo-50 rounded-xl flex items-center justify-center border border-indigo-100 shrink-0">
            <FileText className="h-5 w-5 text-indigo-600" />
          </div>
          <div>
            <h3 className="font-bold text-sm text-slate-900 group-hover:text-indigo-600 transition-colors line-clamp-1">
              {application.service?.title || "Service Request"}
            </h3>
            <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
              {humanizeKey(application.service?.department || "Government")} Dept
            </span>
          </div>
        </div>
      </div>

      <div className="space-y-2.5 mb-4">
        <div className="flex justify-between items-center text-xs">
          <span className="text-slate-500">Ref No.</span>
          <span className="font-mono font-bold text-slate-900 bg-slate-100 px-2 py-0.5 rounded-md">
            {application.government_reference || application.application_number}
          </span>
        </div>
        <div className="flex justify-between items-center text-xs">
          <span className="text-slate-500">Current Stage</span>
          <StatusBadge
            status={application.status}
            government_status={application.government_status}
          />
        </div>
      </div>

      {actionRequired && (
        <div className="mb-4 bg-amber-50 border border-amber-200 rounded-xl p-3 flex items-start space-x-2">
          <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
          <div className="text-xs text-amber-900 space-y-0.5">
            <span className="font-bold block">Citizen Action Needed</span>
            <p className="text-[11px] text-amber-800 leading-tight">
              {statusInfo.actionPrompt || "Please update documents or review application."}
            </p>
          </div>
        </div>
      )}

      <div className="mt-auto pt-3 border-t border-slate-100 space-y-3">
        <div className="space-y-1">
          <div className="flex justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400">
            <span>Stage {statusInfo.stageNumber} of 9</span>
            <span>{progressPercent}% Complete</span>
          </div>
          <ProgressBar progress={progressPercent} className="h-1.5" />
        </div>

        <Link
          href={`/applications/${application.id}`}
          className="w-full flex items-center justify-center space-x-1.5 bg-slate-50 hover:bg-indigo-50 hover:text-indigo-700 text-slate-700 text-xs font-bold uppercase tracking-wider py-2.5 rounded-xl transition border border-slate-200"
        >
          <span>{actionRequired ? (statusInfo.actionLabel || "Fix & Proceed") : "Open Workspace"}</span>
          <ChevronRight className="h-3.5 w-3.5" />
        </Link>
      </div>
    </div>
  );
}
