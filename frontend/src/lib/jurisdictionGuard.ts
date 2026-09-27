/**
 * Centralized Jurisdiction Progression Guard for SEVA AI.
 * 
 * Prevents application creation and submission when a service is requested for an
 * unsupported / unverified jurisdiction.
 * 
 * RULES:
 * - When jurisdiction_notice?.supported === false OR jurisdiction_supported === false:
 *   - Disable "Start Application"
 *   - Prevent application creation through that UI path
 *   - Disable/prevent "Proceed to Submit" / "Authorize & Submit"
 *   - Clearly tell citizen that official requirements are not verified
 *   - Never silently fall back to another jurisdiction
 * - Missing jurisdiction notice or supported jurisdiction does NOT block progression.
 */

export interface JurisdictionNotice {
  supported?: boolean;
  message?: string;
  requested_jurisdiction?: string;
  supported_jurisdictions?: string[];
  verified_jurisdictions?: string[];
}

/**
 * Checks whether the jurisdiction is supported and authorized for progression.
 */
export function isJurisdictionSupported(
  notice?: JurisdictionNotice | null,
  jurisdictionSupportedFlag?: boolean
): boolean {
  if (jurisdictionSupportedFlag === false) {
    return false;
  }
  if (notice && notice.supported === false) {
    return false;
  }
  return true;
}

/**
 * Returns a citizen-friendly message explaining why progression is blocked, or null if supported.
 */
export function getJurisdictionBlockMessage(
  notice?: JurisdictionNotice | null,
  jurisdictionSupportedFlag?: boolean,
  requestedJurisdiction?: string
): string | null {
  if (isJurisdictionSupported(notice, jurisdictionSupportedFlag)) {
    return null;
  }

  const jurName =
    notice?.requested_jurisdiction || requestedJurisdiction || "the requested jurisdiction";

  if (notice?.message) {
    return notice.message;
  }

  const verified = notice?.supported_jurisdictions || notice?.verified_jurisdictions;
  const verifiedList = verified && verified.length > 0 ? ` (Supported: ${verified.join(", ")})` : "";

  return `Official government requirements for jurisdiction '${jurName}' are not currently verified in SEVA. Application creation and submission are disabled to prevent filing incorrect forms${verifiedList}.`;
}
