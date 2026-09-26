"use client";

import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { LogOut, Menu, ShieldCheck } from "lucide-react";
import { useState } from "react";

export default function TopBar() {
  const { user, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <div className="md:hidden">
      <div className="bg-brand-900 text-white px-4 py-3 flex items-center justify-between shadow-xs z-20 relative">
        <Link href="/dashboard" className="flex items-center space-x-2 text-white">
          <div className="h-7 w-7 bg-primary-600 rounded-lg flex items-center justify-center">
            <ShieldCheck className="h-4 w-4 text-white" />
          </div>
          <span className="font-bold text-sm tracking-wide">SEVA AI</span>
        </Link>

        <button 
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="p-1.5 text-brand-300 hover:text-white rounded-md"
        >
          <Menu className="h-5 w-5" />
        </button>
      </div>

      {mobileMenuOpen && (
        <div className="bg-brand-800 absolute top-[52px] left-0 w-full z-10 shadow-lg border-b border-brand-700">
          <div className="p-2 space-y-1">
            <Link href="/dashboard" onClick={() => setMobileMenuOpen(false)} className="block px-3 py-2.5 text-sm font-medium text-brand-200 hover:bg-brand-700 rounded-md">Dashboard</Link>
            <Link href="/services" onClick={() => setMobileMenuOpen(false)} className="block px-3 py-2.5 text-sm font-medium text-brand-200 hover:bg-brand-700 rounded-md">Services</Link>
            <Link href="/applications" onClick={() => setMobileMenuOpen(false)} className="block px-3 py-2.5 text-sm font-medium text-brand-200 hover:bg-brand-700 rounded-md">Applications</Link>
            <Link href="/documents" onClick={() => setMobileMenuOpen(false)} className="block px-3 py-2.5 text-sm font-medium text-brand-200 hover:bg-brand-700 rounded-md">Documents</Link>
            <Link href="/activity" onClick={() => setMobileMenuOpen(false)} className="block px-3 py-2.5 text-sm font-medium text-brand-200 hover:bg-brand-700 rounded-md">Activity</Link>
            <Link href="/profile" onClick={() => setMobileMenuOpen(false)} className="block px-3 py-2.5 text-sm font-medium text-brand-200 hover:bg-brand-700 rounded-md">Profile</Link>
            <Link href="/help" onClick={() => setMobileMenuOpen(false)} className="block px-3 py-2.5 text-sm font-medium text-brand-200 hover:bg-brand-700 rounded-md">Help</Link>
            <Link href="/settings" onClick={() => setMobileMenuOpen(false)} className="block px-3 py-2.5 text-sm font-medium text-brand-200 hover:bg-brand-700 rounded-md">Settings</Link>
          </div>
          <div className="p-3 border-t border-brand-700 flex items-center justify-between bg-brand-900/50">
            <span className="text-sm text-brand-300 truncate pr-4">{user?.full_name}</span>
            <button onClick={logout} className="text-primary-400 hover:text-white p-1">
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
