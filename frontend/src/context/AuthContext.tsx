"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { fetchApi, ApiError } from "@/lib/api";
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
  refreshUser: () => Promise<User | null>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const router = useRouter();

  const refreshUser = useCallback(async (): Promise<User | null> => {
    setLoading(true);
    const rawToken = typeof window !== "undefined" ? localStorage.getItem("seva_token") : null;
    const token =
      rawToken && rawToken !== "null" && rawToken !== "undefined" && rawToken.trim() !== ""
        ? rawToken.trim()
        : null;

    if (!token) {
      setUser(null);
      setLoading(false);
      return null;
    }

    try {
      const userData = await fetchApi("/api/auth/me");
      setUser(userData);
      return userData;
    } catch (err: any) {
      const isAuthFailure = err instanceof ApiError ? err.status === 401 : err?.status === 401;

      if (isAuthFailure) {
        // (b) Invalid or expired token: clear credentials and reset user
        if (typeof window !== "undefined") {
          localStorage.removeItem("seva_token");
        }
        setUser(null);
      } else {
        // (c) Temporary backend / network failure (502, 503, timeout, offline):
        // Do NOT silently delete the token!
        // Leave existing token intact so citizen is not logged out due to network hiccup.
      }
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUser().catch(() => {
      // Safe catch for initial mount:
      // If 401: token cleared, user null
      // If network offline: token preserved, user null or unchanged
    });

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

      if (!data?.access_token) {
        throw new Error("Invalid response: missing access token from server.");
      }

      if (typeof window !== "undefined") {
        localStorage.setItem("seva_token", data.access_token);
      }

      // Verify authenticated user before navigating to dashboard
      let verifiedUser: User | null = null;
      try {
        verifiedUser = await refreshUser();
      } catch (verifyErr: any) {
        throw new Error(
          verifyErr?.message || "Failed to verify citizen session after login."
        );
      }

      if (!verifiedUser) {
        throw new Error("Unable to establish verified citizen session.");
      }

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
