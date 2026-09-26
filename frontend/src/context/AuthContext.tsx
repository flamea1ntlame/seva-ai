"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import { useRouter } from "next/navigation";

export interface User {
  id: string;
  email: string;
  full_name: string;
  phone_number?: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (full_name: string, email: string, password: string, phone_number?: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const router = useRouter();

  const refreshUser = useCallback(async () => {
    setLoading(true);
    const token = typeof window !== "undefined" ? localStorage.getItem("seva_token") : null;
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }

    try {
      const userData = await fetchApi("/api/auth/me");
      setUser(userData);
    } catch {
      if (typeof window !== "undefined") {
        localStorage.removeItem("seva_token");
      }
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUser();

    // Listen to session expired event from fetchApi
    const handleExpired = () => {
      setUser(null);
      router.push("/login?session_expired=1");
    };

    window.addEventListener("seva:session_expired", handleExpired);
    return () => {
      window.removeEventListener("seva:session_expired", handleExpired);
    };
  }, [refreshUser, router]);

  const login = async (email: string, password: string) => {
    setLoading(true);
    try {
      const data = await fetchApi("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: email.trim(), password }),
      });

      if (typeof window !== "undefined") {
        localStorage.setItem("seva_token", data.access_token);
      }
      await refreshUser();
      router.push("/dashboard");
    } catch (err) {
      setLoading(false);
      throw err;
    }
  };

  const signup = async (full_name: string, email: string, password: string, phone_number?: string) => {
    setLoading(true);
    try {
      await fetchApi("/api/auth/signup", {
        method: "POST",
        body: JSON.stringify({
          full_name: full_name.trim(),
          email: email.trim(),
          password,
          phone_number: phone_number?.trim() || null,
        }),
      });

      // Auto login after signup
      await login(email, password);
    } catch (err) {
      setLoading(false);
      throw err;
    }
  };

  const logout = () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem("seva_token");
    }
    setUser(null);
    router.push("/login");
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
