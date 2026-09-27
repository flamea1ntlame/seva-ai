"use client";

import React from "react";
import { CheckCircle2, Clock, XCircle, Circle, AlertTriangle, ShieldCheck } from "lucide-react";
import { getApplicationStatusInfo } from "@/lib/statusMapping";

export default function ApplicationTimeline({ application }: { application: any }) {
  if (!application) return null;

  const info = getApplicationStatusInfo(application.status, application.government_status);
  const currentStage = info.stageNumber; // 1 to 9
  const isRejected = (application.government_status || "").toUpperCase() === "REJECTED";

  // The 5 Major Milestone stages for the high-level citizen timeline
  const milestones = [
    {
      stage: 1,
      minStage: 1,
      label: "Application Started",
      subtext: "Initiated",
    },
    {
      stage: 3,
      minStage: 3,
      label: "Documents Provided",
      subtext: "Uploaded to vault",
    },
    {
      stage: 4,
      minStage: 4,
      label: "Rules Verified",
      subtext: "Requirements met",
    },
    {
      stage: 7,
      minStage: 7,
      label: "Submitted",
      subtext: "Sent to department",
    },
    {
      stage: 8,
      minStage: 8,
      label: isRejected ? "Rejected" : "Officer Processing",
      subtext: isRejected ? "Action needed" : "Under review",
      isRejected,
    },
    {
      stage: 9,
      minStage: 9,
      label: "Completed",
      subtext: "Certificate issued",
    },
  ];

  return (
    <div className="pt-2 pb-4">
      <div className="flex justify-between items-start relative px-2">
        {/* Background connector line */}
        <div className="absolute left-8 right-8 top-3 h-0.5 bg-slate-200 -z-0"></div>

        {milestones.map((m, idx) => {
          const isPassed = currentStage > m.minStage && (!m.isRejected || isRejected);
          const isCurrent = currentStage >= m.minStage && (idx === milestones.length - 1 || currentStage < milestones[idx + 1].minStage);
          const isFailed = m.isRejected && isRejected;

          let Icon = Circle;
          let iconClass = "text-slate-300 bg-white";
          let labelClass = "text-slate-400 font-medium";

          if (isFailed) {
            Icon = XCircle;
            iconClass = "text-rose-600 bg-white";
            labelClass = "text-rose-700 font-bold";
          } else if (isPassed) {
            Icon = CheckCircle2;
            iconClass = "text-emerald-600 bg-white";
            labelClass = "text-emerald-800 font-bold";
          } else if (isCurrent) {
            Icon = Clock;
            iconClass = "text-indigo-600 bg-white animate-pulse";
            labelClass = "text-indigo-900 font-bold";
          }

          return (
            <div key={idx} className="flex flex-col items-center z-10 w-24 text-center">
              <div className="bg-white p-0.5 rounded-full">
                <Icon className={`h-5 w-5 ${iconClass}`} />
              </div>
              <span className={`text-[11px] mt-1.5 leading-tight ${labelClass}`}>
                {m.label}
              </span>
              <span className="text-[9px] text-slate-400 font-medium hidden sm:block mt-0.5">
                {m.subtext}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
