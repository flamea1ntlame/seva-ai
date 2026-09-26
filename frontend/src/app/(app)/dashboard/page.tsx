"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { useEventContext } from "@/contexts/EventContext";
import ChatAssistant from "@/components/ChatAssistant";
import StatusBadge from "@/components/StatusBadge";
import { fetchApi } from "@/lib/api";
import {
  FileText,
  FolderLock,
  Loader2,
  ChevronRight,
  Activity
} from "lucide-react";
import Link from "next/link";

export default function DashboardPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [applications, setApplications] = useState<any[]>([]);
  const [vaultStats, setVaultStats] = useState<{total: number, verified: number, shared: number} | null>(null);
  const [dataLoading, setDataLoading] = useState<boolean>(true);

  const { agentActivity } = useEventContext();

  const loadDashboardData = useCallback(async () => {
    if (!user) return;
    try {
      const [appsRes, statsRes] = await Promise.allSettled([
        fetchApi("/api/applications/"),
        fetchApi("/api/documents/vault-stats"),
      ]);

      if (appsRes.status === "fulfilled") setApplications(appsRes.value);
      if (statsRes.status === "fulfilled") setVaultStats(statsRes.value);
    } catch (err) {
      console.error("Dashboard data load error:", err);
    } finally {
      setDataLoading(false);
    }
  }, [user]);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData, agentActivity]);

  if (authLoading || (!user && !authLoading)) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="h-8 w-8 text-primary-500 animate-spin" />
      </div>
    );
  }

  const activeApplications = applications.filter(app => app.status !== "COMPLETED" && app.government_status !== "APPROVED" && app.government_status !== "REJECTED");

  return (
    <div className="h-full max-w-7xl mx-auto pb-8">
      {/* Main Content Grid */}
      <div className="grid lg:grid-cols-12 gap-6 items-start h-full">
        
        {/* Left: Chat Interface */}
        <div className="lg:col-span-8 flex flex-col h-[calc(100vh-8rem)]">
          <ChatAssistant onApplicationCreated={loadDashboardData} />
        </div>

        {/* Right: Dashboard Summary */}
        <div className="lg:col-span-4 space-y-6">
          
          {/* Active Applications */}
          <div className="bg-white rounded-2xl border border-brand-200 shadow-sm p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-brand-900 flex items-center space-x-2 uppercase tracking-wider">
                <Activity className="h-4 w-4 text-primary-500" />
                <span>Active Applications</span>
              </h2>
              {activeApplications.length > 0 && (
                <Link href="/applications" className="text-[10px] font-bold text-primary-600 uppercase tracking-widest hover:text-primary-800 flex items-center">
                  View All <ChevronRight className="h-3 w-3 ml-0.5" />
                </Link>
              )}
            </div>

            {dataLoading ? (
              <div className="py-8 flex justify-center"><Loader2 className="h-5 w-5 text-brand-400 animate-spin" /></div>
            ) : activeApplications.length === 0 ? (
              <div className="text-center py-6">
                <div className="h-10 w-10 bg-brand-50 rounded-full flex items-center justify-center mx-auto mb-3">
                  <FileText className="h-5 w-5 text-brand-400" />
                </div>
                <p className="text-sm font-bold text-brand-900">No active applications</p>
                <p className="text-xs text-brand-500 mt-1 mb-4">Start a government service request with SEVA and your application will appear here.</p>
                <Link href="/applications" className="inline-flex items-center justify-center px-4 py-2 bg-brand-50 hover:bg-brand-100 text-brand-700 text-xs font-semibold rounded-lg transition-colors">
                  Explore Services
                </Link>
              </div>
            ) : (
              <div className="space-y-3">
                {activeApplications.slice(0, 3).map(app => (
                  <div key={app.id} className="group relative bg-brand-50 border border-brand-100 hover:border-brand-200 rounded-xl p-3 transition-all cursor-pointer">
                    <Link href={`/applications/${app.id}`} className="absolute inset-0 z-10" />
                    <div className="flex items-center justify-between">
                      <div className="min-w-0">
                        <p className="text-[13px] font-bold text-brand-900 truncate">
                          {app.service?.title || app.service?.code?.replace(/_/g, ' ') || "Application"}
                        </p>
                        <div className="flex items-center space-x-2 mt-1">
                          <p className="text-[10px] font-medium text-brand-500 font-mono">
                            SEVA-{app.id.substring(0, 6).toUpperCase()}
                          </p>
                          <StatusBadge status={app.status} government_status={app.government_status} className="scale-[0.85] origin-left" />
                        </div>
                      </div>
                      <ChevronRight className="h-4 w-4 text-brand-300 group-hover:text-primary-500 transition-colors shrink-0 ml-2" />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Document Vault Summary */}
          <div className="bg-white rounded-2xl border border-brand-200 shadow-sm p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-brand-900 flex items-center space-x-2 uppercase tracking-wider">
                <FolderLock className="h-4 w-4 text-primary-500" />
                <span>Document Vault</span>
              </h2>
              <Link href="/documents" className="text-[10px] font-bold text-primary-600 uppercase tracking-widest hover:text-primary-800 flex items-center">
                Open Vault <ChevronRight className="h-3 w-3 ml-0.5" />
              </Link>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div className="bg-brand-50 p-3 rounded-xl border border-brand-100 flex flex-col items-center justify-center text-center">
                <span className="text-lg font-extrabold text-brand-900">{vaultStats?.total || 0}</span>
                <span className="text-[9px] font-bold uppercase tracking-wider text-brand-500 mt-1">Uploaded</span>
              </div>
              <div className="bg-success-50 p-3 rounded-xl border border-success-100 flex flex-col items-center justify-center text-center">
                <span className="text-lg font-extrabold text-success-700">{vaultStats?.verified || 0}</span>
                <span className="text-[9px] font-bold uppercase tracking-wider text-success-600 mt-1">Verified</span>
              </div>
              <div className="bg-primary-50 p-3 rounded-xl border border-primary-100 flex flex-col items-center justify-center text-center">
                <span className="text-lg font-extrabold text-primary-700">{vaultStats?.shared || 0}</span>
                <span className="text-[9px] font-bold uppercase tracking-wider text-primary-600 mt-1">Shared</span>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
