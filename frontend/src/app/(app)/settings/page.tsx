"use client";

import React from "react";
import { Settings, User, Bell, Shield, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";

export default function SettingsPage() {
  const { user, logout } = useAuth();

  return (
    <div className="max-w-4xl mx-auto space-y-8 pb-12">
      <div className="flex items-center space-x-3 mb-6">
        <div className="h-10 w-10 bg-brand-100 rounded-xl flex items-center justify-center text-brand-600">
          <Settings className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-extrabold text-brand-900">Settings</h1>
          <p className="text-sm text-brand-500">Manage your SEVA AI preferences.</p>
        </div>
      </div>

      <div className="bg-warning-50 border border-warning-200 p-4 rounded-xl mb-6 flex items-start space-x-3">
        <Shield className="h-5 w-5 text-warning-600 shrink-0 mt-0.5" />
        <div>
          <h4 className="text-sm font-bold text-warning-800">Account data is managed through services</h4>
          <p className="text-xs text-warning-700 mt-1">
            SEVA AI connects directly to your verified government identity. You cannot change your core identity data here. If you need to update your address or name, you must use SEVA to apply for an official identity update.
          </p>
        </div>
      </div>

      <div className="space-y-4">
        {/* Profile Shortcut */}
        <div className="bg-white rounded-2xl border border-brand-200 p-4 shadow-sm flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="h-10 w-10 bg-brand-50 rounded-xl flex items-center justify-center text-brand-600">
              <User className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-bold text-brand-900 text-sm">Citizen Profile</h3>
              <p className="text-xs text-brand-500">{user?.full_name || "View your verified identity details"}</p>
            </div>
          </div>
          <Link href="/profile" className="p-2 hover:bg-brand-50 rounded-lg transition-colors group">
            <ChevronRight className="h-5 w-5 text-brand-400 group-hover:text-brand-900" />
          </Link>
        </div>

        {/* Notifications (UI Only) */}
        <div className="bg-white rounded-2xl border border-brand-200 p-4 shadow-sm flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="h-10 w-10 bg-brand-50 rounded-xl flex items-center justify-center text-brand-600">
              <Bell className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-bold text-brand-900 text-sm">Notifications</h3>
              <p className="text-xs text-brand-500">Receive alerts when application status changes.</p>
            </div>
          </div>
          <div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" className="sr-only peer" defaultChecked disabled />
              <div className="w-11 h-6 bg-brand-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-brand-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-500 opacity-70"></div>
            </label>
          </div>
        </div>

      </div>
      
      <div className="mt-8 border-t border-brand-200 pt-8">
        <button 
          onClick={logout}
          className="text-sm font-bold text-danger-600 hover:text-danger-700 px-4 py-2 hover:bg-danger-50 rounded-lg transition-colors"
        >
          Sign out of SEVA
        </button>
      </div>
    </div>
  );
}
