"use client";

import Link from "next/link";
import { ShieldCheck, FileText, CheckCircle2, ArrowRight, Compass } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export default function Home() {
  const { user } = useAuth();

  return (
    <div className="max-w-6xl mx-auto px-4 py-16 sm:px-6 lg:px-8 text-center space-y-12">
      <div>
        <div className="inline-flex items-center space-x-2 bg-indigo-50 border border-indigo-100 text-indigo-700 px-3.5 py-1 rounded-full text-xs font-semibold mb-6">
          <ShieldCheck className="h-4 w-4" />
          <span>Official Digital Public Services Platform</span>
        </div>

        <h1 className="text-4xl font-extrabold text-slate-900 sm:text-5xl tracking-tight mb-5">
          Government Services <br />
          <span className="text-indigo-600">Transparent & Assisted by AI</span>
        </h1>

        <p className="text-base sm:text-lg text-slate-600 max-w-2xl mx-auto leading-relaxed">
          Access state and central government certificates, verify eligibility against official rules,
          securely store documents, and track applications in real time.
        </p>

        <div className="flex flex-col sm:flex-row justify-center items-center gap-3 mt-8">
          {user ? (
            <Link
              href="/dashboard"
              className="w-full sm:w-auto px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm rounded-xl shadow-xs flex items-center justify-center space-x-2 transition"
            >
              <span>Go to Citizen Dashboard</span>
              <ArrowRight className="h-4 w-4" />
            </Link>
          ) : (
            <>
              <Link
                href="/signup"
                className="w-full sm:w-auto px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm rounded-xl shadow-xs flex items-center justify-center space-x-2 transition"
              >
                <span>Create Citizen Account</span>
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/login"
                className="w-full sm:w-auto px-6 py-3 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 font-semibold text-sm rounded-xl flex items-center justify-center transition"
              >
                Sign In
              </Link>
            </>
          )}

          <Link
            href="/services"
            className="w-full sm:w-auto px-6 py-3 bg-slate-100 hover:bg-slate-200 text-slate-800 font-semibold text-sm rounded-xl flex items-center justify-center space-x-2 transition"
          >
            <Compass className="h-4 w-4" />
            <span>Explore Service Directory</span>
          </Link>
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-6 text-left pt-6">
        <div className="bg-white p-6 rounded-3xl border border-slate-200 shadow-xs space-y-2">
          <div className="h-10 w-10 bg-indigo-50 text-indigo-600 rounded-xl flex items-center justify-center mb-3 border border-indigo-100">
            <FileText className="h-5 w-5" />
          </div>
          <h3 className="font-bold text-slate-900 text-sm">Authoritative Rules Grounding</h3>
          <p className="text-xs text-slate-500 leading-relaxed">
            SEVA AI validates required and alternative documents directly against official state gazettes and regulations.
          </p>
        </div>

        <div className="bg-white p-6 rounded-3xl border border-slate-200 shadow-xs space-y-2">
          <div className="h-10 w-10 bg-emerald-50 text-emerald-600 rounded-xl flex items-center justify-center mb-3 border border-emerald-100">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <h3 className="font-bold text-slate-900 text-sm">Consent-Controlled Vault</h3>
          <p className="text-xs text-slate-500 leading-relaxed">
            Your identity and financial evidence remain encrypted. Information is only shared with departments upon your explicit consent.
          </p>
        </div>

        <div className="bg-white p-6 rounded-3xl border border-slate-200 shadow-xs space-y-2">
          <div className="h-10 w-10 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center mb-3 border border-blue-100">
            <CheckCircle2 className="h-5 w-5" />
          </div>
          <h3 className="font-bold text-slate-900 text-sm">Full Lifecycle Tracking</h3>
          <p className="text-xs text-slate-500 leading-relaxed">
            Monitor each milestone from initial preparation and document verification through departmental processing and issuance.
          </p>
        </div>
      </div>
    </div>
  );
}
