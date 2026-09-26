export type ApiErrorType =
  | "OFFLINE"
  | "NETWORK"
  | "TIMEOUT"
  | "CORS"
  | "CLIENT_ERROR"
  | "SERVER_ERROR"
  | "PARSE_ERROR";

export class ApiError extends Error {
  status: number;
  errorType: ApiErrorType;
  endpoint?: string;

  constructor(
    message: string,
    status: number,
    errorType: ApiErrorType = "NETWORK",
    endpoint?: string
  ) {
    super(message);
    this.status = status;
    this.errorType = errorType;
    this.endpoint = endpoint;
    this.name = "ApiError";
  }
}

/**
 * Returns the resolved API base URL.
 * In production browser environments, if NEXT_PUBLIC_API_URL is unset,
 * returns an empty string so requests route through Next.js proxy/rewrites
 * rather than attempting to connect to localhost:8000 on the citizen's machine.
 */
export function getApiBaseUrl(): string {
  const envUrl = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (envUrl) {
    let cleaned = envUrl.replace(/\/+$/, "");
    if (cleaned.endsWith("/api")) {
      cleaned = cleaned.slice(0, -4);
    }
    return cleaned;
  }

  if (typeof window !== "undefined") {
    const isLocalhost =
      window.location.hostname === "localhost" ||
      window.location.hostname === "127.0.0.1" ||
      window.location.hostname === "0.0.0.0";
    if (!isLocalhost) {
      return "";
    }
  }

  if (process.env.NODE_ENV === "production" || process.env.VERCEL === "1") {
    return "https://seva-ai-2hks.onrender.com";
  }

  return "http://localhost:8000";
}

export async function fetchApi(endpoint: string, options: RequestInit = {}) {
  const rawToken =
    typeof window !== "undefined" && typeof localStorage !== "undefined"
      ? localStorage.getItem("seva_token")
      : null;
  const token =
    rawToken && rawToken !== "null" && rawToken !== "undefined" && rawToken.trim() !== ""
      ? rawToken.trim()
      : null;
  const baseUrl = getApiBaseUrl();
  const targetUrl = `${baseUrl}${endpoint}`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  try {
    const response = await fetch(targetUrl, {
      cache: "no-store",
      ...options,
      headers,
    });

    if (response.status === 401) {
      let errorData: any = {};
      try {
        errorData = await response.json();
      } catch {
        errorData = {};
      }

      const serverMsg =
        typeof errorData.detail === "string"
          ? errorData.detail
          : Array.isArray(errorData.detail)
          ? errorData.detail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(", ")
          : errorData.message || null;

      const isLoginOrSignup =
        endpoint.includes("/auth/login") || endpoint.includes("/auth/signup");
      const isAuthVerification =
        endpoint.endsWith("/auth/me") || endpoint.includes("/auth/me");

      if (isAuthVerification) {
        if (typeof window !== "undefined") {
          if (typeof localStorage !== "undefined") {
            localStorage.removeItem("seva_token");
          }
          if (typeof window.dispatchEvent === "function") {
            window.dispatchEvent(new CustomEvent("seva:session_expired"));
          }
        }
        throw new ApiError(
          "Your session has expired. Please sign in again.",
          401,
          "CLIENT_ERROR",
          endpoint
        );
      }

      if (isLoginOrSignup) {
        throw new ApiError(
          serverMsg || "Incorrect email or password.",
          401,
          "CLIENT_ERROR",
          endpoint
        );
      }

      // For arbitrary background/data endpoints, preserve error and do NOT destroy the session
      throw new ApiError(
        serverMsg || "Unauthorized access.",
        401,
        "CLIENT_ERROR",
        endpoint
      );
    }

    if (!response.ok) {
      let errorData: any = {};
      try {
        errorData = await response.json();
      } catch {
        errorData = {};
      }

      const serverMsg =
        typeof errorData.detail === "string"
          ? errorData.detail
          : Array.isArray(errorData.detail)
          ? errorData.detail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(", ")
          : errorData.message || null;

      // Distinguish 4xx (client errors) from 5xx (server errors)
      if (response.status >= 500) {
        let msg = serverMsg;
        if (!msg) {
          if (response.status === 502) {
            msg = "SEVA backend service is temporarily unreachable (Bad Gateway). The server may be restarting.";
          } else if (response.status === 503) {
            msg = "SEVA services are temporarily unavailable for maintenance. Please try again shortly.";
          } else if (response.status === 504) {
            msg = "SEVA server took too long to respond (Gateway Timeout). Please try again.";
          } else {
            msg = `SEVA service error (${response.status}). Please try again later.`;
          }
        }
        throw new ApiError(msg, response.status, "SERVER_ERROR", endpoint);
      } else {
        // 4xx Client Error
        let msg = serverMsg;
        if (!msg) {
          if (response.status === 403) {
            msg = "Access denied. You do not have permission to perform this action.";
          } else if (response.status === 404) {
            msg = "The requested SEVA service or resource was not found.";
          } else if (response.status === 409) {
            msg = "Conflict: An application or record with these details already exists.";
          } else if (response.status === 422) {
            msg = "Invalid input data. Please correct the fields and try again.";
          } else if (response.status === 429) {
            msg = "Too many requests. Please wait a moment before trying again.";
          } else {
            msg = `Request failed (${response.status}). Please check your input and try again.`;
          }
        }
        throw new ApiError(msg, response.status, "CLIENT_ERROR", endpoint);
      }
    }

    try {
      return await response.json();
    } catch {
      // Handles empty 200 responses or non-JSON payloads safely
      return null;
    }
  } catch (err: any) {
    if (err instanceof ApiError) {
      throw err;
    }

    // Check if the citizen's device is truly offline
    if (typeof navigator !== "undefined" && navigator.onLine === false) {
      throw new ApiError(
        "You appear to be offline. Please check your internet connection.",
        0,
        "OFFLINE",
        endpoint
      );
    }

    // Check for client-side request timeout
    if (err?.name === "AbortError") {
      throw new ApiError(
        "Request timed out while contacting SEVA services. Please try again.",
        0,
        "TIMEOUT",
        endpoint
      );
    }

    // Check if request failed due to cross-origin / CORS restriction
    const isCrossOrigin =
      typeof window !== "undefined" &&
      targetUrl.startsWith("http") &&
      !targetUrl.startsWith(window.location.origin);

    if (isCrossOrigin) {
      throw new ApiError(
        "Unable to reach SEVA services. The server may be restarting or cross-origin requests are blocked.",
        0,
        "CORS",
        endpoint
      );
    }

    // General network unreachable error
    throw new ApiError(
      "Unable to connect to SEVA services. The server may be temporarily down or starting up.",
      0,
      "NETWORK",
      endpoint
    );
  }
}

/**
 * Validates the current session against /api/auth/me.
 * If the session is invalid/expired (HTTP 401), clears stale auth state
 * from localStorage and dispatches the 'seva:session_expired' event.
 * Returns true if the session is valid, false if invalid/expired.
 */
export async function validateSession(): Promise<boolean> {
  const rawToken =
    typeof window !== "undefined" && typeof localStorage !== "undefined"
      ? localStorage.getItem("seva_token")
      : null;
  const token =
    rawToken && rawToken !== "null" && rawToken !== "undefined" && rawToken.trim() !== ""
      ? rawToken.trim()
      : null;

  if (!token) {
    if (typeof window !== "undefined" && typeof localStorage !== "undefined") {
      localStorage.removeItem("seva_token");
    }
    if (typeof window !== "undefined" && typeof window.dispatchEvent === "function") {
      window.dispatchEvent(new CustomEvent("seva:session_expired"));
    }
    return false;
  }

  try {
    await fetchApi("/api/auth/me");
    return true;
  } catch (err: any) {
    const is401 = err instanceof ApiError ? err.status === 401 : err?.status === 401;
    if (is401) {
      if (typeof window !== "undefined" && typeof localStorage !== "undefined") {
        localStorage.removeItem("seva_token");
      }
      if (typeof window !== "undefined" && typeof window.dispatchEvent === "function") {
        window.dispatchEvent(new CustomEvent("seva:session_expired"));
      }
      return false;
    }
    // Network or server error (502, 503, offline): do not clear session
    return true;
  }
}

/**
 * Controlled session validation for protected endpoints.
 * When a protected endpoint (e.g. applications, requirements, documents, chat)
 * returns 401, this function verifies if the session is actually invalid via /api/auth/me.
 * If invalid, it clears stale auth state, dispatches 'seva:session_expired',
 * and redirects to /login?session_expired=1.
 */
export async function handleSessionValidationOn401(
  err: any,
  router?: { push: (url: string) => void; replace?: (url: string) => void }
): Promise<boolean> {
  const is401 = err instanceof ApiError ? err.status === 401 : err?.status === 401;
  if (!is401) return true;

  const isValid = await validateSession();
  if (!isValid && router && typeof router.push === "function") {
    router.push("/login?session_expired=1");
  }
  return isValid;
}


