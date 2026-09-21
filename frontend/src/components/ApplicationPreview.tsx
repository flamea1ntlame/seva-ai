"use client";

import React, { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";
import { FileText, User, ShieldAlert, CheckCircle2, Building2, Loader2, Edit3, Send } from "lucide-react";

interface ApplicationPreviewProps {
  applicationId: string;
  onEdit: () => void;
  onSubmitSuccess: (status: string, government_reference: string) => void;
}

export default function ApplicationPreview({ applicationId, onEdit, onSubmitSuccess }: ApplicationPreviewProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchApi(`/api/applications/${applicationId}/preview`)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [applicationId]);

  const handleApproveAndSubmit = async () => {
    if (!data?.consent_id) {
      setError("No pending consent found for this application.");
      return;
    }
    
    setSubmitting(true);
    setError(null);
    try {
      // Respond to the existing pending consent (which triggers submission internally)
      const res = await fetchApi(`/api/consents/${data.consent_id}/respond`, {
        method: "POST",
        body: JSON.stringify({ action: "approve" }),
      });

      if (res.status === "APPROVED" && res.submission_result) {
        onSubmitSuccess(res.submission_result.status, res.submission_result.government_reference);
      } else {
        throw new Error("Submission failed or consent was not approved.");
      }
    } catch (err: any) {
      setError(err.message || "Failed to submit application");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center space-y-4 h-full bg-brand-50">
        <Loader2 className="h-8 w-8 text-primary-500 animate-spin" />
        <span className="text-sm font-medium text-brand-600 animate-pulse">Preparing your application preview...</span>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex-1 flex items-center justify-center p-6 h-full bg-brand-50">
        <div className="bg-error-50 text-error-800 p-4 rounded-xl border border-error-200 text-sm max-w-sm text-center">
          {error || "Failed to load application data"}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-brand-50 relative">
      {/* Header */}
      <div className="bg-white border-b border-brand-200 px-6 py-5">
        <h2 className="text-lg font-bold text-brand-900 mb-1">Review Your Application</h2>
        <div className="flex items-center space-x-2 text-xs font-medium text-brand-500">
          <span className="text-primary-600">{data.service?.title}</span>
          <span>•</span>
          <span className="uppercase tracking-wider">{data.service?.department} Dept</span>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        
        {/* Consent Warning Panel */}
        <div className="bg-white border border-brand-200 rounded-xl p-5 shadow-sm">
          <div className="flex items-start space-x-3">
            <div className="h-10 w-10 bg-primary-50 rounded-lg flex items-center justify-center shrink-0 border border-primary-100 mt-1">
              <ShieldAlert className="h-5 w-5 text-primary-600" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-brand-900 mb-1">Data Sharing Consent</h3>
              <p className="text-xs text-brand-600 leading-relaxed mb-3">
                Before submitting, SEVA requires your consent to share the following verified information with the <strong>{data.service?.department} Department</strong> for the purpose of processing your <strong>{data.service?.title}</strong>.
              </p>
              
              <div className="bg-brand-50 rounded-lg p-3 border border-brand-100">
                <span className="text-[10px] font-bold text-brand-500 uppercase tracking-wider mb-2 block">Data To Be Shared</span>
                <div className="flex flex-wrap gap-2">
                  {Object.keys(data.form_data || {}).map(key => (
                    <span key={key} className="text-xs font-medium bg-white border border-brand-200 px-2 py-1 rounded-md text-brand-700 capitalize">
                      {key.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Application Data Snapshot */}
        <div className="grid md:grid-cols-2 gap-6">
          <div className="space-y-3">
            <h4 className="text-xs font-bold text-brand-700 uppercase tracking-wider flex items-center space-x-1.5">
              <User className="h-4 w-4" />
              <span>Personal Information</span>
            </h4>
            <div className="bg-white rounded-xl border border-brand-200 shadow-sm divide-y divide-brand-100">
              {Object.entries(data.form_data || {}).map(([key, value]) => (
                <div key={key} className="px-4 py-3 flex flex-col sm:flex-row sm:justify-between sm:items-center">
                  <span className="text-[11px] text-brand-500 uppercase font-bold">{key.replace(/_/g, ' ')}</span>
                  <span className="text-sm font-medium text-brand-900 mt-1 sm:mt-0 text-right">{String(value)}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-3">
            <h4 className="text-xs font-bold text-brand-700 uppercase tracking-wider flex items-center space-x-1.5">
              <FileText className="h-4 w-4" />
              <span>Verified Documents</span>
            </h4>
            <div className="space-y-2">
              {data.documents?.map((doc: any) => (
                <div key={doc.id} className="bg-white rounded-xl border border-brand-200 p-3 shadow-sm flex items-center justify-between">
                  <div>
                    <p className="text-xs font-bold text-brand-900 line-clamp-1">{doc.title}</p>
                    <p className="text-[10px] text-brand-500 uppercase mt-0.5">{doc.document_type.replace(/_/g, ' ')}</p>
                  </div>
                  <CheckCircle2 className="h-4 w-4 text-success-500 shrink-0" />
                </div>
              ))}
            </div>
          </div>
        </div>

      </div>

      {/* Footer Actions */}
      <div className="bg-white border-t border-brand-200 p-4 px-6 flex flex-col sm:flex-row justify-between items-center space-y-3 sm:space-y-0 shadow-lg relative z-10">
        <button
          onClick={onEdit}
          disabled={submitting}
          className="w-full sm:w-auto px-5 py-2.5 text-sm font-bold text-brand-600 hover:text-brand-900 bg-brand-50 hover:bg-brand-100 border border-brand-200 rounded-xl transition-colors disabled:opacity-50 flex items-center justify-center space-x-2"
        >
          <Edit3 className="h-4 w-4" />
          <span>Go Back & Edit</span>
        </button>

        <button
          onClick={handleApproveAndSubmit}
          disabled={submitting}
          className="w-full sm:w-auto px-6 py-2.5 text-sm font-bold text-white bg-primary-600 hover:bg-primary-700 rounded-xl shadow-md hover:shadow-lg transition-all disabled:opacity-50 flex items-center justify-center space-x-2"
        >
          {submitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Submitting...</span>
            </>
          ) : (
            <>
              <span>Approve & Submit</span>
              <Send className="h-4 w-4" />
            </>
          )}
        </button>
      </div>
    </div>
  );
}
