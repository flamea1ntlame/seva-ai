"use client";

import React, { useRef, useState } from "react";
import {
  Upload,
  X,
  Loader2,
  FileUp,
  CheckCircle2,
  AlertCircle,
  RotateCcw,
  FileText,
  Clock,
  ShieldCheck,
} from "lucide-react";
import { DocumentVerificationBadge } from "@/components/StatusBadge";
import { humanizeKey } from "@/lib/statusMapping";

export interface UploadStage {
  step: "idle" | "uploading" | "extracting" | "success" | "error";
  fileName?: string;
  fileSize?: number;
  documentType?: string;
  verificationStatus?: string;
  errorMessage?: string;
}

interface DocumentUploaderProps {
  onUpload: (file: File, type: string) => Promise<any>;
  uploading?: boolean;
  defaultType?: string;
  allowedTypes?: Array<{ value: string; label: string }>;
  onCancel?: () => void;
}

const DEFAULT_DOC_TYPES = [
  { value: "identity_proof", label: "Identity Proof (Aadhaar / Voter ID / Passport)" },
  { value: "income_proof", label: "Income Proof (Salary Slip / Form 16 / ITR)" },
  { value: "address_proof", label: "Address Proof (Utility Bill / Domicile)" },
  { value: "hospital_certificate", label: "Hospital Birth Certificate" },
  { value: "medical_declaration", label: "Medical Fitness Declaration" },
  { value: "parent_identity_proof", label: "Parent's Identity Proof" },
  { value: "photograph", label: "Passport Photograph" },
];

export default function DocumentUploader({
  onUpload,
  uploading: externalUploading = false,
  defaultType = "identity_proof",
  allowedTypes = DEFAULT_DOC_TYPES,
  onCancel,
}: DocumentUploaderProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [selectedType, setSelectedType] = useState(defaultType);
  const [lastUploadedFile, setLastUploadedFile] = useState<File | null>(null);

  const [stage, setStage] = useState<UploadStage>({
    step: "idle",
  });

  const isUploading = externalUploading || stage.step === "uploading" || stage.step === "extracting";

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleFile = async (file: File) => {
    // Avoid duplicate rapid submission
    if (isUploading) return;

    // Check size limit: 10MB max
    if (file.size > 10 * 1024 * 1024) {
      setStage({
        step: "error",
        fileName: file.name,
        errorMessage: "File exceeds 10MB limit. Please upload a smaller document.",
      });
      return;
    }

    // Supported formats
    const validExtensions = [".pdf", ".jpg", ".jpeg", ".png"];
    const hasValidExt = validExtensions.some((ext) => file.name.toLowerCase().endsWith(ext));
    if (!hasValidExt) {
      setStage({
        step: "error",
        fileName: file.name,
        errorMessage: "Unsupported format. Only PDF, JPG, and PNG files are accepted.",
      });
      return;
    }

    setLastUploadedFile(file);
    setStage({
      step: "uploading",
      fileName: file.name,
      fileSize: file.size,
      documentType: selectedType,
    });

    try {
      // Simulate/Transition to extraction state
      setTimeout(() => {
        setStage((prev) => (prev.step === "uploading" ? { ...prev, step: "extracting" } : prev));
      }, 700);

      const result = await onUpload(file, selectedType);

      // Successfully processed by backend
      setStage({
        step: "success",
        fileName: file.name,
        fileSize: file.size,
        documentType: selectedType,
        verificationStatus: result?.verification_status || "PENDING",
      });

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    } catch (err: any) {
      setStage({
        step: "error",
        fileName: file.name,
        documentType: selectedType,
        errorMessage: err.message || "Document upload failed. Please try again.",
      });
    }
  };

  const retryUpload = () => {
    if (lastUploadedFile) {
      handleFile(lastUploadedFile);
    } else {
      setStage({ step: "idle" });
    }
  };

  const resetUploader = () => {
    setStage({ step: "idle" });
    setLastUploadedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <div className="w-full bg-white rounded-2xl border border-slate-200 p-5 shadow-xs space-y-4">
      
      {/* Category selector */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <label className="text-xs font-bold text-slate-700 uppercase tracking-wide">
            Select Document Category
          </label>
          {onCancel && (
            <button
              onClick={onCancel}
              className="text-xs text-slate-400 hover:text-slate-600 font-medium"
            >
              Cancel
            </button>
          )}
        </div>
        <select
          value={selectedType}
          onChange={(e) => setSelectedType(e.target.value)}
          disabled={isUploading}
          className="w-full text-xs font-medium bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
        >
          {allowedTypes.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
      </div>

      {/* Upload Drag/Drop Box */}
      {stage.step === "idle" && (
        <div
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
          className={`relative border-2 border-dashed rounded-2xl p-6 transition-all duration-200 flex flex-col items-center justify-center text-center cursor-pointer ${
            dragActive
              ? "border-indigo-500 bg-indigo-50"
              : "border-slate-300 bg-slate-50 hover:bg-slate-100 hover:border-indigo-400"
          }`}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            accept=".pdf,.jpg,.jpeg,.png"
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          />

          <div className="h-10 w-10 bg-white rounded-xl flex items-center justify-center shadow-xs border border-slate-200 mb-2 text-indigo-600">
            <FileUp className="h-5 w-5" />
          </div>
          <p className="text-xs font-bold text-slate-900 mb-0.5">
            Click to select or drag and drop file here
          </p>
          <p className="text-[11px] text-slate-500">
            Accepted formats: PDF, JPG, PNG (Max 10MB)
          </p>
        </div>
      )}

      {/* Uploading / Extracting State */}
      {(stage.step === "uploading" || stage.step === "extracting") && (
        <div className="p-6 bg-slate-50 border border-slate-200 rounded-2xl flex flex-col items-center justify-center text-center space-y-3">
          <Loader2 className="h-8 w-8 text-indigo-600 animate-spin" />
          <div className="space-y-1">
            <span className="text-xs font-bold text-slate-900 block">
              {stage.step === "uploading"
                ? "Uploading document to secure vault..."
                : "Reading document and extracting verification data..."}
            </span>
            <span className="text-[11px] text-slate-500 block font-mono">
              {stage.fileName}
            </span>
          </div>
          <span className="text-[10px] text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-md font-semibold">
            Stage: {stage.step === "uploading" ? "1/2 Uploading" : "2/2 OCR & Verification Check"}
          </span>
        </div>
      )}

      {/* Success State */}
      {stage.step === "success" && (
        <div className="p-4 bg-emerald-50/70 border border-emerald-200 rounded-2xl space-y-3">
          <div className="flex items-start space-x-3">
            <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />
            <div className="flex-1 space-y-1">
              <span className="text-xs font-bold text-emerald-950 block">
                Document Uploaded Successfully
              </span>
              <p className="text-[11px] text-emerald-800">
                File: <strong className="font-mono">{stage.fileName}</strong> has been secured and linked to category{" "}
                <strong>{humanizeKey(stage.documentType || "")}</strong>.
              </p>
              <div className="pt-1">
                <DocumentVerificationBadge
                  verification_status={stage.verificationStatus}
                  showExplanation
                />
              </div>
            </div>
          </div>

          <div className="flex justify-end pt-2 border-t border-emerald-100">
            <button
              onClick={resetUploader}
              className="text-xs font-semibold text-emerald-800 hover:text-emerald-950 underline"
            >
              Upload another document
            </button>
          </div>
        </div>
      )}

      {/* Error State with Retry */}
      {stage.step === "error" && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-2xl space-y-3">
          <div className="flex items-start space-x-3">
            <AlertCircle className="h-5 w-5 text-rose-600 shrink-0 mt-0.5" />
            <div className="flex-1 space-y-1">
              <span className="text-xs font-bold text-rose-950 block">
                Upload or Processing Error
              </span>
              <p className="text-xs text-rose-800">
                {stage.errorMessage || "An error occurred while uploading. Please check the file and try again."}
              </p>
            </div>
          </div>

          <div className="flex items-center justify-end space-x-2 pt-2 border-t border-rose-100">
            <button
              onClick={resetUploader}
              className="px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-800"
            >
              Choose different file
            </button>
            <button
              onClick={retryUpload}
              className="px-3 py-1.5 text-xs font-bold bg-rose-600 hover:bg-rose-700 text-white rounded-xl flex items-center space-x-1"
            >
              <RotateCcw className="h-3 w-3" />
              <span>Retry Upload</span>
            </button>
          </div>
        </div>
      )}

    </div>
  );
}
