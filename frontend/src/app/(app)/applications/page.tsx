"use client";

import React, { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";
import ApplicationCard from "@/components/ApplicationCard";
import { FileText, Loader2, Search, Plus, Compass } from "lucide-react";
import Link from "next/link";
import { getApplicationStatusInfo } from "@/lib/statusMapping";

export default function ApplicationsPage() {
  const [applications, setApplications] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("ALL"); // ALL, ACTION_REQUIRED, ACTIVE, COMPLETED, REJECTED

  useEffect(() => {
    fetchApi("/api/applications/")
      .then((data) => setApplications(Array.isArray(data) ? data : []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const filteredApps = applications.filter((app) => {
    // Text search
    const searchLower = search.toLowerCase();
    const matchesSearch =
      (app.application_number && app.application_number.toLowerCase().includes(searchLower)) ||
      (app.government_reference && app.government_reference.toLowerCase().includes(searchLower)) ||
      (app.service?.title && app.service.title.toLowerCase().includes(searchLower)) ||
      (app.service?.department && app.service.department.toLowerCase().includes(searchLower));

    if (!matchesSearch) return false;

    const info = getApplicationStatusInfo(app.status, app.government_status);
    const isCompleted = app.status === "COMPLETED" || (app.government_status || "").toUpperCase() === "APPROVED";
    const isRejected = (app.government_status || "").toUpperCase() === "REJECTED";
    const isActive = !isCompleted && !isRejected;

    if (filter === "ACTION_REQUIRED") return info.actionRequired;
    if (filter === "ACTIVE") return isActive;
    if (filter === "COMPLETED") return isCompleted;
    if (filter === "REJECTED") return isRejected;
    return true; // ALL
  });

  return (
    <div className="max-w-6xl mx-auto space-y-6 pb-12">
      
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Citizen Applications</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Track and manage your government service submissions, document verifications, and progress.
          </p>
        </div>

        <Link
          href="/services"
          className="inline-flex items-center space-x-1.5 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-bold transition shadow-xs self-start md:self-auto"
        >
          <Compass className="h-4 w-4" />
          <span>Explore Services & Apply</span>
        </Link>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-xs flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="relative w-full sm:w-80">
          <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search by reference, service, or department..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        <div className="flex items-center space-x-2 w-full sm:w-auto">
          <span className="text-xs font-bold text-slate-500 whitespace-nowrap">Filter:</span>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-full sm:w-auto bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs font-semibold text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="ALL">All Applications ({applications.length})</option>
            <option value="ACTION_REQUIRED">Action Required</option>
            <option value="ACTIVE">In Progress</option>
            <option value="COMPLETED">Completed</option>
            <option value="REJECTED">Rejected</option>
          </select>
        </div>
      </div>

      {/* Grid of Applications */}
      {loading ? (
        <div className="py-24 flex flex-col items-center justify-center space-y-3">
          <Loader2 className="h-8 w-8 text-indigo-600 animate-spin" />
          <span className="text-xs text-slate-500 font-medium">Loading applications...</span>
        </div>
      ) : filteredApps.length === 0 ? (
        <div className="bg-white rounded-3xl border border-slate-200 p-12 text-center flex flex-col items-center space-y-3">
          <div className="h-12 w-12 bg-slate-50 rounded-2xl flex items-center justify-center text-slate-400 border border-slate-100">
            <FileText className="h-6 w-6" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-bold text-slate-900">No applications match your criteria</h3>
            <p className="text-xs text-slate-500 max-w-sm">
              {search || filter !== "ALL"
                ? "Try clearing your search keyword or switching your filter."
                : "You have not started any service applications yet. Browse the official catalog to begin."}
            </p>
          </div>
          <Link
            href="/services"
            className="mt-2 inline-flex items-center space-x-1.5 px-4 py-2 bg-indigo-600 text-white rounded-xl text-xs font-bold hover:bg-indigo-700 transition"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Start an Application</span>
          </Link>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredApps.map((app) => (
            <ApplicationCard key={app.id} application={app} />
          ))}
        </div>
      )}

    </div>
  );
}
