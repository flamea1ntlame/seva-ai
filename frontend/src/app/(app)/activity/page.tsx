"use client";

import React, { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";
import { Activity, Loader2, Calendar } from "lucide-react";

export default function ActivityPage() {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchApi("/api/audit/")
      .then(setLogs)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      
      <div className="mb-8">
        <h1 className="text-2xl font-extrabold text-brand-900">Activity Log</h1>
        <p className="text-sm text-brand-500 mt-1">A complete record of your interactions and application progress.</p>
      </div>

      {loading ? (
        <div className="py-20 flex justify-center">
          <Loader2 className="h-8 w-8 text-primary-500 animate-spin" />
        </div>
      ) : logs.length === 0 ? (
        <div className="bg-white rounded-3xl border border-brand-200 p-12 text-center">
          <Activity className="h-8 w-8 text-brand-300 mx-auto mb-4" />
          <p className="text-brand-500 text-sm">No activity recorded yet.</p>
        </div>
      ) : (
        <div className="bg-white rounded-3xl border border-brand-200 shadow-sm p-6 sm:p-8">
          <div className="space-y-6 relative before:absolute before:inset-0 before:ml-4 md:before:ml-6 before:-translate-x-px before:h-full before:w-0.5 before:bg-brand-100">
            {logs.map((log) => {
              // Humanize actions
              let humanAction = log.action.replace(/_/g, ' ');
              let detailText = log.details || "";

              if (log.action === "APPLICATION_CREATED") humanAction = "Application Started";
              else if (log.action === "CONSENT_APPROVED") humanAction = "Consent Approved";
              else if (log.action === "DOCUMENT_UPLOADED") humanAction = "Document Uploaded";
              else if (log.action === "DATA_EXTRACTED") humanAction = "Document Data Extracted";
              else if (log.action === "STATUS_CHANGED") {
                humanAction = `Application Status Updated`;
              }
              else if (log.action === "SUBMIT_APPLICATION") humanAction = "Application Submitted to Government";
              
              const isStatusChange = log.action.includes("STATUS") || log.action.includes("SUBMIT");

              return (
                <div key={log.id} className="relative flex items-start space-x-4 md:space-x-6">
                  {/* Timeline dot */}
                  <div className={`flex items-center justify-center w-8 h-8 rounded-full border-4 border-white shadow shrink-0 z-10 ${isStatusChange ? 'bg-primary-500' : 'bg-brand-300'}`}></div>
                  
                  {/* Content card */}
                  <div className="flex-1 bg-brand-50/50 border border-brand-100 rounded-2xl p-4 md:p-5 hover:bg-brand-50 transition-colors">
                    <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center mb-2 gap-2">
                      <h4 className="text-sm font-bold text-brand-900">{humanAction}</h4>
                      <div className="flex items-center space-x-1.5 text-[10px] font-bold uppercase tracking-wider text-brand-500 bg-white px-2 py-1 rounded-md border border-brand-100 w-fit">
                        <Calendar className="h-3 w-3" />
                        <span>{new Date(log.created_at).toLocaleString()}</span>
                      </div>
                    </div>
                    
                    <p className="text-xs text-brand-600 leading-relaxed font-medium">
                      {detailText || `Action performed on ${log.resource_type.toLowerCase()} ${log.resource_id}`}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
