"use client";

import React from "react";
import { AlertTriangle, CheckCircle2, Clock, FileWarning, ArrowRight } from "lucide-react";
import { humanizeKey } from "@/lib/statusMapping";

interface MissingDocumentsNoticeProps {
  missingDocuments?: string[];
  providedDocuments?: Array<{
    id: string;
    document_type: string;
    title?: string;
    verification_status: string;
    verified?: boolean;
  }>;
  onUploadAction?: (documentType?: string) => void;
  className?: string;
}

export default function MissingDocumentsNotice({
  missingDocuments = [],
  providedDocuments = [],
  onUploadAction,
  className = "",
}: MissingDocumentsNoticeProps) {
  const hasMissing = missingDocuments.length > 0;

  // Filter provided docs that need review
  const needsReviewDocs = providedDocuments.filter(
    (d) => d.verification_status === "NEEDS_REVIEW" || d.verification_status === "REJECTED"
  );

  if (!hasMissing && needsReviewDocs.length === 0) {
    return (
      <div className={`p-4 bg-emerald-50 border border-emerald-200 rounded-2xl ${className}`}>
        <div className="flex items-center space-x-3">
          <div className="h-8 w-8 rounded-xl bg-emerald-100 border border-emerald-200 flex items-center justify-center text-emerald-700 shrink-0">
            <CheckCircle2 className="h-4 w-4" />
          </div>
          <div>
            <h4 className="text-xs font-bold text-emerald-900 uppercase tracking-wider">
              All Mandatory Documents Provided
            </h4>
            <p className="text-xs text-emerald-700 mt-0.5">
              You have supplied all required documents according to authoritative rules.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`bg-white border-2 border-amber-300 rounded-2xl p-5 shadow-xs space-y-4 ${className}`}>
      
      {/* Prominent Header */}
      <div className="flex items-start space-x-3">
        <div className="h-9 w-9 rounded-xl bg-amber-100 border border-amber-200 flex items-center justify-center text-amber-700 shrink-0 mt-0.5">
          <AlertTriangle className="h-5 w-5" />
        </div>
        <div className="flex-1">
          <span className="text-[10px] font-extrabold uppercase tracking-widest text-amber-700 block">
            Application Requirement Alert
          </span>
          <h3 className="text-sm sm:text-base font-extrabold text-slate-900">
            What am I still missing?
          </h3>
          <p className="text-xs text-slate-600 mt-0.5">
            Your application cannot be submitted until the following items are provided and verified.
          </p>
        </div>
      </div>

      {/* Missing items list */}
      {hasMissing && (
        <div className="space-y-2">
          <span className="text-[11px] font-bold uppercase tracking-wider text-rose-600 block">
            Required Documents Not Yet Provided ({missingDocuments.length})
          </span>
          <div className="grid sm:grid-cols-2 gap-2">
            {missingDocuments.map((docType) => (
              <div
                key={docType}
                className="flex items-center justify-between p-3 rounded-xl bg-rose-50/70 border border-rose-200"
              >
                <div className="flex items-center space-x-2">
                  <FileWarning className="h-4 w-4 text-rose-600 shrink-0" />
                  <span className="text-xs font-bold text-rose-900">
                    {humanizeKey(docType)}
                  </span>
                </div>
                {onUploadAction && (
                  <button
                    onClick={() => onUploadAction(docType)}
                    className="text-[11px] font-bold text-indigo-700 hover:text-indigo-900 flex items-center space-x-0.5 bg-white px-2 py-1 rounded-md border border-indigo-200"
                  >
                    <span>Upload</span>
                    <ArrowRight className="h-3 w-3" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Items requiring review or rejected */}
      {needsReviewDocs.length > 0 && (
        <div className="space-y-2 pt-2 border-t border-slate-100">
          <span className="text-[11px] font-bold uppercase tracking-wider text-amber-700 block">
            Documents Requiring Attention ({needsReviewDocs.length})
          </span>
          <div className="space-y-2">
            {needsReviewDocs.map((doc) => (
              <div
                key={doc.id}
                className="flex items-center justify-between p-3 rounded-xl bg-amber-50/70 border border-amber-200"
              >
                <div className="space-y-0.5">
                  <span className="text-xs font-bold text-amber-900 block">
                    {doc.title || humanizeKey(doc.document_type)}
                  </span>
                  <span className="text-[11px] text-amber-700">
                    Status: {doc.verification_status === "REJECTED" ? "Rejected - Please re-upload" : "Needs Review"}
                  </span>
                </div>
                {onUploadAction && (
                  <button
                    onClick={() => onUploadAction(doc.document_type)}
                    className="text-[11px] font-bold text-amber-900 bg-white px-2.5 py-1 rounded-md border border-amber-300 hover:bg-amber-100"
                  >
                    Replace / Re-upload
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Provided and Validated preview */}
      {providedDocuments.length > 0 && (
        <div className="pt-2 border-t border-slate-100">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500 block mb-2">
            Already Provided ({providedDocuments.length})
          </span>
          <div className="flex flex-wrap gap-2">
            {providedDocuments.map((doc) => (
              <span
                key={doc.id}
                className="inline-flex items-center space-x-1.5 text-xs bg-slate-50 border border-slate-200 px-2.5 py-1 rounded-lg text-slate-700"
              >
                {doc.verification_status === "VERIFIED" ? (
                  <CheckCircle2 className="h-3 w-3 text-emerald-600" />
                ) : (
                  <Clock className="h-3 w-3 text-amber-500" />
                )}
                <span className="font-medium">{doc.title || humanizeKey(doc.document_type)}</span>
              </span>
            ))}
          </div>
        </div>
      )}

    </div>
  );
}
