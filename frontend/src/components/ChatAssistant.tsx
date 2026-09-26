"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import { fetchApi } from "@/lib/api";
import { useEventContext } from "@/contexts/EventContext";
import DocumentUploader from "./DocumentUploader";
import ApplicationPreview from "./ApplicationPreview";
import {
  Send,
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  Circle,
  Loader2,
  AlertTriangle,
  FileCheck2,
  AlertCircle,
  Building2,
  RotateCcw,
  MapPin,
  HelpCircle,
  FileWarning,
} from "lucide-react";
import toast from "react-hot-toast";
import { humanizeKey } from "@/lib/statusMapping";

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

export interface UploadedDoc {
  id: string;
  title: string;
  document_type: string;
  verification_status: string;
  extracted_data?: Record<string, any>;
  created_at: string;
}

export default function ChatAssistant({
  onApplicationCreated,
  initialApplicationId,
}: {
  onApplicationCreated?: () => void;
  initialApplicationId?: string;
}) {
  const { user } = useAuth();
  const { agentActivity } = useEventContext();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [uploadedDocs, setUploadedDocs] = useState<UploadedDoc[]>([]);
  const [currentAppId, setCurrentAppId] = useState<string | null>(initialApplicationId || null);
  const [showConsentPreview, setShowConsentPreview] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const currentUserIdRef = useRef<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, agentActivity, uploadedDocs, uploading]);

  // Reset state whenever user identity changes to prevent cross-citizen data leaks
  useEffect(() => {
    if (!user) {
      setMessages([]);
      setCurrentAppId(null);
      setHistoryLoaded(false);
      currentUserIdRef.current = null;
      return;
    }

    if (currentUserIdRef.current !== user.id) {
      currentUserIdRef.current = user.id;
      setMessages([]);
      setCurrentAppId(initialApplicationId || null);
      setHistoryLoaded(false);
    }
  }, [user, initialApplicationId]);

  // Load chat history from backend if available to preserve conversational context
  useEffect(() => {
    if (!user || historyLoaded) return;

    fetchApi("/api/chat/history")
      .then((history) => {
        if (Array.isArray(history) && history.length > 0) {
          const mapped: ChatMessage[] = history.flatMap((item: any) => {
            const userPart: ChatMessage = {
              id: `user-${item.id}`,
              sender: "user",
              text: item.original_message,
              timestamp: new Date(item.created_at).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              }),
            };

            const assistantPart: ChatMessage = {
              id: `assistant-${item.id}`,
              sender: "assistant",
              text: item.reply || "I processed your request.",
              timestamp: new Date(item.created_at).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              }),
              service_code: item.service_code,
              application_id: item.application_id,
            };

            return [userPart, assistantPart];
          });

          setMessages(mapped);
          if (history[history.length - 1]?.application_id) {
            setCurrentAppId(history[history.length - 1].application_id);
          }
        } else {
          // Default Welcome Message
          setMessages([
            {
              id: "welcome-1",
              sender: "assistant",
              text: `Namaste, ${
                user?.full_name?.split(" ")[0] || "Citizen"
              }.\n\nI am SEVA, your official digital government assistant.\n\nTell me what service or certificate you need (for example: "I need an Income Certificate" or "Birth certificate for scholarship"), and I will guide you through the requirements.`,
              timestamp: new Date().toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              }),
            },
          ]);
        }
      })
      .catch(() => {
        // Fallback welcome message
        setMessages([
          {
            id: "welcome-fallback",
            sender: "assistant",
            text: `Namaste, ${
              user?.full_name?.split(" ")[0] || "Citizen"
            }.\n\nI am SEVA, your government services assistant. How may I help you today?`,
            timestamp: new Date().toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            }),
          },
        ]);
      })
      .finally(() => setHistoryLoaded(true));
  }, [user, historyLoaded]);

  // Sync uploaded documents
  useEffect(() => {
    if (user) {
      fetchApi("/api/documents/")
        .then((data) => setUploadedDocs(Array.isArray(data) ? data : []))
        .catch(() => {});
    }
  }, [user]);

  // Check if last message needs consent preview
  useEffect(() => {
    if (messages.length > 0) {
      const lastMsg = messages[messages.length - 1];
      if (lastMsg.status === "CONSENT_REQUIRED") {
        setShowConsentPreview(true);
      } else {
        setShowConsentPreview(false);
      }
    }
  }, [messages]);

  const handleSend = async (textToSend: string = input) => {
    const trimmed = textToSend.trim();
    if (!trimmed || !user || loading || uploading) return;

    if (textToSend === input) setInput("");
    setError(null);

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: "user",
      text: trimmed,
      timestamp: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const data = await fetchApi("/api/chat", {
        method: "POST",
        body: JSON.stringify({
          citizen_id: user.id,
          message: trimmed,
        }),
      });

      if (data.application_id) {
        setCurrentAppId(data.application_id);
      }

      const aiMsg: ChatMessage = {
        id: `ai-${Date.now()}`,
        sender: "assistant",
        text: data.reply,
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
        service_code: data.service_code,
        application_id: data.application_id,
        status: data.status,
        required_documents: data.required_documents || [],
        required_fields: data.required_fields || [],
        missing_documents: data.missing_documents || [],
        verified_documents: data.verified_documents || [],
        clarification_options: data.clarification_options || [],
        jurisdiction: data.jurisdiction,
        jurisdiction_notice: data.jurisdiction_notice,
        responsible_officer: data.responsible_officer,
      };

      setMessages((prev) => [...prev, aiMsg]);

      if (data.application_id && onApplicationCreated) {
        onApplicationCreated();
      }
    } catch (err: any) {
      const errorMsg = err.message || "Failed to process request. Please try again.";
      setError(errorMsg);
      toast.error(errorMsg);

      const errorChatMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        sender: "assistant",
        text: "I could not connect to SEVA services. Please try sending your message again.",
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
        isError: true,
      };
      setMessages((prev) => [...prev, errorChatMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (file: File, type: string) => {
    if (!user) return;
    setUploading(true);
    setError(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("document_type", type);
    formData.append("citizen_id", user.id);
    if (currentAppId) {
      formData.append("application_id", currentAppId);
    }

    try {
      const token = localStorage.getItem("seva_token");
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/documents/upload`,
        {
          method: "POST",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: formData,
        }
      );

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: "Upload failed" }));
        throw new Error(errData.detail || "Upload failed");
      }

      const uploadedDoc: UploadedDoc = await res.json();
      setUploadedDocs((prev) => [uploadedDoc, ...prev]);

      toast.success("Document uploaded and recorded successfully.");

      const sysMsg: ChatMessage = {
        id: `sys-${Date.now()}`,
        sender: "system",
        text: `📄 Uploaded: ${file.name} for ${humanizeKey(type)}`,
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      };
      setMessages((prev) => [...prev, sysMsg]);

      // Inform assistant to re-evaluate application state
      if (onApplicationCreated) onApplicationCreated();
      await handleSend(`I uploaded my ${humanizeKey(type)}. Please update my application.`);
    } catch (err: any) {
      setError(err.message || "Document upload failed.");
      toast.error(err.message || "Upload failed");
      throw err;
    } finally {
      setUploading(false);
    }
  };

  if (showConsentPreview && currentAppId) {
    return (
      <div className="bg-white rounded-3xl shadow-sm border border-slate-200 flex flex-col h-[720px] overflow-hidden">
        <ApplicationPreview
          applicationId={currentAppId}
          onEdit={() => {
            setShowConsentPreview(false);
            handleSend("I need to review or change details before submitting.");
          }}
          onSubmitSuccess={(status, ref) => {
            setShowConsentPreview(false);
            const aiMsg: ChatMessage = {
              id: `ai-${Date.now()}`,
              sender: "assistant",
              text: `Your application has been officially submitted!\n\nGovernment Reference Number: **${ref}**\n\nYou can track processing milestones in the tracking view.`,
              timestamp: new Date().toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              }),
              status: status,
            };
            setMessages((prev) => [...prev, aiMsg]);
            toast.success("Application Submitted Successfully");
            if (onApplicationCreated) onApplicationCreated();
          }}
        />
      </div>
    );
  }

  const hasUserMessages = messages.some((m) => m.sender === "user");

  return (
    <div className="bg-white rounded-3xl shadow-sm border border-slate-200 flex flex-col h-[720px] overflow-hidden">
      
      {/* Header */}
      <div className="px-6 py-4 flex items-center justify-between border-b border-slate-100 bg-white">
        <div className="flex items-center space-x-3">
          <div className="h-9 w-9 rounded-xl bg-indigo-50 flex items-center justify-center text-indigo-600 border border-indigo-100">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <h3 className="font-bold text-sm text-slate-900 tracking-tight">SEVA Citizen Assistant</h3>
            <p className="text-[11px] text-slate-500 font-medium">Conversational Government AI Guide</p>
          </div>
        </div>

        {currentAppId && (
          <span className="text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-md bg-indigo-50 text-indigo-700 border border-indigo-200">
            Active Application Linked
          </span>
        )}
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto bg-slate-50/50 p-6 space-y-5">
        {messages.map((msg) => {
          if (msg.sender === "system") {
            return (
              <div key={msg.id} className="flex justify-center my-2">
                <span className="text-xs bg-slate-100 text-slate-600 px-3 py-1 rounded-full border border-slate-200 font-medium">
                  {msg.text}
                </span>
              </div>
            );
          }

          const isUser = msg.sender === "user";

          return (
            <div
              key={msg.id}
              className={`flex items-end space-x-2.5 ${
                isUser ? "justify-end" : "justify-start"
              }`}
            >
              {!isUser && (
                <div className="h-7 w-7 rounded-full bg-indigo-100 border border-indigo-200 flex items-center justify-center shrink-0 mb-1 text-indigo-700">
                  <Sparkles className="h-3.5 w-3.5" />
                </div>
              )}

              <div
                className={`max-w-[85%] sm:max-w-[80%] flex flex-col space-y-2 ${
                  isUser ? "items-end" : "items-start"
                }`}
              >
                {/* Bubble */}
                <div
                  className={`px-4 py-3 rounded-2xl text-[13px] leading-relaxed shadow-2xs ${
                    isUser
                      ? "bg-slate-900 text-white rounded-br-xs"
                      : msg.isError
                      ? "bg-rose-50 text-rose-900 border border-rose-200 rounded-bl-xs"
                      : "bg-white text-slate-800 border border-slate-200 rounded-bl-xs"
                  }`}
                >
                  <div className="whitespace-pre-line">{msg.text}</div>
                </div>

                {/* Structured Notice / Metadata attached to AI message */}
                {!isUser && (
                  <div className="w-full space-y-3">
                    
                    {/* Unsupported Jurisdiction Notice */}
                    {msg.jurisdiction_notice && (
                      <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-xl space-y-1.5 text-xs text-amber-900">
                        <div className="flex items-center space-x-1.5 font-bold text-amber-800">
                          <MapPin className="h-4 w-4 text-amber-600 shrink-0" />
                          <span>Jurisdiction Notice</span>
                        </div>
                        <p className="leading-relaxed">
                          {msg.jurisdiction_notice.message ||
                            `The requested jurisdiction "${msg.jurisdiction_notice.requested_jurisdiction}" is not currently supported for online processing.`}
                        </p>
                        {msg.jurisdiction_notice.supported_jurisdictions && (
                          <div className="pt-1 text-[11px] text-amber-700 font-medium">
                            Supported: {msg.jurisdiction_notice.supported_jurisdictions.map(humanizeKey).join(", ")}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Clarification Options (clickable pills) */}
                    {msg.clarification_options && msg.clarification_options.length > 0 && (
                      <div className="p-3 bg-white border border-slate-200 rounded-xl space-y-2">
                        <span className="text-[11px] font-bold text-slate-700 uppercase tracking-wider flex items-center space-x-1">
                          <HelpCircle className="h-3.5 w-3.5 text-indigo-500" />
                          <span>Clarification Options (Click to select):</span>
                        </span>
                        <div className="flex flex-wrap gap-2">
                          {msg.clarification_options.map((option, idx) => (
                            <button
                              key={idx}
                              onClick={() => handleSend(option)}
                              className="px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 text-indigo-800 rounded-lg text-xs font-semibold transition text-left"
                            >
                              {option}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Service & Requirements Card */}
                    {msg.service_code && (
                      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs space-y-3">
                        <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                          <div className="flex items-center space-x-1.5">
                            <ShieldCheck className="h-4 w-4 text-indigo-600" />
                            <span className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                              {humanizeKey(msg.service_code)}
                            </span>
                          </div>
                          {msg.jurisdiction && (
                            <span className="text-[10px] font-semibold text-slate-500 bg-slate-100 px-2 py-0.5 rounded-md">
                              Jurisdiction: {humanizeKey(msg.jurisdiction)}
                            </span>
                          )}
                        </div>

                        {/* Missing Documents vs Verified Documents */}
                        {msg.required_documents && msg.required_documents.length > 0 && (
                          <div className="space-y-1.5">
                            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                              Required Documents Checklist
                            </span>
                            <div className="space-y-1.5">
                              {msg.required_documents.map((doc, idx) => {
                                const isVerified = msg.verified_documents?.includes(doc);
                                const isMissing = msg.missing_documents?.includes(doc);

                                return (
                                  <div
                                    key={idx}
                                    className="flex items-center justify-between text-xs p-1.5 rounded-lg bg-slate-50"
                                  >
                                    <div className="flex items-center space-x-2">
                                      {isVerified ? (
                                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                                      ) : isMissing ? (
                                        <Circle className="h-3.5 w-3.5 text-amber-500" />
                                      ) : (
                                        <Circle className="h-3.5 w-3.5 text-slate-300" />
                                      )}
                                      <span
                                        className={
                                          isVerified
                                            ? "text-slate-800 font-medium"
                                            : "text-slate-900 font-semibold"
                                        }
                                      >
                                        {humanizeKey(doc)}
                                      </span>
                                    </div>
                                    <span
                                      className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded-sm ${
                                        isVerified
                                          ? "bg-emerald-100 text-emerald-800"
                                          : isMissing
                                          ? "bg-amber-100 text-amber-800"
                                          : "bg-slate-200 text-slate-700"
                                      }`}
                                    >
                                      {isVerified ? "Verified" : isMissing ? "Missing" : "Required"}
                                    </span>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}

                        {/* Inline Document Uploader when collecting documents */}
                        {(msg.status === "COLLECTING_DOCUMENTS" ||
                          msg.status === "MISSING_INFORMATION") &&
                          !uploading && (
                            <div className="pt-2 border-t border-slate-100">
                              <DocumentUploader
                                onUpload={handleFileUpload}
                                uploading={uploading}
                                defaultType={msg.missing_documents?.[0] || "identity_proof"}
                              />
                            </div>
                          )}
                      </div>
                    )}

                  </div>
                )}
              </div>
            </div>
          );
        })}

        {/* Quick starter suggestions */}
        {!hasUserMessages && (
          <div className="pt-3 flex flex-col space-y-2 pl-9">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              Suggested Requests
            </span>
            <button
              onClick={() => handleSend("I want to apply for an Income Certificate")}
              className="text-left px-3.5 py-2 bg-white border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50/50 rounded-xl text-xs font-semibold text-slate-700 transition w-fit"
            >
              Apply for an Income Certificate
            </button>
            <button
              onClick={() => handleSend("How can I prove my family income for a scholarship?")}
              className="text-left px-3.5 py-2 bg-white border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50/50 rounded-xl text-xs font-semibold text-slate-700 transition w-fit"
            >
              How can I prove my family income for scholarship?
            </button>
            <button
              onClick={() => handleSend("I need a Birth Certificate")}
              className="text-left px-3.5 py-2 bg-white border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50/50 rounded-xl text-xs font-semibold text-slate-700 transition w-fit"
            >
              Apply for a Birth Certificate
            </button>
          </div>
        )}

        {/* Real-time agent status or loading */}
        {(loading || uploading || agentActivity) && (
          <div className="flex justify-start pl-2">
            <div className="flex items-center space-x-2 bg-white border border-slate-200 px-3.5 py-2 rounded-xl shadow-xs">
              <Loader2 className="h-3.5 w-3.5 text-indigo-600 animate-spin shrink-0" />
              <span className="text-xs font-medium text-slate-600 animate-pulse">
                {agentActivity || (uploading ? "Uploading document to vault..." : "SEVA is analyzing...")}
              </span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input box */}
      <div className="p-4 bg-white border-t border-slate-100">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex items-center space-x-2 bg-slate-50 border border-slate-200 rounded-2xl px-2.5 py-1.5 focus-within:ring-2 focus-within:ring-indigo-500 focus-within:border-transparent transition"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Tell SEVA what you need (e.g. 'need income cert', 'driving licence')..."
            className="flex-1 bg-transparent text-xs sm:text-sm px-3 py-2 focus:outline-none text-slate-900 placeholder:text-slate-400"
            disabled={loading || uploading}
          />
          <button
            type="submit"
            disabled={loading || uploading || !input.trim()}
            className="h-9 w-9 bg-slate-900 hover:bg-slate-800 disabled:bg-slate-300 text-white rounded-xl flex items-center justify-center transition shrink-0"
            title="Send Message"
          >
            <Send className="h-4 w-4 ml-0.5" />
          </button>
        </form>
      </div>
    </div>
  );
}
