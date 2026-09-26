const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

export async function fetchApi(endpoint: string, options: RequestInit = {}) {
  const token = typeof window !== "undefined" ? localStorage.getItem("seva_token") : null;
  
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      cache: "no-store",
      ...options,
      headers,
    });

    if (response.status === 401) {
      if (typeof window !== "undefined") {
        // Clear expired or invalid credentials
        localStorage.removeItem("seva_token");
        // Dispatch session expired event so AuthProvider can sync state
        window.dispatchEvent(new CustomEvent("seva:session_expired"));
      }
      throw new ApiError("Your session has expired. Please sign in again.", 401);
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: "An unexpected error occurred." }));
      const errorMsg = typeof errorData.detail === "string" 
        ? errorData.detail 
        : (errorData.message || "Request failed. Please try again.");
      throw new ApiError(errorMsg, response.status);
    }

    return response.json();
  } catch (err: any) {
    if (err instanceof ApiError) {
      throw err;
    }
    // Handle network timeout or server unreachable gracefully without raw stack traces
    throw new ApiError("Unable to reach SEVA services. Please check your internet connection.", 0);
  }
}
