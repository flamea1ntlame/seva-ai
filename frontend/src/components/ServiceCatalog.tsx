"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { fetchApi } from "@/lib/api";
import {
  Search,
  Building2,
  Clock,
  IndianRupee,
  FileText,
  ChevronRight,
  ShieldCheck,
  AlertCircle,
  Loader2,
  Sparkles,
  Info,
} from "lucide-react";
import { humanizeKey } from "@/lib/statusMapping";
import {
  isJurisdictionSupported,
  getJurisdictionBlockMessage,
} from "@/lib/jurisdictionGuard";

export interface ServiceItem {
  id: string;
  code: string;
  title: string;
  description?: string;
  department: string;
  required_documents?: string[];
  required_fields?: string[];
  processing_time_days: number;
  fee_amount: number;
  is_active: boolean;
}

export interface ServiceDetailRequirements {
  service_code: string;
  service_name: string;
  department: string;
  title: string;
  description: string;
  responsible_authority?: {
    title: string;
    office: string;
    appeal_authority?: string;
  };
  required_documents: string[];
  required_fields: string[];
  processing_time_days: number;
  fee_amount: number;
  document_options?: Record<string, Array<{ name: string; authority?: string; digital_verify?: boolean }>>;
  jurisdiction?: string;
  jurisdiction_supported?: boolean;
  jurisdiction_notice?: {
    message: string;
    requested_jurisdiction: string;
    supported_jurisdictions: string[];
  };
}

interface ServiceCatalogProps {
  onSelectService?: (service: ServiceItem) => void;
  showStartAction?: boolean;
}

export default function ServiceCatalog({
  onSelectService,
  showStartAction = true,
}: ServiceCatalogProps) {
  const router = useRouter();

  const [services, setServices] = useState<ServiceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [selectedDepartment, setSelectedDepartment] = useState("ALL");
  const [selectedService, setSelectedService] = useState<ServiceItem | null>(null);
  const [serviceRequirements, setServiceRequirements] = useState<ServiceDetailRequirements | null>(null);
  const [loadingReqs, setLoadingReqs] = useState(false);
  const [startingApp, setStartingApp] = useState(false);

  useEffect(() => {
    fetchApi("/api/services/")
      .then((data) => {
        setServices(Array.isArray(data) ? data : []);
      })
      .catch((err) => {
        setError(err.message || "Failed to load government services catalog.");
      })
      .finally(() => setLoading(false));
  }, []);

  const loadRequirements = async (service: ServiceItem) => {
    setSelectedService(service);
    setLoadingReqs(true);
    setServiceRequirements(null);

    try {
      const reqs = await fetchApi(`/api/services/${service.code}/requirements`);
      setServiceRequirements(reqs);
    } catch {
      // Fallback gracefully to the base service definition from catalog
      setServiceRequirements({
        service_code: service.code,
        service_name: service.title,
        department: service.department,
        title: service.title,
        description: service.description || "",
        required_documents: service.required_documents || [],
        required_fields: service.required_fields || [],
        processing_time_days: service.processing_time_days,
        fee_amount: service.fee_amount,
      });
    } finally {
      setLoadingReqs(false);
    }
  };

  const handleStartApplication = async (service: ServiceItem) => {
    if (selectedService?.id === service.id && serviceRequirements) {
      const allowed = isJurisdictionSupported(
        serviceRequirements.jurisdiction_notice,
        serviceRequirements.jurisdiction_supported
      );
      if (!allowed) {
        const msg = getJurisdictionBlockMessage(
          serviceRequirements.jurisdiction_notice,
          serviceRequirements.jurisdiction_supported,
          serviceRequirements.jurisdiction
        );
        setError(msg || "Official requirements for this jurisdiction are not verified in SEVA. Application creation is disabled.");
        return;
      }
    }

    if (onSelectService) {
      onSelectService(service);
      return;
    }

    setStartingApp(true);
    try {
      const app = await fetchApi("/api/applications/", {
        method: "POST",
        body: JSON.stringify({
          service_id: service.id,
          form_data: {},
          remarks: "Initiated via Service Catalog",
        }),
      });
      router.push(`/applications/${app.id}`);
    } catch (err: any) {
      setError(err.message || "Failed to start application. Please try again.");
    } finally {
      setStartingApp(false);
    }
  };

  const departments = ["ALL", ...Array.from(new Set(services.map((s) => s.department).filter(Boolean)))];

  const filteredServices = services.filter((s) => {
    const term = search.toLowerCase();
    const matchesSearch =
      s.title.toLowerCase().includes(term) ||
      (s.description && s.description.toLowerCase().includes(term)) ||
      s.department.toLowerCase().includes(term);

    const matchesDept = selectedDepartment === "ALL" || s.department === selectedDepartment;
    return matchesSearch && matchesDept;
  });

  return (
    <div className="space-y-6">
      {/* Header and Search Filters */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-5">
          <div>
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">Official Service Directory</h2>
            <p className="text-sm text-slate-500 mt-0.5">
              Authoritative government services retrieved dynamically from official portals.
            </p>
          </div>

          <div className="relative w-full md:w-80">
            <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search by certificate, scheme, or keyword..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 transition"
            />
          </div>
        </div>

        {/* Department Filter Pills */}
        <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-100">
          {departments.map((dept) => (
            <button
              key={dept}
              onClick={() => setSelectedDepartment(dept)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wider transition ${
                selectedDepartment === dept
                  ? "bg-indigo-600 text-white shadow-xs"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {dept === "ALL" ? "All Departments" : humanizeKey(dept)}
            </button>
          ))}
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-sm flex items-center space-x-2">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
          <span>{error}</span>
        </div>
      )}

      {/* Main Grid: Service Cards */}
      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center space-y-3">
          <Loader2 className="h-8 w-8 text-indigo-600 animate-spin" />
          <span className="text-sm text-slate-500 font-medium">Loading authoritative services...</span>
        </div>
      ) : filteredServices.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center">
          <FileText className="h-10 w-10 text-slate-300 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-800">No matching services found</h3>
          <p className="text-xs text-slate-500 mt-1">
            Try searching for a different service name or department.
          </p>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredServices.map((service) => (
            <div
              key={service.id}
              className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs hover:shadow-md transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between gap-2 mb-3">
                  <span className="inline-flex items-center space-x-1 text-[11px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-indigo-50 text-indigo-700 border border-indigo-100">
                    <Building2 className="h-3 w-3" />
                    <span>{humanizeKey(service.department)}</span>
                  </span>

                  <span className="text-xs font-semibold text-slate-700 flex items-center">
                    <IndianRupee className="h-3 w-3 inline text-slate-500" />
                    <span>{service.fee_amount > 0 ? service.fee_amount.toFixed(2) : "Free"}</span>
                  </span>
                </div>

                <h3 className="text-base font-bold text-slate-900 mb-2 tracking-tight">
                  {service.title}
                </h3>

                <p className="text-xs text-slate-600 line-clamp-3 mb-4 leading-relaxed">
                  {service.description || "Official government citizen service."}
                </p>

                {/* Key metadata badges */}
                <div className="flex items-center space-x-4 text-xs text-slate-500 mb-5">
                  <span className="inline-flex items-center space-x-1">
                    <Clock className="h-3.5 w-3.5 text-slate-400" />
                    <span>{service.processing_time_days} days SLA</span>
                  </span>
                  <span className="inline-flex items-center space-x-1">
                    <FileText className="h-3.5 w-3.5 text-slate-400" />
                    <span>{service.required_documents?.length || 0} docs required</span>
                  </span>
                </div>
              </div>

              {/* Action buttons */}
              <div className="pt-4 border-t border-slate-100 flex items-center space-x-2">
                <button
                  onClick={() => loadRequirements(service)}
                  className="flex-1 px-3 py-2 text-xs font-semibold text-slate-700 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-xl transition"
                >
                  View Requirements
                </button>

                {showStartAction && (
                  <button
                    onClick={() => handleStartApplication(service)}
                    disabled={startingApp}
                    className="flex-1 px-3 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl transition flex items-center justify-center space-x-1 disabled:opacity-50"
                  >
                    <span>Apply Now</span>
                    <ChevronRight className="h-3 w-3" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Service Details & Government Requirements Modal */}
      {selectedService && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-2xl w-full max-h-[85vh] overflow-y-auto border border-slate-200 shadow-xl p-6 sm:p-8 space-y-6 animate-in fade-in zoom-in-95 duration-150">
            
            {/* Modal Header */}
            <div className="flex items-start justify-between border-b border-slate-100 pb-4">
              <div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-600 mb-1 block">
                  {humanizeKey(selectedService.department)} Department
                </span>
                <h3 className="text-xl font-bold text-slate-900 tracking-tight">
                  {selectedService.title}
                </h3>
              </div>
              <button
                onClick={() => setSelectedService(null)}
                className="text-slate-400 hover:text-slate-600 text-sm font-semibold p-1"
              >
                ✕ Close
              </button>
            </div>

            {loadingReqs ? (
              <div className="py-12 flex flex-col items-center justify-center space-y-3">
                <Loader2 className="h-6 w-6 text-indigo-600 animate-spin" />
                <span className="text-xs text-slate-500">Retrieving official rules...</span>
              </div>
            ) : serviceRequirements ? (
              <div className="space-y-5 text-sm">
                
                {/* Description */}
                <div>
                  <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                    Service Overview
                  </h4>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    {serviceRequirements.description}
                  </p>
                </div>

                {/* Responsible Authority */}
                {serviceRequirements.responsible_authority && (
                  <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block">
                      Competent Issuing Authority
                    </span>
                    <p className="text-xs font-semibold text-slate-900">
                      {serviceRequirements.responsible_authority.title}
                    </p>
                    <p className="text-xs text-slate-600">
                      Office: {serviceRequirements.responsible_authority.office}
                    </p>
                    {serviceRequirements.responsible_authority.appeal_authority && (
                      <p className="text-[11px] text-slate-500 mt-1">
                        Appellate Officer: {serviceRequirements.responsible_authority.appeal_authority}
                      </p>
                    )}
                  </div>
                )}

                {/* Statutory Metrics */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block">
                      Prescribed Timeline
                    </span>
                    <span className="text-sm font-bold text-slate-900 mt-0.5 block">
                      {serviceRequirements.processing_time_days} Working Days
                    </span>
                  </div>
                  <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block">
                      Statutory Fee
                    </span>
                    <span className="text-sm font-bold text-slate-900 mt-0.5 block">
                      {serviceRequirements.fee_amount > 0
                        ? `₹ ${serviceRequirements.fee_amount.toFixed(2)}`
                        : "No Fee (Free Service)"}
                    </span>
                  </div>
                </div>

                {/* Required Documents with Supported Alternatives */}
                <div>
                  <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                    Official Required Documents & Acceptable Alternatives
                  </h4>

                  <div className="space-y-2.5">
                    {serviceRequirements.required_documents.map((docType) => {
                      const options = serviceRequirements.document_options?.[docType] || [];
                      return (
                        <div
                          key={docType}
                          className="p-3 bg-white border border-slate-200 rounded-xl space-y-1.5"
                        >
                          <div className="flex items-center space-x-2">
                            <ShieldCheck className="h-4 w-4 text-indigo-600 shrink-0" />
                            <span className="text-xs font-bold text-slate-900">
                              {humanizeKey(docType)}
                            </span>
                            <span className="text-[10px] font-semibold uppercase px-1.5 py-0.5 bg-rose-50 text-rose-700 rounded-sm">
                              Mandatory
                            </span>
                          </div>

                          {options.length > 0 ? (
                            <div className="pl-6 space-y-1">
                              <span className="text-[11px] text-slate-500 font-medium block">
                                Any of the following will be accepted:
                              </span>
                              <div className="flex flex-wrap gap-1.5">
                                {options.map((opt, i) => (
                                  <span
                                    key={i}
                                    className="text-[11px] bg-slate-100 border border-slate-200 text-slate-700 px-2 py-0.5 rounded-md"
                                    title={opt.authority ? `Issued by: ${opt.authority}` : ""}
                                  >
                                    {opt.name}
                                    {opt.digital_verify && " (Digital)"}
                                  </span>
                                ))}
                              </div>
                            </div>
                          ) : (
                            <p className="text-xs text-slate-500 pl-6">
                              Original government issued {humanizeKey(docType)}.
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Unsupported Jurisdiction Notice / Blocker */}
                {!isJurisdictionSupported(serviceRequirements.jurisdiction_notice, serviceRequirements.jurisdiction_supported) && (
                  <div className="p-4 bg-amber-50 border-2 border-amber-300 rounded-2xl space-y-1 text-xs text-amber-950">
                    <span className="font-extrabold uppercase tracking-wide text-amber-900 block">
                      Application Disabled: Unverified Jurisdiction
                    </span>
                    <p className="leading-relaxed font-medium">
                      {getJurisdictionBlockMessage(
                        serviceRequirements.jurisdiction_notice,
                        serviceRequirements.jurisdiction_supported,
                        serviceRequirements.jurisdiction
                      )}
                    </p>
                  </div>
                )}

                {/* Modal CTA */}
                <div className="pt-4 border-t border-slate-100 flex justify-end space-x-3">
                  <button
                    onClick={() => setSelectedService(null)}
                    className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-800 bg-slate-100 hover:bg-slate-200 rounded-xl transition"
                  >
                    Close
                  </button>

                  {showStartAction && (
                    <button
                      onClick={() => {
                        const allowed = isJurisdictionSupported(
                          serviceRequirements.jurisdiction_notice,
                          serviceRequirements.jurisdiction_supported
                        );
                        if (!allowed) return;
                        setSelectedService(null);
                        handleStartApplication(selectedService);
                      }}
                      disabled={startingApp || !isJurisdictionSupported(serviceRequirements.jurisdiction_notice, serviceRequirements.jurisdiction_supported)}
                      className="px-5 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 rounded-xl transition flex items-center space-x-1.5 shadow-sm disabled:cursor-not-allowed"
                      title={!isJurisdictionSupported(serviceRequirements.jurisdiction_notice, serviceRequirements.jurisdiction_supported) ? "Application creation disabled for unverified jurisdiction" : undefined}
                    >
                      <Sparkles className="h-3.5 w-3.5" />
                      <span>
                        {isJurisdictionSupported(serviceRequirements.jurisdiction_notice, serviceRequirements.jurisdiction_supported)
                          ? `Start Application for ${selectedService.title}`
                          : "Application Disabled (Unverified Jurisdiction)"}
                      </span>
                    </button>
                  )}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
