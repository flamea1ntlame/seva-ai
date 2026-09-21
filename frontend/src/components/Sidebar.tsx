"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import {
  LayoutDashboard,
  FileText,
  FolderLock,
  Activity,
  User,
  LogOut,
  HelpCircle,
  Settings,
  ShieldCheck
} from "lucide-react";

export default function Sidebar() {
  const pathname = usePathname();
  const { logout, user } = useAuth();

  const navigation = [
    { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
    { name: "Applications", href: "/applications", icon: FileText },
    { name: "Documents", href: "/documents", icon: FolderLock },
    { name: "Activity", href: "/activity", icon: Activity },
    { name: "Profile", href: "/profile", icon: User },
  ];

  const isActive = (href: string) => {
    return pathname === href || (href !== "/dashboard" && pathname?.startsWith(href));
  };

  return (
    <div className="hidden md:flex flex-col w-64 bg-brand-900 border-r border-brand-800 text-slate-300 min-h-screen fixed left-0 top-0">
      <div className="p-6">
        <Link href="/dashboard" className="flex items-center space-x-3 text-white">
          <div className="h-8 w-8 bg-primary-600 rounded-xl flex items-center justify-center shadow-xs">
            <ShieldCheck className="h-5 w-5 text-white" />
          </div>
          <div>
            <span className="font-bold text-lg tracking-wide block leading-none">SEVA</span>
            <span className="text-[10px] text-primary-200 font-medium uppercase tracking-widest block mt-0.5">Assistant</span>
          </div>
        </Link>
      </div>

      <div className="flex-1 px-4 space-y-1 mt-6">
        {navigation.map((item) => {
          const active = isActive(item.href);
          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                active
                  ? "bg-primary-600/10 text-primary-400"
                  : "hover:bg-brand-800/50 hover:text-white"
              }`}
            >
              <item.icon className={`h-4 w-4 ${active ? "text-primary-400" : "text-brand-400"}`} />
              <span>{item.name}</span>
            </Link>
          );
        })}
      </div>

      <div className="p-4 mt-auto">
        <div className="mb-4 px-3 space-y-1">
          <Link href="/help" className="flex items-center space-x-3 py-2 text-sm font-medium text-brand-400 hover:text-white transition-colors">
            <HelpCircle className="h-4 w-4" />
            <span>Help</span>
          </Link>
          <Link href="/settings" className="flex items-center space-x-3 py-2 text-sm font-medium text-brand-400 hover:text-white transition-colors">
            <Settings className="h-4 w-4" />
            <span>Settings</span>
          </Link>
        </div>
        
        <div className="bg-brand-800/40 rounded-xl p-3 border border-brand-700/50 flex items-center justify-between">
          <div className="flex items-center space-x-3 truncate">
            <div className="h-8 w-8 rounded-full bg-brand-700 flex items-center justify-center text-xs font-bold text-white shrink-0">
              {user?.full_name?.charAt(0) || "U"}
            </div>
            <div className="truncate">
              <p className="text-sm font-medium text-white truncate">{user?.full_name}</p>
              <p className="text-[10px] text-brand-400 truncate">{user?.email}</p>
            </div>
          </div>
          <button onClick={logout} className="p-1.5 text-brand-400 hover:text-white hover:bg-brand-700 rounded-lg transition-colors" title="Log out">
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
