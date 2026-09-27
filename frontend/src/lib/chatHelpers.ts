export interface ChatMessage {
  id: string;
  sender: "user" | "assistant" | "system";
  text: string;
  timestamp: string;
  service_code?: string;
  application_id?: string;
  status?: string;
  required_documents?: string[];
  required_fields?: string[];
  missing_documents?: string[];
  verified_documents?: string[];
  clarification_options?: string[];
  jurisdiction?: string;
  jurisdiction_notice?: {
    message?: string;
    requested_jurisdiction?: string;
    supported_jurisdictions?: string[];
  };
  responsible_officer?: string;
  isError?: boolean;
}

export function mapChatHistoryItem(item: any): ChatMessage {
  const timestamp = item.created_at
    ? new Date(item.created_at).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      })
    : "";

  if (item.role === "user") {
    return {
      id: `user-${item.id}`,
      sender: "user",
      text: item.original_message || item.text || "",
      timestamp,
      application_id: item.application_id,
      service_code: item.service_code,
    };
  }

  return {
    id: `assistant-${item.id}`,
    sender: "assistant",
    text: item.reply || item.original_message || item.text || "I processed your request.",
    timestamp,
    service_code: item.service_code,
    application_id: item.application_id,
    status: item.status,
    required_documents: item.required_documents || [],
    required_fields: item.required_fields || [],
    missing_documents: item.missing_documents || [],
    verified_documents: item.verified_documents || [],
    clarification_options: item.clarification_options || [],
    jurisdiction: item.jurisdiction,
    jurisdiction_notice: item.jurisdiction_notice,
    responsible_officer: item.responsible_officer,
  };
}

export function mapChatHistory(history: any[]): ChatMessage[] {
  if (!Array.isArray(history)) return [];
  return history
    .filter((item) => item && (item.role === "user" || item.role === "assistant"))
    .map(mapChatHistoryItem);
}

export function detectServiceInText(text: string): string | null {
  const lower = (text || "").toLowerCase().trim();
  if (
    lower.includes("driving licence") ||
    lower.includes("driving license") ||
    lower.includes("driver licence") ||
    lower.includes("driver license") ||
    lower.includes("learner licence") ||
    lower.includes("learning licence") ||
    /\b(driving|licence|license|dl)\b/i.test(lower)
  ) {
    return "driving_license";
  }
  if (
    lower.includes("birth certificate") ||
    lower.includes("birth cert") ||
    lower.includes("newborn") ||
    lower.includes("new born") ||
    lower.includes("baby birth") ||
    lower.includes("child birth") ||
    lower.includes("janma praman") ||
    (/\bbirth\b/i.test(lower) && /\b(child|baby|certificate|register|registration)\b/i.test(lower))
  ) {
    return "birth_certificate";
  }
  if (
    lower.includes("income certificate") ||
    lower.includes("income cert") ||
    lower.includes("salary certificate") ||
    lower.includes("earnings certificate") ||
    lower.includes("revenue certificate") ||
    /\b(income|scholarship)\b/i.test(lower)
  ) {
    return "income_certificate";
  }
  return null;
}

export function resolveChatPayload(
  userId: string,
  message: string,
  currentAppId: string | null,
  currentServiceCode: string | null
): {
  payload: { citizen_id: string; message: string; application_id?: string };
  nextAppId: string | null;
  detectedService: string | null;
} {
  const detectedService = detectServiceInText(message);
  const isUnrelatedService =
    Boolean(detectedService) &&
    Boolean(currentServiceCode) &&
    detectedService !== currentServiceCode;

  const effectiveAppId = isUnrelatedService ? null : currentAppId;
  const payload: { citizen_id: string; message: string; application_id?: string } = {
    citizen_id: userId,
    message,
  };
  if (effectiveAppId) {
    payload.application_id = effectiveAppId;
  }
  return {
    payload,
    nextAppId: effectiveAppId,
    detectedService,
  };
}
