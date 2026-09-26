/**
 * Resolves the backend API URL for Next.js rewrites and production configuration.
 *
 * In production/Vercel environments, this ensures an explicit backend URL
 * is configured (via NEXT_PUBLIC_API_URL, BACKEND_URL, API_URL, or RENDER_EXTERNAL_URL)
 * and prevents silently falling back to localhost:8000.
 */
function resolveBackendUrl(env = process.env) {
  const targetKeys = [
    "NEXT_PUBLIC_API_URL",
    "BACKEND_URL",
    "API_URL",
    "RENDER_EXTERNAL_URL",
    "NEXT_PUBLIC_BACKEND_URL",
    "SEVA_BACKEND_URL",
  ];

  let rawUrl = "";
  if (env && typeof env === "object") {
    // 1. Direct check
    for (const key of targetKeys) {
      if (typeof env[key] === "string" && env[key].trim()) {
        rawUrl = env[key].trim();
        break;
      }
    }

    // 2. Case-insensitive and trimmed key fallback
    if (!rawUrl) {
      for (const k of Object.keys(env)) {
        const normalizedKey = k.trim().toUpperCase();
        if (targetKeys.includes(normalizedKey)) {
          if (typeof env[k] === "string" && env[k].trim()) {
            rawUrl = env[k].trim();
            break;
          }
        }
      }
    }
  }

  if (rawUrl) {
    // Strip surrounding quotes if present
    let cleaned = rawUrl.replace(/^["']|["']$/g, "").trim();
    // Strip trailing slashes
    cleaned = cleaned.replace(/\/+$/, "");
    // Strip redundant trailing /api if present
    if (cleaned.endsWith("/api")) {
      cleaned = cleaned.slice(0, -4);
    }
    return cleaned;
  }

  const isVercel = env.VERCEL === "1" || Boolean(env.VERCEL_ENV);
  const isProduction = env.NODE_ENV === "production";

  if (isVercel || isProduction) {
    throw new Error(
      "[SEVA API CONFIG ERROR] Missing backend API URL in production deployment. " +
      "Environment variable NEXT_PUBLIC_API_URL or BACKEND_URL must be configured in Vercel. " +
      "Production rewrites must not target localhost:8000."
    );
  }

  // Local development fallback
  return "http://localhost:8000";
}

module.exports = {
  resolveBackendUrl,
};
