"use client";

import React, { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { Lock, Mail, AlertCircle, Info, Loader2, ShieldCheck } from "lucide-react";

function LoginFormContent() {
  const { login, user, loading: authLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [email, setEmail] = useState("citizen@example.com");
  const [password, setPassword] = useState("password123");
  const [error, setError] = useState("");
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [sessionExpiredNotice, setSessionExpiredNotice] = useState(false);

  // Redirect authenticated citizens directly to dashboard
  useEffect(() => {
    if (!authLoading && user) {
      router.replace("/dashboard");
    }
  }, [user, authLoading, router]);

  // Check if citizen landed here because their session expired
  useEffect(() => {
    if (searchParams.get("session_expired") === "1") {
      setSessionExpiredNotice(true);
    }
  }, [searchParams]);

  const validate = () => {
    const errors: Record<string, string> = {};
    if (!email.trim()) {
      errors.email = "Email address is required.";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      errors.email = "Please enter a valid email address.";
    }

    if (!password) {
      errors.password = "Password is required.";
    } else if (password.length < 6) {
      errors.password = "Password must be at least 6 characters.";
    }

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting || authLoading) return;

    setError("");
    setSessionExpiredNotice(false);

    if (!validate()) return;

    setIsSubmitting(true);

    try {
      await login(email, password);
    } catch (err: any) {
      setError(err.message || "Invalid email or password. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (authLoading) {
    return (
      <div className="min-h-[80vh] flex items-center justify-center">
        <Loader2 className="h-8 w-8 text-indigo-600 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4 py-12">
      <div className="max-w-md w-full bg-white rounded-2xl border border-slate-200 p-8 shadow-sm">
        
        {/* Header */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-indigo-50 text-indigo-600 mb-3 border border-indigo-100">
            <ShieldCheck className="h-6 w-6" />
          </div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Citizen Sign In</h2>
          <p className="text-sm text-slate-500 mt-1">Access verified digital government services via SEVA AI</p>
        </div>

        {/* Session Expired Notice */}
        {sessionExpiredNotice && (
          <div className="mb-4 p-3.5 bg-amber-50 border border-amber-200 text-amber-800 text-xs rounded-xl flex items-start space-x-2">
            <Info className="h-4 w-4 shrink-0 text-amber-600 mt-0.5" />
            <span>Your session has expired for security reasons. Please sign in again.</span>
          </div>
        )}

        {/* Global Error Banner */}
        {error && (
          <div className="mb-4 p-3.5 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded-xl flex items-start space-x-2">
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-500 mt-0.5" />
            <span className="font-medium">{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Email Address
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                <Mail className="h-4 w-4" />
              </div>
              <input
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  if (validationErrors.email) setValidationErrors(prev => ({ ...prev, email: "" }));
                }}
                className={`w-full pl-9 pr-3 py-2.5 border rounded-xl text-sm text-slate-900 focus:outline-none focus:ring-2 transition ${
                  validationErrors.email
                    ? "border-rose-300 focus:ring-rose-400 bg-rose-50/20"
                    : "border-slate-300 focus:ring-indigo-500"
                }`}
                placeholder="citizen@example.com"
                disabled={isSubmitting}
              />
            </div>
            {validationErrors.email && (
              <p className="text-xs text-rose-600 mt-1 font-medium">{validationErrors.email}</p>
            )}
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Password
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                <Lock className="h-4 w-4" />
              </div>
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (validationErrors.password) setValidationErrors(prev => ({ ...prev, password: "" }));
                }}
                className={`w-full pl-9 pr-3 py-2.5 border rounded-xl text-sm text-slate-900 focus:outline-none focus:ring-2 transition ${
                  validationErrors.password
                    ? "border-rose-300 focus:ring-rose-400 bg-rose-50/20"
                    : "border-slate-300 focus:ring-indigo-500"
                }`}
                placeholder="••••••••"
                disabled={isSubmitting}
              />
            </div>
            {validationErrors.password && (
              <p className="text-xs text-rose-600 mt-1 font-medium">{validationErrors.password}</p>
            )}
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold rounded-xl shadow-sm transition disabled:opacity-50 flex items-center justify-center space-x-2"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Signing in...</span>
              </>
            ) : (
              <span>Sign In</span>
            )}
          </button>
        </form>

        <div className="mt-6 text-center text-xs text-slate-500">
          Don't have an account?{" "}
          <Link href="/signup" className="font-semibold text-indigo-600 hover:underline">
            Register as a new citizen
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-[80vh] flex items-center justify-center">
          <Loader2 className="h-8 w-8 text-indigo-600 animate-spin" />
        </div>
      }
    >
      <LoginFormContent />
    </Suspense>
  );
}
