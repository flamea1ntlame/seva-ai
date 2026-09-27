"use client";

import React from "react";
import ServiceCatalog from "@/components/ServiceCatalog";

export default function ServicesPage() {
  return (
    <div className="max-w-6xl mx-auto space-y-6 pb-12">
      <div className="space-y-1">
        <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Government Services Catalog</h1>
        <p className="text-sm text-slate-500">
          Explore all digital public services, review requirements, fees, timelines, and start applications.
        </p>
      </div>

      <ServiceCatalog />
    </div>
  );
}
