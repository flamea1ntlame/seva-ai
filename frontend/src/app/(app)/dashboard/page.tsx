"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { useEventContext } from "@/contexts/EventContext";
import ChatAssistant from "@/components/ChatAssistant";
import ApplicationCard from "@/components/ApplicationCard";
import { fetchApi } from "@/lib/api";
import {
  FileText,
  FolderLock,
  Loader2,
  Sparkles,
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

  // Auto-reload data when SSE triggers a status change
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
  }, [loadDashboardData, agentActivity]); // agentActivity or a specific SSE trigger could also reload data

  // We should also listen for specific SSE events here to trigger reload, but since the requirement is to use one SSE connection, the EventContext could expose a `lastEvent` timestamp to trigger re-fetches. For now, polling or triggering on `agentActivity` change works for demo purposes, or we can just rely on the `ChatAssistant` triggering `onApplicationCreated`.

  if (authLoading || (!user && !authLoading)) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="h-8 w-8 text-primary-500 animate-spin" />
      </div>
    );
  }

  const activeApplications = applications.filter(app => app.status !== "COMPLETED" && app.government_status !== "APPROVED" && app.government_status !== "REJECTED");

  return (
    <div className="max-w-6xl mx-auto space-y-8 pb-12">
      
      {/* Hero Section */}
      <div className="bg-brand-900 rounded-3xl p-8 sm:p-10 text-white relative overflow-hidden shadow-lg">
        {/* Decorative background blur */}
        <div className="absolute top-0 right-0 -mr-20 -mt-20 w-96 h-96 bg-primary-600/30 rounded-full blur-3xl pointer-events-none"></div>
        <div className="absolute bottom-0 left-0 -ml-20 -mb-20 w-80 h-80 bg-brand-700/40 rounded-full blur-3xl pointer-events-none"></div>

        <div className="relative z-10 max-w-2xl">
          <span className="inline-flex items-center space-x-1.5 text-primary-300 text-[10px] font-bold uppercase tracking-widest mb-4">
            <Sparkles className="h-3.5 w-3.5" />
            <span>SEVA AI Assistant</span>
          </span>
          <h1 className="text-3xl sm:text-4xl font-extrabold mb-3 tracking-tight">
            Good morning, {user?.full_name?.split(' ')[0]}
          </h1>
          <p className="text-brand-300 text-sm sm:text-base mb-8 max-w-xl leading-relaxed">
            I am your official government services assistant. Tell me what you need, and I'll handle the requirements, document validation, and submission for you.
          </p>
          
          {/* Quick Suggestions */}
          <div className="flex flex-wrap gap-3">
            {["Income Certificate", "Birth Certificate", "Driving Licence"].map((service) => (
              <div key={service} className="bg-white/10 hover:bg-white/20 border border-white/10 px-4 py-2 rounded-xl text-sm font-medium text-white transition-colors cursor-pointer backdrop-blur-sm">
                Apply for {service}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid lg:grid-cols-12 gap-8 items-start">
        
        {/* Left: Chat Interface */}
        <div className="lg:col-span-7">
          <ChatAssistant onApplicationCreated={loadDashboardData} />
        </div>

        {/* Right: Dashboard Summary */}
        <div className="lg:col-span-5 space-y-6">
          
          {/* Active Applications */}
          <div className="bg-white rounded-2xl border border-brand-200 shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-brand-900 flex items-center space-x-2 uppercase tracking-wider">
                <Activity className="h-4 w-4 text-primary-500" />
                <span>Active Applications</span>
              </h2>
              <Link href="/applications" className="text-[10px] font-bold text-primary-600 uppercase tracking-widest hover:text-primary-800 flex items-center">
                View All <ChevronRight className="h-3 w-3 ml-0.5" />
              </Link>
            </div>

            {dataLoading ? (
              <div className="py-8 flex justify-center"><Loader2 className="h-5 w-5 text-brand-400 animate-spin" /></div>
            ) : activeApplications.length === 0 ? (
              <div className="text-center py-6">
                <FileText className="h-8 w-8 text-brand-300 mx-auto mb-2" />
                <p className="text-sm font-medium text-brand-600">No active applications</p>
                <p className="text-xs text-brand-400 mt-1">Ask SEVA to start a new application.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {activeApplications.slice(0, 2).map(app => (
                  <ApplicationCard key={app.id} application={app} />
                ))}
              </div>
            )}
          </div>

          {/* Document Vault Summary */}
          <div className="bg-white rounded-2xl border border-brand-200 shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-brand-900 flex items-center space-x-2 uppercase tracking-wider">
                <FolderLock className="h-4 w-4 text-primary-500" />
                <span>Document Vault</span>
              </h2>
              <Link href="/documents" className="text-[10px] font-bold text-primary-600 uppercase tracking-widest hover:text-primary-800 flex items-center">
                Open Vault <ChevronRight className="h-3 w-3 ml-0.5" />
              </Link>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="bg-brand-50 p-4 rounded-xl border border-brand-100 flex flex-col items-center justify-center text-center">
                <span className="text-xl font-extrabold text-brand-900">{vaultStats?.total || 0}</span>
                <span className="text-[9px] font-bold uppercase tracking-wider text-brand-500 mt-1">Total</span>
              </div>
              <div className="bg-success-50 p-4 rounded-xl border border-success-100 flex flex-col items-center justify-center text-center">
                <span className="text-xl font-extrabold text-success-700">{vaultStats?.verified || 0}</span>
                <span className="text-[9px] font-bold uppercase tracking-wider text-success-600 mt-1">Verified</span>
              </div>
              <div className="bg-primary-50 p-4 rounded-xl border border-primary-100 flex flex-col items-center justify-center text-center">
                <span className="text-xl font-extrabold text-primary-700">{vaultStats?.shared || 0}</span>
                <span className="text-[9px] font-bold uppercase tracking-wider text-primary-600 mt-1">Shared</span>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
