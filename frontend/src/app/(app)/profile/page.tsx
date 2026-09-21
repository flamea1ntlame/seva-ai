"use client";

import React from "react";
import { useAuth } from "@/context/AuthContext";
import { User, ShieldCheck, Mail, LogOut } from "lucide-react";

export default function ProfilePage() {
  const { user, logout } = useAuth();

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      
      <div className="mb-8">
        <h1 className="text-2xl font-extrabold text-brand-900">Your Profile</h1>
        <p className="text-sm text-brand-500 mt-1">Manage your SEVA account settings.</p>
      </div>

      <div className="bg-white rounded-3xl border border-brand-200 shadow-sm overflow-hidden">
        <div className="bg-brand-900 p-8 sm:p-12 text-center relative overflow-hidden">
          <div className="absolute top-0 right-0 -mr-20 -mt-20 w-64 h-64 bg-primary-600/30 rounded-full blur-3xl pointer-events-none"></div>
          
          <div className="relative z-10 flex flex-col items-center">
            <div className="h-24 w-24 bg-white rounded-full flex items-center justify-center text-4xl font-bold text-primary-600 shadow-lg border-4 border-brand-800 mb-4">
              {user?.full_name?.charAt(0) || "U"}
            </div>
            <h2 className="text-2xl font-bold text-white">{user?.full_name}</h2>
            <div className="flex items-center space-x-2 mt-2 bg-brand-800/50 px-3 py-1 rounded-full border border-brand-700">
              <ShieldCheck className="h-4 w-4 text-success-400" />
              <span className="text-xs text-brand-200 font-medium tracking-wide">Verified Citizen</span>
            </div>
          </div>
        </div>

        <div className="p-8 sm:p-12 space-y-8">
          
          <div>
            <h3 className="text-sm font-bold text-brand-900 flex items-center space-x-2 uppercase tracking-wider mb-4 border-b border-brand-100 pb-2">
              <User className="h-4 w-4 text-primary-500" />
              <span>Personal Details</span>
            </h3>
            
            <div className="space-y-4">
              <div>
                <span className="block text-[10px] font-bold text-brand-500 uppercase tracking-wider mb-1">Full Name</span>
                <span className="text-sm font-medium text-brand-900">{user?.full_name}</span>
              </div>
              <div>
                <span className="block text-[10px] font-bold text-brand-500 uppercase tracking-wider mb-1">Citizen ID</span>
                <span className="text-sm font-mono text-brand-700 bg-brand-50 px-2 py-0.5 rounded border border-brand-100">{user?.id}</span>
              </div>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-bold text-brand-900 flex items-center space-x-2 uppercase tracking-wider mb-4 border-b border-brand-100 pb-2">
              <Mail className="h-4 w-4 text-primary-500" />
              <span>Contact Information</span>
            </h3>
            
            <div className="space-y-4">
              <div>
                <span className="block text-[10px] font-bold text-brand-500 uppercase tracking-wider mb-1">Email Address</span>
                <span className="text-sm font-medium text-brand-900">{user?.email}</span>
              </div>
            </div>
          </div>

          <div className="pt-6 border-t border-brand-100 flex justify-end">
            <button 
              onClick={logout}
              className="flex items-center space-x-2 px-6 py-2.5 bg-error-50 hover:bg-error-100 text-error-700 font-bold rounded-xl transition-colors border border-error-200 text-sm"
            >
              <LogOut className="h-4 w-4" />
              <span>Sign Out</span>
            </button>
          </div>

        </div>
      </div>

    </div>
  );
}
