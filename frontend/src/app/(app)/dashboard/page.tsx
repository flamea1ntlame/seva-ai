"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { useEventContext } from "@/contexts/EventContext";
import ChatAssistant from "@/components/ChatAssistant";
import ApplicationCard from "@/components/ApplicationCard";
import StatusBadge from "@/components/StatusBadge";
import { fetchApi } from "@/lib/api";
import {
  FileText,
  FolderLock,
  Loader2,
  Sparkles,
  ChevronRight,
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Compass,
  ArrowRight,
  ShieldCheck,
  Building2,
} from "lucide-react";
import Link from "next/link";
import { getApplicationStatusInfo, humanizeKey } from "@/lib/statusMapping";

export default function DashboardPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [applications, setApplications] = useState<any[]>([]);
  const [vaultStats, setVaultStats] = useState<{ total: number; verified: number; shared: number } | null>(null);
  const [dataLoading, setDataLoading] = useState<boolean>(true);

  const { agentActivity } = useEventContext();

  const loadDashboardData = useCallback(async () => {
    if (!user) return;
    try {
      const [appsRes, statsRes] = await Promise.allSettled([
        fetchApi("/api/applications/"),
        fetchApi("/api/documents/vault-stats"),
      ]);

      if (appsRes.status === "fulfilled") setApplications(Array.isArray(appsRes.value) ? appsRes.value : []);
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
      <div className="h-full py-24 flex flex-col items-center justify-center space-y-3">
        <Loader2 className="h-8 w-8 text-indigo-600 animate-spin" />
        <span className="text-xs text-slate-500 font-medium">Securing session...</span>
      </div>
    );
  }

  // Categorize applications:
  // 1. Action Required: missing documents, consent required, review required
  const actionRequiredApps = applications.filter((app) => {
    const info = getApplicationStatusInfo(app.status, app.government_status);
    return info.actionRequired;
  });

  // 2. In Progress / Submitted / Under Processing
  const activeProcessingApps = applications.filter((app) => {
    const isCompleted = app.status === "COMPLETED" || (app.government_status || "").toUpperCase() === "APPROVED";
    const isRejected = (app.government_status || "").toUpperCase() === "REJECTED";
    const info = getApplicationStatusInfo(app.status, app.government_status);
    return !isCompleted && !isRejected && !info.actionRequired;
  });

  // 3. Completed applications
  const completedApps = applications.filter(
    (app) => app.status === "COMPLETED" || (app.government_status || "").toUpperCase() === "APPROVED"
  );

  return (
    <div className="max-w-6xl mx-auto space-y-8 pb-16">
      
      {/* Hero Header */}
      <div className="bg-slate-900 rounded-3xl p-8 sm:p-10 text-white relative overflow-hidden shadow-md">
        <div className="relative z-10 max-w-2xl space-y-3">
          <span className="inline-flex items-center space-x-1.5 text-indigo-400 text-[10px] font-bold uppercase tracking-widest">
            <Sparkles className="h-3.5 w-3.5" />
            <span>Digital Government Services</span>
          </span>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight">
            Welcome back, {user?.full_name?.split(" ")[0]}
          </h1>
          <p className="text-slate-300 text-xs sm:text-sm leading-relaxed max-w-xl">
            SEVA AI is your direct digital interface for government service applications, document verification,
            and real-time status tracking.
          </p>

          <div className="flex flex-wrap gap-2 pt-2">
            <Link
              href="/services"
              className="inline-flex items-center space-x-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-xl shadow-xs transition"
            >
              <Compass className="h-3.5 w-3.5" />
              <span>Browse All Services</span>
            </Link>
            <Link
              href="/documents"
              className="inline-flex items-center space-x-1.5 px-4 py-2 bg-white/10 hover:bg-white/20 text-white text-xs font-semibold rounded-xl border border-white/10 transition"
            >
              <FolderLock className="h-3.5 w-3.5" />
              <span>Manage Vault</span>
            </Link>
          </div>
        </div>
      </div>

      {/* Prominent Action Required Section */}
      {actionRequiredApps.length > 0 && (
        <div className="bg-amber-50/80 border-2 border-amber-300 rounded-3xl p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2.5">
              <div className="h-8 w-8 rounded-xl bg-amber-200 text-amber-800 flex items-center justify-center shrink-0">
                <AlertTriangle className="h-4 w-4" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                  Citizen Action Required ({actionRequiredApps.length})
                </h2>
                <p className="text-xs text-amber-800">
                  The following applications require your attention before they can proceed.
                </p>
              </div>
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-4">
            {actionRequiredApps.map((app) => {
              const info = getApplicationStatusInfo(app.status, app.government_status);
              return (
                <div
                  key={app.id}
                  className="bg-white rounded-2xl border border-amber-200 p-5 shadow-xs flex flex-col justify-between space-y-4"
                >
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                        {app.application_number}
                      </span>
                      <StatusBadge status={app.status} government_status={app.government_status} />
                    </div>

                    <h3 className="text-sm font-bold text-slate-900">
                      {app.service?.title || "Application"}
                    </h3>

                    <p className="text-xs text-amber-900 font-medium">
                      ⚠️ {info.actionPrompt || info.description}
                    </p>
                  </div>

                  <Link
                    href={`/applications/${app.id}`}
                    className="w-full py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-xl text-xs font-bold transition flex items-center justify-center space-x-1.5 shadow-2xs"
                  >
                    <span>{info.actionLabel || "Take Action"}</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Main Grid: Chat Assistant & Applications Summary */}
      <div className="grid lg:grid-cols-12 gap-8 items-start">
        
        {/* Left: Chatbot Interface */}
        <div className="lg:col-span-7">
          <ChatAssistant onApplicationCreated={loadDashboardData} />
        </div>

        {/* Right: Dashboard Summary Column */}
        <div className="lg:col-span-5 space-y-6">
          
          {/* Active Applications Card */}
          <div className="bg-white rounded-3xl border border-slate-200 shadow-xs p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center space-x-2">
                <Activity className="h-4 w-4 text-indigo-600" />
                <span>Active Applications ({applications.length})</span>
              </h2>
              <Link
                href="/applications"
                className="text-[11px] font-bold text-indigo-600 hover:text-indigo-800 flex items-center"
              >
                View All <ChevronRight className="h-3 w-3 ml-0.5" />
              </Link>
            </div>

            {dataLoading ? (
              <div className="py-8 flex justify-center">
                <Loader2 className="h-5 w-5 text-indigo-600 animate-spin" />
              </div>
            ) : applications.length === 0 ? (
              <div className="text-center py-8 space-y-2">
                <FileText className="h-8 w-8 text-slate-300 mx-auto" />
                <p className="text-xs font-semibold text-slate-700">No applications started yet</p>
                <p className="text-[11px] text-slate-500">
                  Ask SEVA in the chat or browse services to start an application.
                </p>
                <Link
                  href="/services"
                  className="inline-block mt-2 px-3 py-1.5 bg-indigo-50 text-indigo-700 rounded-lg text-xs font-bold"
                >
                  Explore Services
                </Link>
              </div>
            ) : (
              <div className="space-y-3">
                {applications.slice(0, 3).map((app) => (
                  <ApplicationCard key={app.id} application={app} />
                ))}
              </div>
            )}
          </div>

          {/* Document Vault Summary */}
          <div className="bg-white rounded-3xl border border-slate-200 shadow-xs p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center space-x-2">
                <FolderLock className="h-4 w-4 text-indigo-600" />
                <span>Citizen Document Vault</span>
              </h2>
              <Link
                href="/documents"
                className="text-[11px] font-bold text-indigo-600 hover:text-indigo-800 flex items-center"
              >
                Open Vault <ChevronRight className="h-3 w-3 ml-0.5" />
              </Link>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="bg-slate-50 p-3.5 rounded-2xl border border-slate-100 flex flex-col items-center justify-center text-center">
                <span className="text-lg font-extrabold text-slate-900">{vaultStats?.total || 0}</span>
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mt-0.5">
                  Uploaded
                </span>
              </div>
              <div className="bg-emerald-50 p-3.5 rounded-2xl border border-emerald-100 flex flex-col items-center justify-center text-center">
                <span className="text-lg font-extrabold text-emerald-800">{vaultStats?.verified || 0}</span>
                <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 mt-0.5">
                  Verified
                </span>
              </div>
              <div className="bg-indigo-50 p-3.5 rounded-2xl border border-indigo-100 flex flex-col items-center justify-center text-center">
                <span className="text-lg font-extrabold text-indigo-800">{vaultStats?.shared || 0}</span>
                <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-700 mt-0.5">
                  Shared
                </span>
              </div>
            </div>
          </div>

          {/* Completed Applications Badge */}
          {completedApps.length > 0 && (
            <div className="bg-white rounded-3xl border border-slate-200 shadow-xs p-5 flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="h-9 w-9 bg-emerald-100 text-emerald-700 rounded-xl flex items-center justify-center shrink-0">
                  <CheckCircle2 className="h-5 w-5" />
                </div>
                <div>
                  <span className="text-xs font-bold text-slate-900 block">
                    {completedApps.length} Completed {completedApps.length === 1 ? "Service" : "Services"}
                  </span>
                  <span className="text-[11px] text-slate-500">Official certificate issued</span>
                </div>
              </div>
              <Link
                href="/applications?filter=COMPLETED"
                className="text-xs font-bold text-indigo-600 hover:text-indigo-800"
              >
                View
              </Link>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
