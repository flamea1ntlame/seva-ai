import React from "react";
import { CheckCircle2, Clock, XCircle, Circle } from "lucide-react";

export default function ApplicationTimeline({ application }: { application: any }) {
  // SEVA status dictates if it reached the government submission gate
  const isSubmitted = ["SUBMITTED", "TRACKING", "COMPLETED"].includes(application.status);
  
  // Government status logic
  const isUnderReview = application.government_status === "UNDER_REVIEW" || application.government_status === "APPROVED" || application.government_status === "REJECTED";
  const isApproved = application.government_status === "APPROVED";
  const isRejected = application.government_status === "REJECTED";

  if (!isSubmitted && application.status !== "COMPLETED") {
    return null; // Timeline only shows post-submission tracking
  }

  const steps = [
    {
      label: "Submitted",
      completed: isSubmitted,
      active: application.status === "SUBMITTED" && !application.government_status,
      rejected: false,
    },
    {
      label: "Government Received",
      completed: isUnderReview || isApproved || isRejected || application.government_status === "SUBMITTED",
      active: application.government_status === "SUBMITTED",
      rejected: false,
    },
    {
      label: "Under Review",
      completed: isApproved || isRejected,
      active: application.government_status === "UNDER_REVIEW",
      rejected: false,
    },
    {
      label: isRejected ? "Rejected" : (isApproved ? "Approved" : "Decision"),
      completed: isApproved || isRejected,
      active: false,
      rejected: isRejected,
    },
  ];

  return (
    <div className="pt-4 pb-2">
      <div className="flex justify-between items-center relative px-2">
        {/* Background line */}
        <div className="absolute left-6 right-6 top-[9px] h-0.5 bg-brand-200 -z-10"></div>
        
        {steps.map((step, idx) => {
          let Icon = Circle;
          let colorClass = "text-brand-300 bg-white border-brand-200";
          let labelColor = "text-brand-400";
          
          if (step.rejected) {
            Icon = XCircle;
            colorClass = "text-error-500 bg-white";
            labelColor = "text-error-600 font-bold";
          } else if (step.completed) {
            Icon = CheckCircle2;
            colorClass = "text-success-500 bg-white";
            labelColor = "text-success-600 font-bold";
          } else if (step.active) {
            Icon = Clock;
            colorClass = "text-primary-500 bg-white animate-pulse";
            labelColor = "text-primary-600 font-bold";
          }

          return (
            <div key={idx} className="flex flex-col items-center z-10 w-20">
              <div className="bg-white px-1">
                <Icon className={`h-5 w-5 ${colorClass}`} fill="currentColor" stroke="white" strokeWidth={2} />
              </div>
              <span className={`text-[10px] mt-2 text-center uppercase tracking-wider ${labelColor}`}>
                {step.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
