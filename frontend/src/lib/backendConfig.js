/**
 * Resolves the backend API URL for Next.js rewrites and production configuration.
 *
 * In production/Vercel environments, this ensures an explicit backend URL
 * is configured (via NEXT_PUBLIC_API_URL, BACKEND_URL, API_URL, or RENDER_EXTERNAL_URL)
 * and prevents silently falling back to localhost:8000.
 */
function resolveBackendUrl(env = process.env) {
  const envUrl = (
    env.NEXT_PUBLIC_API_URL ||
    env.BACKEND_URL ||
    env.API_URL ||
    env.RENDER_EXTERNAL_URL ||
    ""
  ).trim();

  if (envUrl) {
    let cleaned = envUrl.replace(/\/+$/, "");
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
