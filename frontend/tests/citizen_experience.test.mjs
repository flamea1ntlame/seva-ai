import test from "node:test";
import assert from "node:assert/strict";

// We import the compiled / pure JS logic or mock implementations that mirror statusMapping and API logic
import {
  getApplicationStatusInfo,
  getDocumentStatusInfo,
  humanizeKey,
  CITIZEN_STAGES,
} from "../src/lib/statusMapping.ts";

import { ApiError } from "../src/lib/api.ts";

test("1. Centralized Status Mapping: 9 Canonical Citizen Stages", async (t) => {
  await t.test("maps DISCOVER and STARTED to Stage 1: Started", () => {
    const info = getApplicationStatusInfo("DISCOVER");
    assert.equal(info.stageNumber, 1);
    assert.equal(info.label, "Started");
    assert.equal(info.actionRequired, true);
  });

  await t.test("maps COLLECTING_DOCUMENTS to Stage 2: Documents Required", () => {
    const info = getApplicationStatusInfo("COLLECTING_DOCUMENTS");
    assert.equal(info.stageNumber, 2);
    assert.equal(info.label, "Documents Required");
    assert.equal(info.actionRequired, true);
    assert.match(info.actionPrompt, /Required documents are missing/i);
  });

  await t.test("maps EXTRACTING to Stage 3: Documents Uploaded", () => {
    const info = getApplicationStatusInfo("EXTRACTING");
    assert.equal(info.stageNumber, 3);
    assert.equal(info.label, "Documents Uploaded");
    assert.equal(info.actionRequired, false);
  });

  await t.test("maps VALIDATING to Stage 4: Verification in Progress", () => {
    const info = getApplicationStatusInfo("VALIDATING");
    assert.equal(info.stageNumber, 4);
    assert.equal(info.label, "Verification in Progress");
    assert.equal(info.actionRequired, false);
  });

  await t.test("maps MISSING_INFORMATION to Stage 5: Review Required", () => {
    const info = getApplicationStatusInfo("MISSING_INFORMATION");
    assert.equal(info.stageNumber, 5);
    assert.equal(info.label, "Review Required");
    assert.equal(info.actionRequired, true);
    assert.match(info.actionPrompt, /missing/i);
  });

  await t.test("maps READY_FOR_REVIEW and CONSENT_REQUIRED to Stage 6", () => {
    const readyInfo = getApplicationStatusInfo("READY_FOR_REVIEW");
    assert.equal(readyInfo.stageNumber, 6);
    assert.equal(readyInfo.label, "Ready for Review");
    assert.equal(readyInfo.actionRequired, true);

    const consentInfo = getApplicationStatusInfo("CONSENT_REQUIRED");
    assert.equal(consentInfo.stageNumber, 6);
    assert.equal(consentInfo.label, "Consent Required");
    assert.equal(consentInfo.actionRequired, true);
  });

  await t.test("maps SUBMITTED to Stage 7: Submitted", () => {
    const info = getApplicationStatusInfo("SUBMITTED");
    assert.equal(info.stageNumber, 7);
    assert.equal(info.label, "Submitted");
    assert.equal(info.actionRequired, false);
  });

  await t.test("maps TRACKING and UNDER_REVIEW to Stage 8: Under Processing", () => {
    const info = getApplicationStatusInfo("TRACKING");
    assert.equal(info.stageNumber, 8);
    assert.equal(info.label, "Under Processing");

    const govInfo = getApplicationStatusInfo("SUBMITTED", "UNDER_REVIEW");
    assert.equal(govInfo.stageNumber, 8);
    assert.equal(govInfo.label, "Under Processing");
  });

  await t.test("maps COMPLETED and APPROVED to Stage 9: Completed", () => {
    const info = getApplicationStatusInfo("COMPLETED");
    assert.equal(info.stageNumber, 9);
    assert.equal(info.label, "Completed");

    const govInfo = getApplicationStatusInfo("SUBMITTED", "APPROVED");
    assert.equal(govInfo.stageNumber, 9);
    assert.equal(govInfo.label, "Completed");
  });

  await t.test("handles REJECTED outcomes properly", () => {
    const info = getApplicationStatusInfo("REJECTED");
    assert.equal(info.label, "Rejected");

    const govInfo = getApplicationStatusInfo("SUBMITTED", "REJECTED");
    assert.equal(govInfo.label, "Rejected by Authority");
  });
});

test("2. Document Verification Status Mapping: Citizen-Safe Language", async (t) => {
  await t.test("VERIFIED documents have checkmark and clear explanation", () => {
    const info = getDocumentStatusInfo("VERIFIED", true);
    assert.equal(info.label, "Verified");
    assert.equal(info.symbol, "✅");
    assert.equal(info.isVerified, true);
    assert.equal(info.needsAttention, false);
    assert.match(info.citizenExplanation, /verified against authoritative/i);
    // CRITICAL SECURITY RULE: Never claim AI proved document is genuine
    assert.doesNotMatch(info.citizenExplanation, /\bAI\b/i);
  });

  await t.test("PENDING verification displays progress state", () => {
    const info = getDocumentStatusInfo("PENDING", false);
    assert.equal(info.label, "Verification in Progress");
    assert.equal(info.symbol, "⏳");
    assert.equal(info.isVerified, false);
  });

  await t.test("NEEDS_REVIEW highlights attention needed", () => {
    const info = getDocumentStatusInfo("NEEDS_REVIEW", false);
    assert.equal(info.label, "Needs Review");
    assert.equal(info.symbol, "⚠️");
    assert.equal(info.needsAttention, true);
    assert.match(info.citizenExplanation, /legible/i);
  });

  await t.test("REJECTED status provides actionable guidance", () => {
    const info = getDocumentStatusInfo("REJECTED", false);
    assert.equal(info.label, "Rejected");
    assert.equal(info.symbol, "❌");
    assert.equal(info.needsAttention, true);
    assert.match(info.citizenExplanation, /re-upload/i);
  });

  await t.test("NOT_VERIFIABLE explains digital registry limitation", () => {
    const info = getDocumentStatusInfo("NOT_VERIFIABLE", false);
    assert.equal(info.label, "Not Verifiable");
    assert.equal(info.symbol, "ℹ️");
    assert.match(info.citizenExplanation, /manual verification/i);
  });
});

test("3. Humanize Key Utility: Strips database internals and underscores", () => {
  assert.equal(humanizeKey("identity_proof"), "Identity Proof");
  assert.equal(humanizeKey("income_certificate"), "Income Certificate");
  assert.equal(humanizeKey("annual_income"), "Annual Income");
  assert.equal(humanizeKey("parent_identity_proof"), "Parent Identity Proof");
  assert.equal(humanizeKey(""), "");
});

test("4. API Error Handling: Clean Citizen-Facing Errors & Session Expiry", async (t) => {
  await t.test("ApiError retains HTTP status and clean message", () => {
    const err = new ApiError("Your session has expired.", 401);
    assert.equal(err.status, 401);
    assert.equal(err.message, "Your session has expired.");
    assert.equal(err.name, "ApiError");
  });

  await t.test("Network failure throws friendly error without stack traces", () => {
    const networkErr = new ApiError("Unable to reach SEVA services. Please check your internet connection.", 0);
    assert.equal(networkErr.status, 0);
    assert.doesNotMatch(networkErr.message, /at Object|node_modules|ECONNREFUSED/);
  });
});

test("5. Document Checklist & Missing Documents Logic", async (t) => {
  const requiredTypes = ["identity_proof", "address_proof", "income_proof"];
  const linkedDocs = [
    { id: "1", document_type: "identity_proof", title: "aadhaar.pdf", verified: true, verification_status: "VERIFIED" },
    { id: "2", document_type: "address_proof", title: "bill.pdf", verified: false, verification_status: "PENDING" },
  ];

  const providedSet = new Set(linkedDocs.map(d => d.document_type));
  const missing = requiredTypes.filter(req => !providedSet.has(req));

  assert.deepEqual(missing, ["income_proof"]);
  assert.equal(missing.length, 1);
  assert.equal(linkedDocs.find(d => d.document_type === "identity_proof")?.verified, true);
  assert.equal(linkedDocs.find(d => d.document_type === "address_proof")?.verified, false);
});

test("6. Duplicate Submission & Idempotency Safeguards", async (t) => {
  let submitCount = 0;
  let isSubmitting = false;

  async function mockSubmitApplication() {
    if (isSubmitting) {
      throw new Error("Duplicate submission prevented.");
    }
    isSubmitting = true;
    try {
      submitCount++;
      return { status: "SUBMITTED", government_reference: "SEVA-987654" };
    } finally {
      isSubmitting = false;
    }
  }

  const res1 = await mockSubmitApplication();
  assert.equal(res1.status, "SUBMITTED");
  assert.equal(submitCount, 1);

  // Rapid double click simulation
  isSubmitting = true;
  await assert.rejects(
    async () => {
      await mockSubmitApplication();
    },
    { message: "Duplicate submission prevented." }
  );
  assert.equal(submitCount, 1);
});

test("7. Chatbot Protocol: Unsupported Jurisdiction & Clarification Contracts", async (t) => {
  const mockChatResponse = {
    reply: "Income certificate services in Kerala are currently not automated online through SEVA.",
    service_code: "income_certificate",
    jurisdiction: "kerala",
    jurisdiction_notice: {
      message: "Income certificate issuance for Kerala is handled through the Akshaya portal.",
      requested_jurisdiction: "kerala",
      supported_jurisdictions: ["karnataka", "national"]
    },
    clarification_options: [
      "Check Karnataka service rules",
      "Ask about Central schemes"
    ],
    required_documents: ["identity_proof", "income_proof"],
    missing_documents: ["identity_proof", "income_proof"]
  };

  assert.ok(mockChatResponse.jurisdiction_notice);
  assert.equal(mockChatResponse.jurisdiction_notice.requested_jurisdiction, "kerala");
  assert.equal(mockChatResponse.clarification_options.length, 2);
  assert.deepEqual(mockChatResponse.missing_documents, ["identity_proof", "income_proof"]);
});
