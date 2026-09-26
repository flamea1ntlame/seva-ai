"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { fetchApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useEventContext } from "@/contexts/EventContext";
import ApplicationTimeline from "@/components/ApplicationTimeline";
import StatusBadge, { DocumentVerificationBadge } from "@/components/StatusBadge";
import DocumentChecklist from "@/components/DocumentChecklist";
import MissingDocumentsNotice from "@/components/MissingDocumentsNotice";
import DocumentUploader from "@/components/DocumentUploader";
import ApplicationPreview from "@/components/ApplicationPreview";
import {
  ArrowLeft,
  Building2,
  User,
  FileText,
  Loader2,
  Calendar,
  FileBadge2,
  Activity,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Send,
  Upload,
  Info,
  Layers,
  Clock,
} from "lucide-react";
import Link from "next/link";
import toast from "react-hot-toast";
import { getApplicationStatusInfo, humanizeKey } from "@/lib/statusMapping";

export default function ApplicationDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { user } = useAuth();
  const id = params.id as string;
  const { agentActivity } = useEventContext();

  const [application, setApplication] = useState<any>(null);
  const [requirements, setRequirements] = useState<any>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"preparation" | "preview" | "tracking">("preparation");
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadTargetType, setUploadTargetType] = useState<string>("identity_proof");
  const [isUploading, setIsUploading] = useState(false);

  const loadData = useCallback(async () => {
    if (!id) return;
    try {
      const [appData, logsData] = await Promise.all([
        fetchApi(`/api/applications/${id}`),
        fetchApi(`/api/applications/${id}/audit`).catch(() => []),
      ]);
      setApplication(appData);
      setLogs(Array.isArray(logsData) ? logsData : []);

      // If application has service code, fetch official requirements
      if (appData?.service?.code) {
        try {
          const reqsData = await fetchApi(`/api/services/${appData.service.code}/requirements`);
          setRequirements(reqsData);
        } catch {
          // Fallback to service model requirements
          setRequirements({
            required_documents: appData.service.required_documents || [],
            required_fields: appData.service.required_fields || [],
            fee_amount: appData.service.fee_amount || 0,
            processing_time_days: appData.service.processing_time_days || 7,
          });
        }
      }
    } catch (err) {
      console.error("Error loading application:", err);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadData();
  }, [loadData, agentActivity]);

  const handleUploadDocument = async (file: File, docType: string) => {
    if (!user) return;
    setIsUploading(true);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("document_type", docType);
    formData.append("citizen_id", user.id);
    formData.append("application_id", id);

    try {
      const token = localStorage.getItem("seva_token");
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/documents/upload`,
        {
          method: "POST",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: formData,
        }
      );

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: "Upload failed" }));
        throw new Error(errData.detail || "Upload failed");
      }

      toast.success("Document uploaded successfully.");
      setShowUploadModal(false);
      await loadData();
    } catch (err: any) {
      toast.error(err.message || "Failed to upload document.");
      throw err;
    } finally {
      setIsUploading(false);
    }
  };

  if (loading) {
    return (
      <div className="h-full py-24 flex flex-col items-center justify-center space-y-3">
        <Loader2 className="h-8 w-8 text-indigo-600 animate-spin" />
        <span className="text-xs text-slate-500 font-medium">Loading application workspace...</span>
      </div>
    );
  }

  if (!application) {
    return (
      <div className="text-center py-20 bg-white rounded-3xl border border-slate-200 p-8 max-w-md mx-auto">
        <AlertTriangle className="h-10 w-10 text-amber-500 mx-auto mb-3" />
        <h3 className="text-base font-bold text-slate-900 mb-1">Application Not Found</h3>
        <p className="text-xs text-slate-500 mb-4">
          The requested application could not be found or you do not have permission to view it.
        </p>
        <Link
          href="/applications"
          className="px-4 py-2 bg-indigo-600 text-white rounded-xl text-xs font-semibold"
        >
          Back to My Applications
        </Link>
      </div>
    );
  }

  const statusInfo = getApplicationStatusInfo(application.status, application.government_status);
  const isPostSubmission = ["SUBMITTED", "TRACKING", "COMPLETED"].includes(application.status);
  const isReadyForReview = ["READY_FOR_REVIEW", "CONSENT_REQUIRED"].includes(application.status);

  // Compute missing documents based on required documents vs provided
  const requiredTypes: string[] = requirements?.required_documents || application.service?.required_documents || [];
  const providedDocs = application.documents || [];
  const providedTypes = new Set(providedDocs.map((d: any) => d.document_type.toLowerCase()));
  const missingTypes = requiredTypes.filter((req) => !providedTypes.has(req.toLowerCase()));

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-16">
      
      {/* Back button */}
      <Link
        href="/applications"
        className="inline-flex items-center space-x-1.5 text-slate-500 hover:text-slate-900 transition text-xs font-semibold"
      >
        <ArrowLeft className="h-4 w-4" />
        <span>Back to Applications</span>
      </Link>

      {/* Main Header Banner */}
      <div className="bg-white rounded-3xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="bg-slate-900 px-6 sm:px-8 py-6 text-white flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-400 block">
              Official Application Workspace
            </span>
            <h1 className="text-2xl font-extrabold tracking-tight">
              {application.service?.title || "Application"}
            </h1>
            <div className="flex items-center space-x-2 text-slate-300 text-xs font-medium">
              <Building2 className="h-4 w-4 text-slate-400" />
              <span>{humanizeKey(application.service?.department || "")} Department</span>
            </div>
          </div>

          <div className="flex flex-col items-start md:items-end space-y-1.5">
            <span className="text-[10px] uppercase tracking-wider text-slate-400 font-bold">
              Application Reference Number
            </span>
            <div className="bg-white/10 border border-white/20 px-3 py-1.5 rounded-xl font-mono text-sm font-bold tracking-wide">
              {application.government_reference || application.application_number}
            </div>
          </div>
        </div>

        {/* Status Bar & Milestone Progression */}
        <div className="p-6 sm:p-8 border-b border-slate-100 bg-white space-y-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                Current Citizen Stage
              </span>
              <StatusBadge
                status={application.status}
                government_status={application.government_status}
                showStage
              />
            </div>

            <div className="space-y-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                {isPostSubmission ? "Submitted On" : "Started On"}
              </span>
              <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-700">
                <Calendar className="h-3.5 w-3.5 text-slate-400" />
                <span>{new Date(application.created_at).toLocaleDateString()}</span>
              </div>
            </div>

            {/* Quick Action button in header if review is ready */}
            {!isPostSubmission && isReadyForReview && (
              <button
                onClick={() => setActiveTab("preview")}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-bold transition flex items-center space-x-1.5 shadow-xs"
              >
                <span>Proceed to Review & Consent</span>
                <Send className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          {/* Timeline */}
          <ApplicationTimeline application={application} />
        </div>

        {/* Workspace Navigation Tabs */}
        <div className="flex border-b border-slate-200 bg-slate-50 px-6 sm:px-8">
          <button
            onClick={() => setActiveTab("preparation")}
            className={`py-3.5 px-4 text-xs font-bold uppercase tracking-wider border-b-2 transition ${
              activeTab === "preparation"
                ? "border-indigo-600 text-indigo-600 bg-white"
                : "border-transparent text-slate-500 hover:text-slate-900"
            }`}
          >
            1. Document Preparation & Rules
          </button>

          <button
            onClick={() => setActiveTab("preview")}
            className={`py-3.5 px-4 text-xs font-bold uppercase tracking-wider border-b-2 transition ${
              activeTab === "preview"
                ? "border-indigo-600 text-indigo-600 bg-white"
                : "border-transparent text-slate-500 hover:text-slate-900"
            }`}
          >
            2. Citizen Review & Consent
          </button>

          <button
            onClick={() => setActiveTab("tracking")}
            className={`py-3.5 px-4 text-xs font-bold uppercase tracking-wider border-b-2 transition ${
              activeTab === "tracking"
                ? "border-indigo-600 text-indigo-600 bg-white"
                : "border-transparent text-slate-500 hover:text-slate-900"
            }`}
          >
            3. Processing & Audit Log
          </button>
        </div>

      </div>

      {/* TAB 1: PREPARATION & CHECKLIST */}
      {activeTab === "preparation" && (
        <div className="space-y-6">
          
          {/* Prominent Missing Documents Alert */}
          <MissingDocumentsNotice
            missingDocuments={missingTypes}
            providedDocuments={providedDocs}
            onUploadAction={(type) => {
              setUploadTargetType(type || "identity_proof");
              setShowUploadModal(true);
            }}
          />

          {/* Readiness Banner */}
          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                Submission Readiness
              </span>
              <h3 className="text-sm font-bold text-slate-900">
                {isPostSubmission
                  ? "Application Already Submitted"
                  : isReadyForReview
                  ? "All Requirements Satisfied - Ready for Final Review"
                  : "Action Required Before Submission"}
              </h3>
              <p className="text-xs text-slate-500">
                {statusInfo.actionPrompt || statusInfo.description}
              </p>
            </div>

            {!isPostSubmission && (
              <button
                disabled={!isReadyForReview}
                onClick={() => setActiveTab("preview")}
                className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-200 disabled:text-slate-400 text-white text-xs font-bold rounded-xl transition flex items-center justify-center space-x-1.5 shrink-0"
              >
                <span>{isReadyForReview ? "Review & Sign Consent" : "Requirements Incomplete"}</span>
              </button>
            )}
          </div>

          {/* Centralized Document Checklist with authoritative rules */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-4">
            <DocumentChecklist
              requiredDocumentTypes={requiredTypes}
              documentOptions={requirements?.document_options || {}}
              linkedDocuments={providedDocs}
              onUploadClick={(type) => {
                setUploadTargetType(type);
                setShowUploadModal(true);
              }}
              readOnly={isPostSubmission}
            />
          </div>

          {/* Applicant Data extracted from documents */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-4">
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center space-x-2">
              <User className="h-4 w-4 text-indigo-600" />
              <span>Extracted Applicant Information</span>
            </h3>

            {application.form_data && Object.keys(application.form_data).length > 0 ? (
              <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-3">
                {Object.entries(application.form_data).map(([key, value]) => (
                  <div key={key} className="p-3 bg-slate-50 border border-slate-100 rounded-xl space-y-0.5">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                      {humanizeKey(key)}
                    </span>
                    <span className="text-xs font-semibold text-slate-900 block">
                      {String(value)}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500">
                Personal details will be extracted automatically when your documents are uploaded and verified.
              </p>
            )}
          </div>

        </div>
      )}

      {/* TAB 2: PREVIEW, CITIZEN REVIEW & CONSENT */}
      {activeTab === "preview" && (
        <div className="bg-white rounded-3xl border border-slate-200 shadow-xs overflow-hidden h-[750px]">
          <ApplicationPreview
            applicationId={id}
            onEdit={() => setActiveTab("preparation")}
            onBackToPreparation={() => setActiveTab("preparation")}
            onSubmitSuccess={() => {
              loadData();
              setActiveTab("tracking");
            }}
          />
        </div>
      )}

      {/* TAB 3: TRACKING & AUDIT TIMELINE */}
      {activeTab === "tracking" && (
        <div className="space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center space-x-2">
                <Activity className="h-4 w-4 text-indigo-600" />
                <span>Processing Status & Tracking Timeline</span>
              </h3>
              <span className="text-[10px] font-bold uppercase text-slate-400">
                {application.government_reference || application.application_number}
              </span>
            </div>

            <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 text-xs space-y-1">
              <span className="font-bold text-slate-900 block">Current Status Note</span>
              <p className="text-slate-600 leading-relaxed">
                {statusInfo.description}
              </p>
            </div>

            {/* Audit log trail */}
            {logs.length > 0 ? (
              <div className="space-y-3 pt-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                  Official Event History
                </span>
                <div className="space-y-2.5">
                  {logs.map((log: any) => (
                    <div
                      key={log.id}
                      className="p-3 bg-white border border-slate-200 rounded-xl flex items-center justify-between text-xs"
                    >
                      <div className="space-y-0.5">
                        <span className="font-bold text-slate-900 block">
                          {humanizeKey(log.action || "Activity")}
                        </span>
                        <span className="text-[10px] text-slate-400">
                          {new Date(log.created_at).toLocaleString()}
                        </span>
                      </div>
                      <span className="text-[10px] font-semibold text-slate-500 bg-slate-100 px-2 py-0.5 rounded-md">
                        Recorded
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-500 py-3">No additional activity logs recorded yet.</p>
            )}
          </div>
        </div>
      )}

      {/* Upload Document Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-lg w-full border border-slate-200 shadow-xl p-6 space-y-4 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                Upload Supporting Document
              </h3>
              <button
                onClick={() => setShowUploadModal(false)}
                className="text-xs font-bold text-slate-400 hover:text-slate-600"
              >
                ✕ Cancel
              </button>
            </div>

            <DocumentUploader
              defaultType={uploadTargetType}
              onUpload={async (file, type) => {
                await handleUploadDocument(file, type);
              }}
              onCancel={() => setShowUploadModal(false)}
            />
          </div>
        </div>
      )}

    </div>
  );
}
