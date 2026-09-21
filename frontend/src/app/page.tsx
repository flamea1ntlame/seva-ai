"use client";

import Link from "next/link";
import { ShieldCheck, FileText, CheckCircle2, ArrowRight } from "lucide-react";

export default function Home() {
  return (
    <div className="max-w-6xl mx-auto px-4 py-16 sm:px-6 lg:px-8 text-center">
      <div className="inline-flex items-center space-x-2 bg-indigo-50 border border-indigo-100 text-indigo-700 px-3 py-1 rounded-full text-xs font-semibold mb-6">
        <ShieldCheck className="h-4 w-4" />
        <span>Unified Citizen Service Platform</span>
      </div>

      <h1 className="text-4xl font-extrabold text-slate-900 sm:text-5xl tracking-tight mb-6">
        Government Services <br />
        <span className="text-indigo-600">Simplified & Streamlined</span>
      </h1>

      <p className="text-lg text-slate-600 max-w-2xl mx-auto mb-8">
        Access income certificates, birth registrations, driving licenses, and manage your secure digital document vault all in one place.
      </p>

      <div className="flex flex-col sm:flex-row justify-center items-center gap-4 mb-16">
        <Link
          href="/signup"
          className="w-full sm:w-auto px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-xl shadow-md flex items-center justify-center space-x-2 transition"
        >
          <span>Create Account</span>
          <ArrowRight className="h-4 w-4" />
        </Link>
        <Link
          href="/login"
          className="w-full sm:w-auto px-6 py-3 bg-white hover:bg-slate-100 text-slate-700 border border-slate-300 font-medium rounded-xl flex items-center justify-center transition"
        >
          Sign In
        </Link>
      </div>

      <div className="grid md:grid-cols-3 gap-8 text-left">
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
          <div className="h-10 w-10 bg-indigo-100 text-indigo-600 rounded-lg flex items-center justify-center mb-4">
            <FileText className="h-5 w-5" />
          </div>
          <h3 className="font-semibold text-slate-900 mb-2">Service Catalog</h3>
          <p className="text-sm text-slate-500">
            Easily apply for government certificates with transparent timeline estimates and fee structures.
          </p>
        </div>

        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
          <div className="h-10 w-10 bg-indigo-100 text-indigo-600 rounded-lg flex items-center justify-center mb-4">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <h3 className="font-semibold text-slate-900 mb-2">Secure Document Vault</h3>
          <p className="text-sm text-slate-500">
            Store identity documents safely with explicit consent controls over data access.
          </p>
        </div>

        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
          <div className="h-10 w-10 bg-indigo-100 text-indigo-600 rounded-lg flex items-center justify-center mb-4">
            <CheckCircle2 className="h-5 w-5" />
          </div>
          <h3 className="font-semibold text-slate-900 mb-2">Application Tracking</h3>
          <p className="text-sm text-slate-500">
            Real-time status updates and event logs for all your submitted service requests.
          </p>
        </div>
      </div>
    </div>
  );
}
