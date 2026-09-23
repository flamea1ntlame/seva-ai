"use client";

import React, { useRef, useState } from "react";
import { Upload, X, Loader2, FileUp } from "lucide-react";
import toast from "react-hot-toast";

interface DocumentUploaderProps {
  onUpload: (file: File, type: string) => Promise<void>;
  uploading: boolean;
}

export default function DocumentUploader({ onUpload, uploading }: DocumentUploaderProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [selectedType, setSelectedType] = useState("identity_proof");

  const docTypes = [
    { value: "identity_proof", label: "Identity Proof (Aadhaar / Voter ID)" },
    { value: "income_proof", label: "Income Proof (Salary Slip / ITR)" },
    { value: "address_proof", label: "Address Proof (Utility Bill / Passport)" },
    { value: "hospital_certificate", label: "Hospital Birth Certificate" },
    { value: "medical_declaration", label: "Medical Fitness Declaration" },
    { value: "photograph", label: "Passport Photograph" },
  ];

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
    if (file.size > 5 * 1024 * 1024) {
      toast.error("File size must be less than 5MB");
      return;
    }
    await onUpload(file, selectedType);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <div className="w-full">
      <div className="mb-3">
        <label className="block text-xs font-bold text-brand-700 uppercase tracking-wide mb-1.5">
          Document Type
        </label>
        <select
          value={selectedType}
          onChange={(e) => setSelectedType(e.target.value)}
          disabled={uploading}
          className="w-full text-sm bg-white border border-brand-200 rounded-xl px-3 py-2.5 font-medium text-brand-900 focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-50"
        >
          {docTypes.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
      </div>

      <div
        onDragEnter={handleDrag}
        onDragOver={handleDrag}
        onDragLeave={handleDrag}
        onDrop={handleDrop}
        className={`relative border-2 border-dashed rounded-2xl p-6 transition-all duration-200 flex flex-col items-center justify-center text-center cursor-pointer ${
          dragActive
            ? "border-primary-500 bg-primary-50"
            : "border-brand-200 bg-brand-50 hover:bg-brand-100/50 hover:border-primary-300"
        } ${uploading ? "opacity-50 pointer-events-none" : ""}`}
        onClick={() => !uploading && fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept=".pdf,.jpg,.jpeg,.png"
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
        />
        
        {uploading ? (
          <div className="flex flex-col items-center space-y-3">
            <Loader2 className="h-8 w-8 text-primary-500 animate-spin" />
            <div className="text-sm font-semibold text-brand-700">Extracting data...</div>
          </div>
        ) : (
          <>
            <div className="h-12 w-12 bg-white rounded-full flex items-center justify-center shadow-xs border border-brand-100 mb-3 text-primary-500">
              <FileUp className="h-5 w-5" />
            </div>
            <p className="text-sm font-bold text-brand-900 mb-1">
              Click to upload or drag and drop
            </p>
            <p className="text-xs text-brand-500">
              PDF, JPG, or PNG (Max. 10MB)
            </p>
          </>
        )}
      </div>
    </div>
  );
}
