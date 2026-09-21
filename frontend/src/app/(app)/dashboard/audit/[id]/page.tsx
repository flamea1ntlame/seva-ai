"use client";

import React, { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";
import { useParams, useRouter } from "next/navigation";
import { 
  ArrowLeft, 
  Loader2, 
  AlertCircle,
  FileCheck,
  ShieldCheck,
  Upload,
  Bot,
  User,
  Settings,
  Building,
  CheckCircle2,
  XCircle,
  FileText
} from "lucide-react";
import { format } from "date-fns";

export default function AuditLogPage() {
  const params = useParams();
  const router = useRouter();
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const applicationId = params.id as string;

  useEffect(() => {
    if (!applicationId) return;

    const loadAuditLogs = async () => {
      try {
        setLoading(true);
        const data = await fetchApi(`/api/applications/${applicationId}/audit`);
        setLogs(data);
      } catch (err: any) {
        setError(err.message || "Failed to load audit logs");
      } finally {
        setLoading(false);
      }
    };

    loadAuditLogs();
  }, [applicationId]);

  const getActorDetails = (actorType: string) => {
    switch (actorType) {
      case "CITIZEN": return { icon: User, color: "bg-blue-100 text-blue-700", label: "Citizen" };
      case "AI_AGENT": return { icon: Bot, color: "bg-purple-100 text-purple-700", label: "AI Agent" };
      case "SYSTEM": return { icon: Settings, color: "bg-slate-100 text-slate-700", label: "System" };
      case "GOVERNMENT_CONNECTOR": return { icon: Building, color: "bg-amber-100 text-amber-700", label: "Gov Connector" };
      default: return { icon: ShieldCheck, color: "bg-gray-100 text-gray-700", label: "Unknown" };
    }
  };

  const getActionDetails = (action: string) => {
    switch (action) {
      case "CREATE_APPLICATION": return { icon: FileText, color: "text-blue-500", label: "Created Application" };
      case "DOCUMENT_UPLOADED": return { icon: Upload, color: "text-blue-500", label: "Uploaded Document" };
      case "DOCUMENT_VERIFIED": return { icon: FileCheck, color: "text-emerald-500", label: "Verified Document" };
      case "WORKFLOW_STATE_CHANGE": return { icon: Settings, color: "text-slate-500", label: "Changed State" };
      case "REQUEST_CONSENT": return { icon: ShieldCheck, color: "text-purple-500", label: "Requested Consent" };
      case "CONSENT_APPROVED": return { icon: CheckCircle2, color: "text-emerald-600", label: "Approved Consent" };
      case "CONSENT_DENIED": return { icon: XCircle, color: "text-rose-500", label: "Denied Consent" };
      case "SUBMISSION_STARTED": return { icon: Loader2, color: "text-amber-500", label: "Started Submission" };
      case "GOVERNMENT_REFERENCE_RECEIVED": return { icon: Building, color: "text-amber-600", label: "Received Gov Reference" };
      case "SUBMIT_APPLICATION": return { icon: CheckCircle2, color: "text-emerald-600", label: "Application Submitted" };
      default: return { icon: FileText, color: "text-slate-500", label: action };
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] space-y-4">
        <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
        <p className="text-slate-500 font-medium">Loading immutable audit trail...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-rose-50 border border-rose-200 p-6 rounded-xl text-center">
        <AlertCircle className="h-8 w-8 text-rose-500 mx-auto mb-3" />
        <h3 className="text-rose-800 font-bold mb-1">Error Loading Logs</h3>
        <p className="text-rose-600 text-sm">{error}</p>
        <button 
          onClick={() => router.back()}
          className="mt-4 px-4 py-2 bg-white text-rose-700 text-sm font-semibold rounded-lg border border-rose-200"
        >
          Go Back
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center space-x-4">
        <button 
          onClick={() => router.back()}
          className="p-2 hover:bg-slate-100 rounded-lg transition"
        >
          <ArrowLeft className="h-5 w-5 text-slate-500" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Audit Trail</h1>
          <p className="text-sm text-slate-500 font-mono">APP ID: {applicationId}</p>
        </div>
      </div>

      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div className="space-y-8 relative before:absolute before:inset-0 before:ml-5 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-gradient-to-b before:from-transparent before:via-slate-200 before:to-transparent">
          
          {logs.map((log: any, index: number) => {
            const actor = getActorDetails(log.actor_type);
            const action = getActionDetails(log.action);
            const ActorIcon = actor.icon;
            const ActionIcon = action.icon;
            const date = new Date(log.created_at);

            return (
              <div key={log.id} className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group is-active">
                {/* Icon Marker */}
                <div className={`flex items-center justify-center w-10 h-10 rounded-full border-4 border-white ${actor.color} shadow shrink-0 md:order-1 md:group-odd:-translate-x-1/2 md:group-even:translate-x-1/2`}>
                  <ActorIcon className="h-4 w-4" />
                </div>
                
                {/* Card */}
                <div className="w-[calc(100%-4rem)] md:w-[calc(50%-2.5rem)] p-4 rounded-xl border border-slate-100 bg-slate-50 shadow-xs">
                  <div className="flex items-center justify-between mb-1">
                    <span className={`text-[10px] font-bold uppercase tracking-wider ${actor.color.replace('bg-', 'text-').replace('-100', '-600')}`}>
                      {actor.label}
                    </span>
                    <time className="text-[10px] text-slate-400 font-mono">
                      {format(date, "MMM d, yyyy HH:mm:ss")}
                    </time>
                  </div>
                  
                  <div className="flex items-start space-x-2">
                    <ActionIcon className={`h-4 w-4 mt-0.5 ${action.color}`} />
                    <div>
                      <h4 className="text-sm font-bold text-slate-800">{action.label}</h4>
                      
                      {/* Details block */}
                      {log.details && (
                        <div className="mt-2 text-xs font-mono bg-white p-2 rounded border border-slate-100 text-slate-600 break-words">
                          {Object.entries(log.details).map(([k, v]) => (
                            <div key={k}>
                              <span className="text-slate-400">{k}:</span> {String(v)}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
          
        </div>
      </div>
    </div>
  );
}
