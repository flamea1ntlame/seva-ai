"use client";

import React, { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";
import DocumentCard from "@/components/DocumentCard";
import { FolderLock, Loader2, Search, ShieldCheck } from "lucide-react";

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<any[]>([]);
  const [stats, setStats] = useState<{total: number, verified: number, shared: number} | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    Promise.all([
      fetchApi("/api/documents/"),
      fetchApi("/api/documents/vault-stats")
    ])
      .then(([docsRes, statsRes]) => {
        setDocuments(docsRes);
        setStats(statsRes);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const filteredDocs = documents.filter(doc => {
    const searchLower = search.toLowerCase();
    return (
      doc.title.toLowerCase().includes(searchLower) ||
      doc.document_type.toLowerCase().includes(searchLower)
    );
  });

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div>
          <h1 className="text-2xl font-extrabold text-brand-900 mb-2">Document Vault</h1>
          <p className="text-sm text-brand-500 max-w-md">
            Your securely stored and verified documents. SEVA uses these to automatically fill your government applications.
          </p>
        </div>
        
        <div className="flex bg-white rounded-2xl border border-brand-200 shadow-sm p-3 gap-6">
          <div className="px-4 text-center">
            <span className="block text-2xl font-black text-brand-900">{stats?.total || 0}</span>
            <span className="text-[10px] uppercase font-bold tracking-wider text-brand-500">Total</span>
          </div>
          <div className="px-4 text-center border-l border-brand-100">
            <span className="block text-2xl font-black text-success-600">{stats?.verified || 0}</span>
            <span className="text-[10px] uppercase font-bold tracking-wider text-success-700">Verified</span>
          </div>
          <div className="px-4 text-center border-l border-brand-100">
            <span className="block text-2xl font-black text-primary-600">{stats?.shared || 0}</span>
            <span className="text-[10px] uppercase font-bold tracking-wider text-primary-700">Shared</span>
          </div>
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex items-center justify-between bg-brand-100/50 p-2 rounded-xl">
        <div className="relative w-full max-w-xs">
          <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-brand-400" />
          <input 
            type="text" 
            placeholder="Search documents..." 
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 pr-4 py-2 bg-white border border-brand-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 w-full"
          />
        </div>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="py-20 flex justify-center">
          <Loader2 className="h-8 w-8 text-primary-500 animate-spin" />
        </div>
      ) : filteredDocs.length === 0 ? (
        <div className="bg-white rounded-3xl border border-brand-200 p-12 text-center flex flex-col items-center">
          <div className="h-16 w-16 bg-brand-50 rounded-2xl flex items-center justify-center mb-4 text-brand-400">
            <FolderLock className="h-8 w-8" />
          </div>
          <h3 className="text-lg font-bold text-brand-900 mb-2">No documents found</h3>
          <p className="text-brand-500 text-sm">
            {search ? "Try adjusting your search terms." : "You haven't uploaded any documents yet. They will appear here when you apply for services."}
          </p>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredDocs.map(doc => (
            <DocumentCard key={doc.id} doc={doc} />
          ))}
        </div>
      )}

      {/* Security notice */}
      <div className="bg-success-50 rounded-2xl p-4 border border-success-200 flex items-start space-x-3 mt-8">
        <ShieldCheck className="h-5 w-5 text-success-600 shrink-0 mt-0.5" />
        <div>
          <h4 className="text-sm font-bold text-success-800">Bank-Grade Security</h4>
          <p className="text-xs text-success-700 mt-1">
            Your documents are encrypted and stored securely. SEVA will never share your information with any government department without your explicit consent.
          </p>
        </div>
      </div>
    </div>
  );
}
