"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { fetchApi } from "@/lib/api";
import { useEventContext } from "@/contexts/EventContext";
import ApplicationTimeline from "@/components/ApplicationTimeline";
import StatusBadge from "@/components/StatusBadge";
import { ArrowLeft, Building2, User, FileText, Loader2, Calendar, FileBadge2, Activity } from "lucide-react";
import Link from "next/link";

export default function ApplicationDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const { agentActivity } = useEventContext();

  const [application, setApplication] = useState<any>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    try {
      const [appData, logsData] = await Promise.all([
        fetchApi(`/api/applications/${id}`),
        fetchApi(`/api/applications/${id}/audit`)
      ]);
      setApplication(appData);
      setLogs(logsData);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (id) {
      loadData();
    }
  }, [id, loadData, agentActivity]);

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="h-8 w-8 text-primary-500 animate-spin" />
      </div>
    );
  }

  if (!application) {
    return (
      <div className="text-center py-20">
        <p className="text-brand-500">Application not found.</p>
        <button onClick={() => router.back()} className="mt-4 text-primary-600 font-bold">Go back</button>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-12">
      
      {/* Back navigation */}
      <Link href="/applications" className="inline-flex items-center space-x-2 text-brand-500 hover:text-brand-900 transition-colors text-sm font-medium">
        <ArrowLeft className="h-4 w-4" />
        <span>Back to Applications</span>
      </Link>

      {/* Header Card */}
      <div className="bg-white rounded-3xl border border-brand-200 shadow-sm overflow-hidden">
        <div className="bg-brand-900 px-8 py-6 text-white flex flex-col md:flex-row md:items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-extrabold mb-1">{application.service?.title || "Application"}</h1>
            <div className="flex items-center space-x-2 text-brand-300 text-sm font-medium">
              <Building2 className="h-4 w-4" />
              <span>{application.service?.department} Department</span>
            </div>
          </div>
          <div className="flex flex-col items-start md:items-end space-y-2">
            <span className="text-[10px] uppercase tracking-wider text-brand-400 font-bold">Reference Number</span>
            <div className="bg-white/10 border border-white/20 px-3 py-1 rounded-lg font-mono font-bold">
              {application.government_reference || application.application_number}
            </div>
          </div>
        </div>

        <div className="p-8 border-b border-brand-100">
          <div className="flex flex-col md:flex-row gap-6 md:items-center justify-between mb-8">
            <div className="space-y-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-brand-500 block">SEVA Status</span>
              <StatusBadge status={application.status} />
            </div>
            
            {application.government_status && (
              <div className="space-y-1">
                <span className="text-[10px] font-bold uppercase tracking-wider text-brand-500 block">Government Status</span>
                <StatusBadge status={application.status} government_status={application.government_status} />
              </div>
            )}

            <div className="space-y-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-brand-500 block">Submitted On</span>
              <div className="flex items-center space-x-1.5 text-sm font-medium text-brand-900">
                <Calendar className="h-4 w-4 text-brand-400" />
                <span>{new Date(application.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          </div>

          <ApplicationTimeline application={application} />
        </div>

        <div className="grid md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-brand-100">
          
          {/* Details Column */}
          <div className="p-8 space-y-6">
            <h3 className="text-sm font-bold text-brand-900 flex items-center space-x-2 uppercase tracking-wider">
              <User className="h-4 w-4 text-primary-500" />
              <span>Applicant Details</span>
            </h3>
            
            {application.form_data && Object.keys(application.form_data).length > 0 ? (
              <div className="space-y-4">
                {Object.entries(application.form_data).map(([k, v]) => (
                  <div key={k}>
                    <span className="block text-[11px] font-bold text-brand-500 uppercase tracking-wider mb-0.5">
                      {k.replace(/_/g, ' ')}
                    </span>
                    <span className="text-sm font-medium text-brand-900">{String(v)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-brand-500">Details will be extracted from documents.</p>
            )}
          </div>

          {/* Documents Column */}
          <div className="p-8 space-y-6">
            <h3 className="text-sm font-bold text-brand-900 flex items-center space-x-2 uppercase tracking-wider">
              <FileBadge2 className="h-4 w-4 text-primary-500" />
              <span>Verified Documents</span>
            </h3>

            {application.documents && application.documents.length > 0 ? (
              <div className="space-y-3">
                {application.documents.map((doc: any) => (
                  <div key={doc.id} className="flex items-start space-x-3 bg-brand-50 border border-brand-100 p-3 rounded-xl">
                    <div className="h-8 w-8 bg-white rounded-lg border border-brand-200 flex items-center justify-center shrink-0">
                      <FileText className="h-4 w-4 text-brand-400" />
                    </div>
                    <div>
                      <p className="text-sm font-bold text-brand-900 line-clamp-1">{doc.title}</p>
                      <p className="text-[10px] uppercase font-bold tracking-wider text-brand-500 mt-0.5">{doc.document_type.replace(/_/g, ' ')}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-brand-500">No documents verified yet.</p>
            )}
          </div>

        </div>
      </div>

      {/* Activity Log */}
      {logs.length > 0 && (
        <div className="bg-white rounded-3xl border border-brand-200 shadow-sm p-8">
          <h3 className="text-sm font-bold text-brand-900 flex items-center space-x-2 uppercase tracking-wider mb-6">
            <Activity className="h-4 w-4 text-primary-500" />
            <span>Activity Timeline</span>
          </h3>

          <div className="space-y-6 relative before:absolute before:inset-0 before:ml-4 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-brand-100">
            {logs.map((log: any, idx: number) => {
              const isStatusChange = log.action.includes("STATUS");
              
              // Humanize the action
              let humanText = log.action.replace(/_/g, ' ');
              if (log.action === "STATUS_CHANGED") {
                humanText = `Status updated to ${log.resource_id}`;
              } else if (log.action === "APPLICATION_CREATED" || log.action === "CREATE_APPLICATION") {
                humanText = "Application started";
              } else if (log.action === "DOCUMENT_VERIFIED") {
                humanText = `Document Verified: ${log.details?.document_type?.replace(/_/g, ' ') || 'Document'}`;
              } else if (log.action === "REQUEST_CONSENT") {
                humanText = "Consent Requested for Data Sharing";
              } else if (log.action === "SUBMIT_APPLICATION") {
                humanText = "Application Submitted to Department";
              } else if (log.action === "CONSENT_APPROVED") {
                humanText = "Consent Approved by Citizen";
              }

              return (
                <div key={log.id} className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group">
                  {/* Icon */}
                  <div className={`flex items-center justify-center w-8 h-8 rounded-full border-2 border-white shadow shrink-0 md:order-1 md:group-odd:-translate-x-1/2 md:group-even:translate-x-1/2 ${isStatusChange ? 'bg-primary-500' : 'bg-brand-300'}`}>
                    <div className="h-2 w-2 bg-white rounded-full"></div>
                  </div>
                  
                  {/* Card */}
                  <div className="w-[calc(100%-4rem)] md:w-[calc(50%-2.5rem)] p-4 rounded-xl border border-brand-100 bg-brand-50 shadow-xs">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[10px] font-bold text-brand-500 uppercase tracking-wider">
                        {new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                    <p className="text-sm font-medium text-brand-900 capitalize">{humanText}</p>
                    <p className="text-xs text-brand-500 mt-1">{new Date(log.created_at).toLocaleDateString()}</p>
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
