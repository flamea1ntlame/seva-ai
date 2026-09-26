"use client";

import React, { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";
import {
  FileText,
  User,
  ShieldCheck,
  CheckCircle2,
  Building2,
  Loader2,
  Edit3,
  Send,
  AlertTriangle,
  AlertCircle,
  Lock,
  Calendar,
  CheckSquare,
  Square,
  Clock,
  Info,
} from "lucide-react";
import { DocumentVerificationBadge } from "@/components/StatusBadge";
import { humanizeKey } from "@/lib/statusMapping";

interface ApplicationPreviewProps {
  applicationId: string;
  onEdit?: () => void;
  onSubmitSuccess?: (status: string, government_reference: string) => void;
  onBackToPreparation?: () => void;
}

export default function ApplicationPreview({
  applicationId,
  onEdit,
  onSubmitSuccess,
  onBackToPreparation,
}: ApplicationPreviewProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [consentAgreed, setConsentAgreed] = useState(false);
  const [submissionComplete, setSubmissionComplete] = useState(false);
  const [referenceNumber, setReferenceNumber] = useState<string | null>(null);

  useEffect(() => {
    fetchApi(`/api/applications/${applicationId}/preview`)
      .then(setData)
      .catch((err) => setError(err.message || "Failed to load application preview."))
      .finally(() => setLoading(false));
  }, [applicationId]);

  const handleApproveAndSubmit = async () => {
    if (!consentAgreed) {
      setError("Please check the declaration box to authorize submission.");
      return;
    }

    if (!data?.consent_id) {
      setError("No pending consent authorization found for this application. Please ensure all documents are ready.");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      // Respond to pending consent record (backend approves consent and initiates departmental dispatch)
      const res = await fetchApi(`/api/consents/${data.consent_id}/respond`, {
        method: "POST",
        body: JSON.stringify({ action: "approve" }),
      });

      if (res.status === "APPROVED" && res.submission_result) {
        setSubmissionComplete(true);
        const ref = res.submission_result.government_reference || data.application_number;
        setReferenceNumber(ref);
        if (onSubmitSuccess) {
          onSubmitSuccess(res.submission_result.status, ref);
        }
      } else {
        throw new Error("Department portal did not accept the submission. Please retry.");
      }
    } catch (err: any) {
      setError(err.message || "Submission failed due to a network or authority issue. Please retry.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center space-y-3 h-full bg-slate-50 p-12">
        <Loader2 className="h-8 w-8 text-indigo-600 animate-spin" />
        <span className="text-xs font-semibold text-slate-600 animate-pulse">
          Generating human-readable application preview...
        </span>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="flex-1 flex items-center justify-center p-6 h-full bg-slate-50">
        <div className="bg-rose-50 text-rose-800 p-6 rounded-2xl border border-rose-200 text-xs max-w-md text-center space-y-3">
          <AlertTriangle className="h-6 w-6 text-rose-600 mx-auto" />
          <p className="font-semibold">{error}</p>
          {onBackToPreparation && (
            <button
              onClick={onBackToPreparation}
              className="px-4 py-2 bg-white text-slate-700 border border-slate-200 rounded-xl font-bold"
            >
              Return to Preparation
            </button>
          )}
        </div>
      </div>
    );
  }

  // After Submission Confirmation View
  if (submissionComplete) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 bg-emerald-50/40 text-center space-y-4 h-full">
        <div className="h-16 w-16 bg-emerald-100 rounded-2xl flex items-center justify-center text-emerald-600 mx-auto border border-emerald-200">
          <CheckCircle2 className="h-8 w-8" />
        </div>
        <div className="space-y-1 max-w-md">
          <span className="text-[10px] font-bold uppercase tracking-widest text-emerald-700">
            Submission Confirmed
          </span>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">
            Application Submitted Successfully
          </h2>
          <p className="text-xs text-slate-600 leading-relaxed">
            Your application for <strong>{data.service?.title}</strong> has been transmitted to the{" "}
            <strong>{data.service?.department} Department</strong>.
          </p>
        </div>

        <div className="p-4 bg-white border border-emerald-200 rounded-2xl shadow-xs max-w-sm w-full space-y-1">
          <span className="text-[10px] uppercase font-bold text-slate-400 block tracking-wider">
            Government Reference Number
          </span>
          <span className="text-base font-extrabold text-slate-900 font-mono tracking-wide">
            {referenceNumber}
          </span>
        </div>

        <p className="text-xs text-slate-500 max-w-sm">
          You can track officer review milestones and download the official certificate upon completion.
        </p>
      </div>
    );
  }

  // Application formData formatted cleanly
  const formData = data.form_data || {};
  const formEntries = Object.entries(formData);

  return (
    <div className="flex flex-col h-full bg-slate-50 relative overflow-hidden">
      
      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-6 py-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-600 block">
              Official Review & Consent
            </span>
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">
              Application Preview: {data.service?.title}
            </h2>
          </div>
          <div className="text-right">
            <span className="text-[10px] uppercase tracking-wider text-slate-400 font-bold block">
              Issuing Department
            </span>
            <span className="text-xs font-bold text-slate-700 uppercase">
              {humanizeKey(data.service?.department || "")} Department
            </span>
          </div>
        </div>
      </div>

      {/* Main scrollable body */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        
        {/* Error message banner if submit attempt failed */}
        {error && (
          <div className="p-4 bg-rose-50 border border-rose-200 text-rose-800 text-xs rounded-xl flex items-start space-x-2">
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-600 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* 1. Applicant & Extracted Information Snapshot */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs space-y-4">
          <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center space-x-2">
            <User className="h-4 w-4 text-indigo-600" />
            <span>Declared Applicant Information</span>
          </h3>

          {formEntries.length > 0 ? (
            <div className="grid sm:grid-cols-2 gap-3 text-xs">
              {formEntries.map(([key, value]) => (
                <div key={key} className="p-3 bg-slate-50 border border-slate-100 rounded-xl space-y-0.5">
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                    {humanizeKey(key)}
                  </span>
                  <span className="text-xs font-semibold text-slate-900 block">
                    {String(value)}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-3 bg-slate-50 border border-slate-100 rounded-xl text-xs text-slate-500">
              Personal and demographic details extracted directly from verified documents.
            </div>
          )}
        </div>

        {/* 2. Attached Verified Documents */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs space-y-4">
          <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center space-x-2">
            <FileText className="h-4 w-4 text-indigo-600" />
            <span>Attached Verification Documents ({data.documents?.length || 0})</span>
          </h3>

          {data.documents && data.documents.length > 0 ? (
            <div className="grid sm:grid-cols-2 gap-3">
              {data.documents.map((doc: any) => (
                <div
                  key={doc.id}
                  className="p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between"
                >
                  <div className="space-y-0.5">
                    <span className="text-xs font-bold text-slate-900 block line-clamp-1">
                      {doc.title}
                    </span>
                    <span className="text-[10px] uppercase font-bold text-slate-500">
                      {humanizeKey(doc.document_type)}
                    </span>
                  </div>
                  <DocumentVerificationBadge
                    verification_status={doc.verification_status}
                    verified={doc.verified}
                  />
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500">No documents attached.</p>
          )}
        </div>

        {/* 3. Statutory Consent & Citizen Declaration */}
        <div className="bg-white border-2 border-indigo-200 rounded-2xl p-5 shadow-xs space-y-4">
          <div className="flex items-start space-x-3">
            <div className="h-9 w-9 bg-indigo-50 border border-indigo-100 rounded-xl flex items-center justify-center text-indigo-600 shrink-0 mt-0.5">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div className="space-y-1">
              <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                Statutory Citizen Declaration & Consent
              </h3>
              <p className="text-xs text-slate-600 leading-relaxed">
                By submitting this application, you authorize SEVA AI to transmit your verified identity,
                address, and supporting documents to the <strong>{humanizeKey(data.service?.department || "")} Department</strong> solely
                for the processing of your <strong>{data.service?.title}</strong>.
              </p>
            </div>
          </div>

          <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-700 space-y-1.5">
            <p className="font-semibold text-slate-800">Legal Declaration:</p>
            <p className="italic text-slate-600">
              "I solemnly declare that the information provided herein and in the attached supporting documents is true and correct to the best of my knowledge. I understand that submitting false or misleading information is punishable under applicable laws."
            </p>
          </div>

          {/* Explicit user action required */}
          <div
            onClick={() => setConsentAgreed(!consentAgreed)}
            className="flex items-start space-x-3 p-3 rounded-xl border border-indigo-100 bg-indigo-50/50 cursor-pointer hover:bg-indigo-50 transition"
          >
            <div className="mt-0.5 shrink-0 text-indigo-600">
              {consentAgreed ? (
                <CheckSquare className="h-5 w-5 text-indigo-600" />
              ) : (
                <Square className="h-5 w-5 text-slate-400" />
              )}
            </div>
            <span className="text-xs font-semibold text-slate-900 select-none">
              I have verified all the details above and give my explicit consent to submit this application.
            </span>
          </div>
        </div>

      </div>

      {/* Footer Submission Actions */}
      <div className="bg-white border-t border-slate-200 p-4 px-6 flex flex-col sm:flex-row justify-between items-center gap-3 shadow-lg relative z-10">
        <button
          onClick={onEdit || onBackToPreparation}
          disabled={submitting}
          className="w-full sm:w-auto px-5 py-2.5 text-xs font-bold text-slate-700 bg-slate-100 hover:bg-slate-200 border border-slate-200 rounded-xl transition disabled:opacity-50 flex items-center justify-center space-x-2"
        >
          <Edit3 className="h-4 w-4" />
          <span>Return & Edit Information</span>
        </button>

        <button
          onClick={handleApproveAndSubmit}
          disabled={submitting || !consentAgreed}
          className="w-full sm:w-auto px-6 py-2.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 rounded-xl shadow-xs transition flex items-center justify-center space-x-2 disabled:cursor-not-allowed"
        >
          {submitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Transmitting to Department...</span>
            </>
          ) : (
            <>
              <span>Authorize & Submit Application</span>
              <Send className="h-4 w-4" />
            </>
          )}
        </button>
      </div>
    </div>
  );
}
