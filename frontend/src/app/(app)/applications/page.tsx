"use client";

import React, { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";
import ApplicationCard from "@/components/ApplicationCard";
import { FileText, Loader2, Search } from "lucide-react";

export default function ApplicationsPage() {
  const [applications, setApplications] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("ALL"); // ALL, ACTIVE, COMPLETED, REJECTED

  useEffect(() => {
    fetchApi("/api/applications/")
      .then(setApplications)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const filteredApps = applications.filter(app => {
    // Text search
    const searchLower = search.toLowerCase();
    const matchesSearch = 
      app.application_number.toLowerCase().includes(searchLower) ||
      (app.government_reference && app.government_reference.toLowerCase().includes(searchLower)) ||
      (app.service?.title && app.service.title.toLowerCase().includes(searchLower));
    
    if (!matchesSearch) return false;

    // Status filter
    const isCompleted = app.status === "COMPLETED" || app.government_status === "APPROVED";
    const isRejected = app.government_status === "REJECTED";
    const isActive = !isCompleted && !isRejected;

    if (filter === "ACTIVE") return isActive;
    if (filter === "COMPLETED") return isCompleted;
    if (filter === "REJECTED") return isRejected;
    return true; // ALL
  });

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-brand-900">My Applications</h1>
          <p className="text-sm text-brand-500 mt-1">Track and manage your government service requests.</p>
        </div>
        
        <div className="flex items-center space-x-3">
          <div className="relative">
            <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-brand-400" />
            <input 
              type="text" 
              placeholder="Search applications..." 
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 pr-4 py-2 bg-white border border-brand-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 w-full sm:w-64"
            />
          </div>
          <select 
            value={filter} 
            onChange={(e) => setFilter(e.target.value)}
            className="bg-white border border-brand-200 rounded-xl px-3 py-2 text-sm font-medium text-brand-700 focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="ALL">All Status</option>
            <option value="ACTIVE">Active</option>
            <option value="COMPLETED">Completed</option>
            <option value="REJECTED">Rejected</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="py-20 flex justify-center">
          <Loader2 className="h-8 w-8 text-primary-500 animate-spin" />
        </div>
      ) : filteredApps.length === 0 ? (
        <div className="bg-white rounded-3xl border border-brand-200 p-12 text-center flex flex-col items-center">
          <div className="h-16 w-16 bg-brand-50 rounded-2xl flex items-center justify-center mb-4 text-brand-400">
            <FileText className="h-8 w-8" />
          </div>
          <h3 className="text-lg font-bold text-brand-900 mb-2">No applications found</h3>
          <p className="text-brand-500 text-sm">
            {search || filter !== "ALL" 
              ? "Try adjusting your search or filters." 
              : "You haven't started any applications yet. Go to the dashboard to ask SEVA to start one."}
          </p>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredApps.map(app => (
            <ApplicationCard key={app.id} application={app} />
          ))}
        </div>
      )}
    </div>
  );
}
