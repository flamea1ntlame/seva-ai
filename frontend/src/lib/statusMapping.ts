/**
 * Centralized Citizen Experience Status and Verification Mapping for SEVA AI.
 * 
 * Maps canonical backend database states to human-readable citizen labels,
 * actionable descriptions, visual indicators, and clear guidance.
 * 
 * FRONTEND RULE: Never invent backend states; map canonical states cleanly.
 * Never claim a document is genuine solely because an AI model processed it.
 */

export interface ApplicationStatusInfo {
  stageNumber: number; // 1 to 9
  label: string;
  description: string;
  badgeClass: string;
  dotColor: string;
  actionRequired: boolean;
  actionLabel?: string;
  actionPrompt?: string;
}

export interface DocumentStatusInfo {
  label: string;
  symbol: string;
  badgeClass: string;
  citizenExplanation: string;
  isVerified: boolean;
  needsAttention: boolean;
}

/**
 * 9 Standard Citizen-Facing Application Stages
 */
export const CITIZEN_STAGES = [
  { step: 1, name: "Started", description: "Application initiated" },
  { step: 2, name: "Documents Required", description: "Awaiting mandatory documents" },
  { step: 3, name: "Documents Uploaded", description: "Documents uploaded, data extraction in progress" },
  { step: 4, name: "Verification", description: "Validating against authoritative rules" },
  { step: 5, name: "Review Required", description: "Citizen action needed for missing items or warnings" },
  { step: 6, name: "Ready for Submission", description: "Consent and final citizen review" },
  { step: 7, name: "Submitted", description: "Successfully submitted to department" },
  { step: 8, name: "Under Processing", description: "Department officer review in progress" },
  { step: 9, name: "Completed", description: "Official certificate / outcome issued" },
] as const;

/**
 * Map canonical backend application states to citizen-facing status info
 */
export function getApplicationStatusInfo(
  status?: string,
  government_status?: string
): ApplicationStatusInfo {
  const normStatus = (status || "").toUpperCase();
  const normGov = (government_status || "").toUpperCase();

  // Government outcomes override internal state once submitted
  if (normGov === "APPROVED") {
    return {
      stageNumber: 9,
      label: "Completed",
      description: "Application approved by the issuing authority.",
      badgeClass: "bg-emerald-50 text-emerald-800 border-emerald-200",
      dotColor: "bg-emerald-500",
      actionRequired: false,
    };
  }

  if (normGov === "REJECTED") {
    return {
      stageNumber: 8,
      label: "Rejected by Authority",
      description: "Department officer reviewed and rejected the application.",
      badgeClass: "bg-rose-50 text-rose-800 border-rose-200",
      dotColor: "bg-rose-500",
      actionRequired: false,
    };
  }

  if (normGov === "UNDER_REVIEW") {
    return {
      stageNumber: 8,
      label: "Under Processing",
      description: "Under review by the competent departmental officer.",
      badgeClass: "bg-indigo-50 text-indigo-800 border-indigo-200",
      dotColor: "bg-indigo-500",
      actionRequired: false,
    };
  }

  switch (normStatus) {
    case "DISCOVER":
    case "STARTED":
      return {
        stageNumber: 1,
        label: "Started",
        description: "Application started. Identify required documents.",
        badgeClass: "bg-slate-50 text-slate-700 border-slate-200",
        dotColor: "bg-slate-400",
        actionRequired: true,
        actionLabel: "Provide Documents",
        actionPrompt: "Please provide the required documents to proceed.",
      };

    case "COLLECTING_DOCUMENTS":
      return {
        stageNumber: 2,
        label: "Documents Required",
        description: "Mandatory documents must be provided before submission.",
        badgeClass: "bg-amber-50 text-amber-800 border-amber-200",
        dotColor: "bg-amber-500",
        actionRequired: true,
        actionLabel: "Upload Documents",
        actionPrompt: "Required documents are missing. Please upload them.",
      };

    case "EXTRACTING":
      return {
        stageNumber: 3,
        label: "Documents Uploaded",
        description: "Your documents are uploaded. System is reading details.",
        badgeClass: "bg-sky-50 text-sky-800 border-sky-200",
        dotColor: "bg-sky-500",
        actionRequired: false,
      };

    case "VALIDATING":
      return {
        stageNumber: 4,
        label: "Verification in Progress",
        description: "Verifying document eligibility against official rules.",
        badgeClass: "bg-blue-50 text-blue-800 border-blue-200",
        dotColor: "bg-blue-500",
        actionRequired: false,
      };

    case "MISSING_INFORMATION":
    case "ACTION_REQUIRED":
      return {
        stageNumber: 5,
        label: "Review Required",
        description: "Missing documents or details require your attention.",
        badgeClass: "bg-orange-50 text-orange-800 border-orange-200",
        dotColor: "bg-orange-500",
        actionRequired: true,
        actionLabel: "Fix Issues",
        actionPrompt: "Some required documents or fields are missing.",
      };

    case "READY_FOR_REVIEW":
      return {
        stageNumber: 6,
        label: "Ready for Review",
        description: "All requirements met. Ready for final citizen review.",
        badgeClass: "bg-teal-50 text-teal-800 border-teal-200",
        dotColor: "bg-teal-500",
        actionRequired: true,
        actionLabel: "Review Application",
        actionPrompt: "Review your information before submitting.",
      };

    case "CONSENT_REQUIRED":
      return {
        stageNumber: 6,
        label: "Consent Required",
        description: "Data sharing authorization needed before submission.",
        badgeClass: "bg-purple-50 text-purple-800 border-purple-200",
        dotColor: "bg-purple-500",
        actionRequired: true,
        actionLabel: "Give Consent",
        actionPrompt: "Please authorize data sharing with the department.",
      };

    case "SUBMITTING":
      return {
        stageNumber: 7,
        label: "Submitting",
        description: "Transmitting application to government portal...",
        badgeClass: "bg-indigo-50 text-indigo-800 border-indigo-200",
        dotColor: "bg-indigo-500",
        actionRequired: false,
      };

    case "SUBMITTED":
      return {
        stageNumber: 7,
        label: "Submitted",
        description: "Application successfully submitted. Awaiting officer action.",
        badgeClass: "bg-blue-50 text-blue-800 border-blue-200",
        dotColor: "bg-blue-500",
        actionRequired: false,
      };

    case "TRACKING":
      return {
        stageNumber: 8,
        label: "Under Processing",
        description: "Application is being processed by the department.",
        badgeClass: "bg-indigo-50 text-indigo-800 border-indigo-200",
        dotColor: "bg-indigo-500",
        actionRequired: false,
      };

    case "COMPLETED":
      return {
        stageNumber: 9,
        label: "Completed",
        description: "Application process is complete.",
        badgeClass: "bg-emerald-50 text-emerald-800 border-emerald-200",
        dotColor: "bg-emerald-500",
        actionRequired: false,
      };

    case "REJECTED":
      return {
        stageNumber: 8,
        label: "Rejected",
        description: "Application was rejected.",
        badgeClass: "bg-rose-50 text-rose-800 border-rose-200",
        dotColor: "bg-rose-500",
        actionRequired: false,
      };

    default:
      return {
        stageNumber: 1,
        label: (status || "Unknown").replace(/_/g, " "),
        description: "Application in progress.",
        badgeClass: "bg-slate-50 text-slate-700 border-slate-200",
        dotColor: "bg-slate-400",
        actionRequired: false,
      };
  }
}

/**
 * Map document verification states to citizen-safe visual info
 * 
 * Allowed states:
 * ✅ Verified
 * ⏳ Verification in progress
 * ⚠️ Needs review
 * ❌ Rejected
 * ℹ️ Not verifiable
 */
export function getDocumentStatusInfo(
  verification_status?: string,
  verified?: boolean
): DocumentStatusInfo {
  const norm = (verification_status || "").toUpperCase();

  if (verified || norm === "VERIFIED") {
    return {
      label: "Verified",
      symbol: "✅",
      badgeClass: "bg-emerald-50 text-emerald-700 border-emerald-200",
      citizenExplanation: "Document verified against authoritative requirements.",
      isVerified: true,
      needsAttention: false,
    };
  }

  if (norm === "OCR_EXTRACTED") {
    return {
      label: "Verification in Progress",
      symbol: "⏳",
      badgeClass: "bg-blue-50 text-blue-700 border-blue-200",
      citizenExplanation: "Document data has been digitally extracted. Verification in progress.",
      isVerified: false,
      needsAttention: false,
    };
  }

  if (norm === "REJECTED" || norm === "SUSPICIOUS") {
    return {
      label: "Rejected",
      symbol: "❌",
      badgeClass: "bg-rose-50 text-rose-700 border-rose-200",
      citizenExplanation: "Document does not satisfy requirements. Please re-upload.",
      isVerified: false,
      needsAttention: true,
    };
  }

  if (norm === "NEEDS_REVIEW" || norm === "FLAGGED") {
    return {
      label: "Needs Review",
      symbol: "⚠️",
      badgeClass: "bg-amber-50 text-amber-800 border-amber-200",
      citizenExplanation: "Requires review. Ensure all text and stamps are legible.",
      isVerified: false,
      needsAttention: true,
    };
  }

  if (norm === "NOT_VERIFIABLE" || norm === "UNVERIFIED") {
    return {
      label: "Not Verifiable",
      symbol: "ℹ️",
      badgeClass: "bg-slate-100 text-slate-700 border-slate-200",
      citizenExplanation: "Could not be digitally validated. Manual verification may be required.",
      isVerified: false,
      needsAttention: false,
    };
  }

  // Default: PENDING / EXTRACTING / PROCESSING
  return {
    label: "Verification in Progress",
    symbol: "⏳",
    badgeClass: "bg-blue-50 text-blue-700 border-blue-200",
    citizenExplanation: "Awaiting automated or departmental verification.",
    isVerified: false,
    needsAttention: false,
  };
}

/**
 * Humanize technical field / document type keys
 * e.g. "identity_proof" -> "Identity Proof"
 */
export function humanizeKey(key: string): string {
  if (!key) return "";
  return key
    .replace(/[_-]/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
