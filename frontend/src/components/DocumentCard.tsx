import React from "react";
import { FileText, CheckCircle2, Clock, Share2, ShieldAlert } from "lucide-react";

export default function DocumentCard({ doc }: { doc: any }) {
  const isVerified = doc.verification_status === "VERIFIED";
  const isFailed = doc.verification_status === "FAILED";

  return (
    <div className="bg-white p-4 rounded-xl border border-brand-200 shadow-xs flex flex-col h-full group hover:border-primary-200 transition-colors">
      <div className="flex justify-between items-start mb-3">
        <div className="flex items-center space-x-3">
          <div className={`h-10 w-10 rounded-lg flex items-center justify-center shrink-0 ${isVerified ? 'bg-success-50 text-success-600' : (isFailed ? 'bg-error-50 text-error-600' : 'bg-brand-50 text-brand-500')}`}>
            <FileText className="h-5 w-5" />
          </div>
          <div>
            <span className="font-bold text-sm text-brand-900 line-clamp-1" title={doc.title}>
              {doc.title}
            </span>
            <span className="text-[10px] uppercase tracking-wider font-bold text-brand-500">
              {doc.document_type.replace(/_/g, ' ')}
            </span>
          </div>
        </div>
      </div>

      <div className="mt-auto space-y-3">
        {doc.extracted_data && isVerified && (
          <div className="bg-brand-50 p-2.5 rounded-lg text-[10px] font-mono text-brand-600 border border-brand-100 space-y-1">
            {Object.entries(doc.extracted_data).slice(0, 3).map(([k, v]) => (
              <div key={k} className="flex justify-between">
                <span className="text-brand-400 capitalize">{k.replace(/_/g, ' ')}:</span> 
                <span className="text-brand-800 font-bold text-right truncate ml-2">{String(v)}</span>
              </div>
            ))}
            {Object.keys(doc.extracted_data).length > 3 && (
              <div className="text-center text-brand-400 pt-1 border-t border-brand-200 mt-1">
                + {Object.keys(doc.extracted_data).length - 3} more fields
              </div>
            )}
          </div>
        )}

        <div className="flex justify-between items-center pt-2 border-t border-brand-100">
          <span className="text-[10px] text-brand-400">
            {new Date(doc.created_at).toLocaleDateString()}
          </span>
          {isVerified ? (
            <span className="text-[10px] font-bold text-success-700 bg-success-50 border border-success-200 px-2 py-0.5 rounded-full flex items-center space-x-1">
              <CheckCircle2 className="h-3 w-3" />
              <span>Verified</span>
            </span>
          ) : isFailed ? (
            <span className="text-[10px] font-bold text-error-700 bg-error-50 border border-error-200 px-2 py-0.5 rounded-full flex items-center space-x-1">
              <ShieldAlert className="h-3 w-3" />
              <span>Failed</span>
            </span>
          ) : (
            <span className="text-[10px] font-bold text-brand-600 bg-brand-50 border border-brand-200 px-2 py-0.5 rounded-full flex items-center space-x-1">
              <Clock className="h-3 w-3" />
              <span>Pending</span>
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
