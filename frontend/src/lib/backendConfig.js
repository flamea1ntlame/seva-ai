const DEFAULT_PRODUCTION_BACKEND_URL = "https://seva-ai-2hks.onrender.com";

/**
 * Resolves the backend API URL for Next.js rewrites and production configuration.
 *
 * Priority:
 * 1. NEXT_PUBLIC_API_URL
 * 2. BACKEND_URL
 * 3. API_URL
 * 4. SEVA_BACKEND_URL (and RENDER_EXTERNAL_URL / NEXT_PUBLIC_BACKEND_URL)
 *
 * On Vercel/production, if all environment variables are absent, falls back to:
 * https://seva-ai-2hks.onrender.com
 *
 * In local development only, falls back to:
 * http://localhost:8000
 */
function resolveBackendUrl(env = process.env) {
  const targetKeys = [
    "NEXT_PUBLIC_API_URL",
    "BACKEND_URL",
    "API_URL",
    "SEVA_BACKEND_URL",
    "RENDER_EXTERNAL_URL",
    "NEXT_PUBLIC_BACKEND_URL",
  ];

  let rawUrl = "";
  if (env && typeof env === "object") {
    // 1. Direct priority check
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

  // In Vercel or production builds, if all environment variables are absent,
  // use the verified SEVA Render backend. Never use localhost in production/Vercel.
  if (isVercel || isProduction) {
    return DEFAULT_PRODUCTION_BACKEND_URL;
  }

  // Local development fallback
  return "http://localhost:8000";
}

module.exports = {
  DEFAULT_PRODUCTION_BACKEND_URL,
  resolveBackendUrl,
};
