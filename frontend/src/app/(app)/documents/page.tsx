"use client";

import React, { useEffect, useState, useCallback } from "react";
import { fetchApi, getApiBaseUrl } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import DocumentCard from "@/components/DocumentCard";
import DocumentUploader from "@/components/DocumentUploader";
import { FolderLock, Loader2, Search, ShieldCheck, Plus, X } from "lucide-react";
import toast from "react-hot-toast";

export default function DocumentsPage() {
  const { user } = useAuth();
  const [documents, setDocuments] = useState<any[]>([]);
  const [stats, setStats] = useState<{ total: number; verified: number; shared: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [showUploadModal, setShowUploadModal] = useState(false);

  const loadDocs = useCallback(async () => {
    try {
      const [docsRes, statsRes] = await Promise.all([
        fetchApi("/api/documents/"),
        fetchApi("/api/documents/vault-stats").catch(() => null),
      ]);
      setDocuments(Array.isArray(docsRes) ? docsRes : []);
      if (statsRes) setStats(statsRes);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDocs();
  }, [loadDocs]);

  const handleUpload = async (file: File, type: string) => {
    if (!user) return;
    const formData = new FormData();
    formData.append("file", file);
    formData.append("document_type", type);
    formData.append("citizen_id", user.id);

    const token = localStorage.getItem("seva_token");
    const res = await fetch(
      `${getApiBaseUrl()}/api/documents/upload`,
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

    const newDoc = await res.json();
    toast.success("Document uploaded to vault.");
    await loadDocs();
    setShowUploadModal(false);
    return newDoc;
  };

  const filteredDocs = documents.filter((doc) => {
    const searchLower = search.toLowerCase();
    return (
      (doc.title && doc.title.toLowerCase().includes(searchLower)) ||
      (doc.document_type && doc.document_type.toLowerCase().includes(searchLower))
    );
  });

  return (
    <div className="max-w-6xl mx-auto space-y-8 pb-12">
      
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Citizen Document Vault</h1>
          <p className="text-xs text-slate-500 max-w-md mt-0.5">
            Your securely encrypted and verified documents. SEVA links these automatically to your service applications.
          </p>
        </div>

        <div className="flex items-center space-x-4">
          <div className="flex bg-white rounded-2xl border border-slate-200 shadow-xs p-3 gap-6">
            <div className="px-3 text-center">
              <span className="block text-xl font-extrabold text-slate-900">{stats?.total || 0}</span>
              <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">Total</span>
            </div>
            <div className="px-3 text-center border-l border-slate-100">
              <span className="block text-xl font-extrabold text-emerald-600">{stats?.verified || 0}</span>
              <span className="text-[10px] uppercase font-bold tracking-wider text-emerald-700">Verified</span>
            </div>
            <div className="px-3 text-center border-l border-slate-100">
              <span className="block text-xl font-extrabold text-indigo-600">{stats?.shared || 0}</span>
              <span className="text-[10px] uppercase font-bold tracking-wider text-indigo-700">Shared</span>
            </div>
          </div>

          <button
            onClick={() => setShowUploadModal(true)}
            className="px-4 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-2xl text-xs font-bold transition flex items-center space-x-1.5 shadow-xs"
          >
            <Plus className="h-4 w-4" />
            <span>Upload Document</span>
          </button>
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex items-center justify-between bg-white border border-slate-200 p-3 rounded-2xl shadow-xs">
        <div className="relative w-full max-w-sm">
          <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search documents by name or category..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500 w-full"
          />
        </div>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="py-24 flex justify-center">
          <Loader2 className="h-8 w-8 text-indigo-600 animate-spin" />
        </div>
      ) : filteredDocs.length === 0 ? (
        <div className="bg-white rounded-3xl border border-slate-200 p-12 text-center flex flex-col items-center space-y-3">
          <div className="h-12 w-12 bg-slate-50 rounded-2xl flex items-center justify-center text-slate-400">
            <FolderLock className="h-6 w-6" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-bold text-slate-900">No documents in your vault</h3>
            <p className="text-xs text-slate-500 max-w-sm">
              {search
                ? "No documents match your search keyword."
                : "You have not uploaded any documents yet. Upload your identity, address, or income proofs to speed up applications."}
            </p>
          </div>
          <button
            onClick={() => setShowUploadModal(true)}
            className="mt-2 px-4 py-2 bg-indigo-600 text-white rounded-xl text-xs font-bold hover:bg-indigo-700 transition"
          >
            Upload Document Now
          </button>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredDocs.map((doc) => (
            <DocumentCard key={doc.id} doc={doc} />
          ))}
        </div>
      )}

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-lg w-full border border-slate-200 shadow-xl p-6 space-y-4 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                Upload Document to Vault
              </h3>
              <button
                onClick={() => setShowUploadModal(false)}
                className="text-xs font-bold text-slate-400 hover:text-slate-600"
              >
                ✕ Cancel
              </button>
            </div>

            <DocumentUploader
              onUpload={handleUpload}
              onCancel={() => setShowUploadModal(false)}
            />
          </div>
        </div>
      )}

      {/* Security Privacy Notice */}
      <div className="bg-slate-50 rounded-2xl p-5 border border-slate-200 flex items-start space-x-3.5">
        <ShieldCheck className="h-5 w-5 text-indigo-600 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
            Privacy & Data Sovereign Guarantee
          </h4>
          <p className="text-xs text-slate-600 leading-relaxed">
            Your uploaded documents are securely hashed and stored. SEVA AI will never share your personal documents or extracted demographic details with any government department without your explicit prior consent.
          </p>
        </div>
      </div>

    </div>
  );
}
