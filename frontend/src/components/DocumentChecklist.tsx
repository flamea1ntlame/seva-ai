"use client";

import React from "react";
import {
  CheckCircle2,
  AlertTriangle,
  Clock,
  XCircle,
  FileQuestion,
  HelpCircle,
  Upload,
  ShieldCheck,
  Info,
  Layers,
} from "lucide-react";
import { DocumentVerificationBadge } from "@/components/StatusBadge";
import { humanizeKey } from "@/lib/statusMapping";

export interface DocumentOption {
  name: string;
  authority?: string;
  digital_verify?: boolean;
}

export interface DocumentRequirementRule {
  type: string;
  name?: string;
  description?: string;
  options?: DocumentOption[];
  isMandatory?: boolean;
}

export interface LinkedDocument {
  id: string;
  document_type: string;
  title: string;
  verified: boolean;
  verification_status: string;
  file_size?: number;
  mime_type?: string;
  created_at?: string;
}

interface DocumentChecklistProps {
  requiredDocumentTypes?: string[];
  documentOptions?: Record<string, DocumentOption[]>;
  linkedDocuments?: LinkedDocument[];
  onUploadClick?: (documentType: string) => void;
  readOnly?: boolean;
}

export default function DocumentChecklist({
  requiredDocumentTypes = [],
  documentOptions = {},
  linkedDocuments = [],
  onUploadClick,
  readOnly = false,
}: DocumentChecklistProps) {
  
  // Categorize requirements based on linked documents
  const items = requiredDocumentTypes.map((reqType) => {
    // Check if citizen provided this document type
    const matches = linkedDocuments.filter(
      (d) => d.document_type.toLowerCase() === reqType.toLowerCase()
    );

    const provided = matches.length > 0;
    const primaryDoc = provided ? matches[0] : null;
    const isVerified = primaryDoc?.verification_status === "VERIFIED" || primaryDoc?.verified === true;
    const needsReview = primaryDoc?.verification_status === "NEEDS_REVIEW";
    const isRejected = primaryDoc?.verification_status === "REJECTED";
    const isPending = provided && !isVerified && !needsReview && !isRejected;

    const alternatives = documentOptions[reqType] || [];

    // Why is this document required (backend explanation / humanized meaning)
    let whyRequired = `Official proof required by department rules to verify eligibility for ${humanizeKey(reqType)}.`;
    if (reqType.includes("identity")) {
      whyRequired = "Required to verify applicant identity against official records.";
    } else if (reqType.includes("address")) {
      whyRequired = "Required to confirm residential jurisdiction and local eligibility.";
    } else if (reqType.includes("income")) {
      whyRequired = "Authoritative evidence of annual family earnings to assess scheme eligibility.";
    } else if (reqType.includes("hospital") || reqType.includes("birth")) {
      whyRequired = "Institutional birth notification or discharge summary confirming birth event.";
    } else if (reqType.includes("parent")) {
      whyRequired = "Identity proof of child's father or mother (child's identity cannot satisfy this).";
    }

    return {
      type: reqType,
      name: humanizeKey(reqType),
      whyRequired,
      alternatives,
      provided,
      primaryDoc,
      isVerified,
      needsReview,
      isRejected,
      isPending,
      satisfiesRequirement: isVerified,
    };
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center space-x-2">
            <ShieldCheck className="h-4 w-4 text-indigo-600" />
            <span>Document Checklist & Verification Status</span>
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Official checklist required for government validation.
          </p>
        </div>
      </div>

      <div className="space-y-3">
        {items.map((item) => (
          <div
            key={item.type}
            className={`bg-white rounded-2xl border transition-all p-5 shadow-xs ${
              item.isVerified
                ? "border-emerald-200 bg-emerald-50/20"
                : item.needsReview || item.isRejected
                ? "border-amber-300 bg-amber-50/20"
                : item.provided
                ? "border-blue-200 bg-blue-50/10"
                : "border-slate-200 hover:border-slate-300"
            }`}
          >
            <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
              
              {/* Left Column: Document Name, Purpose & Satisfaction */}
              <div className="space-y-2 flex-1">
                <div className="flex items-center flex-wrap gap-2">
                  <span className="text-sm font-bold text-slate-900">
                    {item.name}
                  </span>

                  <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-slate-100 text-slate-600">
                    Required
                  </span>

                  {item.provided ? (
                    <DocumentVerificationBadge
                      verification_status={item.primaryDoc?.verification_status}
                      verified={item.isVerified}
                    />
                  ) : (
                    <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider bg-rose-50 text-rose-700 border border-rose-200">
                      <XCircle className="h-3 w-3" />
                      <span>Missing</span>
                    </span>
                  )}
                </div>

                {/* Explanation: Why it is required */}
                <p className="text-xs text-slate-600 leading-relaxed">
                  {item.whyRequired}
                </p>

                {/* Acceptable Alternatives from Rules Engine */}
                {item.alternatives.length > 0 && (
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 space-y-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 flex items-center space-x-1">
                      <Layers className="h-3 w-3" />
                      <span>Acceptable Document Options</span>
                    </span>
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {item.alternatives.map((alt, i) => (
                        <span
                          key={i}
                          className="text-[11px] bg-white border border-slate-200 px-2 py-0.5 rounded-md text-slate-700 font-medium"
                          title={alt.authority ? `Issuing Body: ${alt.authority}` : ""}
                        >
                          {alt.name}
                          {alt.digital_verify && " (Instant Verification)"}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Provided Document Details */}
                {item.provided && item.primaryDoc && (
                  <div className="text-xs text-slate-500 pt-1 flex items-center space-x-2">
                    <span className="font-semibold text-slate-700">Uploaded File:</span>
                    <span className="font-mono text-slate-800">{item.primaryDoc.title}</span>
                  </div>
                )}
              </div>

              {/* Right Column: Citizen Actions */}
              <div className="flex flex-col items-end justify-center shrink-0 space-y-2">
                {!readOnly && onUploadClick && (
                  <div>
                    {item.provided ? (
                      <button
                        onClick={() => onUploadClick(item.type)}
                        className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-xl border border-slate-200 transition flex items-center space-x-1.5"
                      >
                        <Upload className="h-3.5 w-3.5" />
                        <span>Re-upload / Replace</span>
                      </button>
                    ) : (
                      <button
                        onClick={() => onUploadClick(item.type)}
                        className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-xl shadow-xs transition flex items-center space-x-1.5"
                      >
                        <Upload className="h-3.5 w-3.5" />
                        <span>Upload {item.name}</span>
                      </button>
                    )}
                  </div>
                )}

                {/* Citizen-safe explanation note */}
                {item.isVerified && (
                  <span className="text-[11px] font-semibold text-emerald-700 flex items-center space-x-1">
                    <CheckCircle2 className="h-3 w-3" />
                    <span>Satisfies Requirement</span>
                  </span>
                )}
                {item.needsReview && (
                  <span className="text-[11px] font-semibold text-amber-700 flex items-center space-x-1">
                    <AlertTriangle className="h-3 w-3" />
                    <span>Attention Required</span>
                  </span>
                )}
              </div>

            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
