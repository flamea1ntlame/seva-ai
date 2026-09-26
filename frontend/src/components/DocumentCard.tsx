"use client";

import React from "react";
import { FileText, Calendar } from "lucide-react";
import { DocumentVerificationBadge } from "./StatusBadge";
import { humanizeKey } from "@/lib/statusMapping";

export default function DocumentCard({ doc }: { doc: any }) {
  const isVerified = doc.verification_status === "VERIFIED" || doc.verified === true;

  return (
    <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex flex-col h-full group hover:border-indigo-200 hover:shadow-sm transition-all">
      <div className="flex justify-between items-start mb-3">
        <div className="flex items-center space-x-3">
          <div
            className={`h-10 w-10 rounded-xl flex items-center justify-center shrink-0 border ${
              isVerified
                ? "bg-emerald-50 text-emerald-600 border-emerald-100"
                : "bg-slate-50 text-slate-500 border-slate-200"
            }`}
          >
            <FileText className="h-5 w-5" />
          </div>
          <div>
            <span className="font-bold text-xs sm:text-sm text-slate-900 line-clamp-1" title={doc.title}>
              {doc.title}
            </span>
            <span className="text-[10px] uppercase tracking-wider font-bold text-slate-400">
              {humanizeKey(doc.document_type || "Document")}
            </span>
          </div>
        </div>
      </div>

      <div className="mt-auto space-y-3">
        {doc.extracted_data && isVerified && (
          <div className="bg-slate-50 p-2.5 rounded-xl text-[10px] text-slate-600 border border-slate-100 space-y-1">
            <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
              Extracted Facts
            </span>
            {Object.entries(doc.extracted_data).slice(0, 3).map(([k, v]) => (
              <div key={k} className="flex justify-between">
                <span className="text-slate-500 font-medium capitalize">{humanizeKey(k)}:</span>
                <span className="text-slate-900 font-semibold text-right truncate ml-2">
                  {String(v)}
                </span>
              </div>
            ))}
            {Object.keys(doc.extracted_data).length > 3 && (
              <div className="text-center text-slate-400 pt-1 border-t border-slate-200 mt-1">
                + {Object.keys(doc.extracted_data).length - 3} more verified fields
              </div>
            )}
          </div>
        )}

        <div className="flex justify-between items-center pt-3 border-t border-slate-100">
          <div className="flex items-center space-x-1 text-[11px] text-slate-400">
            <Calendar className="h-3 w-3" />
            <span>{new Date(doc.created_at).toLocaleDateString()}</span>
          </div>

          <DocumentVerificationBadge
            verification_status={doc.verification_status}
            verified={doc.verified}
          />
        </div>
      </div>
    </div>
  );
}
