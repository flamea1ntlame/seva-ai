"use client";

import React, { useState, useRef, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import { fetchApi } from "@/lib/api";
import { useEventContext } from "@/contexts/EventContext";
import DocumentUploader from "./DocumentUploader";
import ApplicationPreview from "./ApplicationPreview";
import DocumentCard from "./DocumentCard";
import MarkdownRenderer from "./MarkdownRenderer";
import {
  Send,
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  Circle,
  Loader2,
  AlertTriangle,
  FileCheck2,
  Check,
  Bot
} from "lucide-react";
import toast from "react-hot-toast";

export interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  text: string;
  timestamp: string;
  service_code?: string;
  application_id?: string;
  status?: string;
  required_documents?: string[];
  required_fields?: string[];
}

export interface UploadedDoc {
  id: string;
  title: string;
  document_type: string;
  verification_status: string;
  extracted_data?: Record<string, any>;
  created_at: string;
}

export default function ChatAssistant({ onApplicationCreated }: { onApplicationCreated?: () => void }) {
  const { user } = useAuth();
  const { agentActivity } = useEventContext();
  
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [uploadedDocs, setUploadedDocs] = useState<UploadedDoc[]>([]);
  const [currentAppId, setCurrentAppId] = useState<string | null>(null);
  const [showConsentPreview, setShowConsentPreview] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, agentActivity, uploadedDocs, uploading]);

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

  useEffect(() => {
    if (user) {
      fetchApi("/api/documents/")
        .then((data) => setUploadedDocs(data))
        .catch((err) => console.error("Error fetching docs:", err));
    }
  }, [user]);

  const handleSend = async (text: string = input) => {
    if (!text.trim() || !user || loading || uploading) return;

    const userMsgText = text.trim();
    if (text === input) setInput("");
    setError(null);

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: "user",
      text: userMsgText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const data = await fetchApi("/api/chat", {
        method: "POST",
        body: JSON.stringify({
          citizen_id: user.id,
          message: userMsgText,
        }),
      });

      if (data.application_id) {
        setCurrentAppId(data.application_id);
      }

      const aiMsg: ChatMessage = {
        id: `ai-${Date.now()}`,
        sender: "assistant",
        text: data.reply,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        service_code: data.service_code,
        application_id: data.application_id,
        status: data.status,
        required_documents: data.required_documents || [],
        required_fields: data.required_fields || [],
      };

      setMessages((prev) => [...prev, aiMsg]);

      if (data.application_id && onApplicationCreated) {
        onApplicationCreated();
      }
    } catch (err: any) {
      setError(err.message || "Failed to process request.");
      toast.error("Failed to connect to SEVA.");
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
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/documents/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: "Upload failed" }));
        throw new Error(errData.detail || "Upload failed");
      }

      const uploadedDoc: UploadedDoc = await res.json();
      setUploadedDocs((prev) => [uploadedDoc, ...prev]);
      
      toast.success("Document verified successfully");

      const sysMsg: ChatMessage = {
        id: `sys-${Date.now()}`,
        sender: "user",
        text: `Uploaded: ${file.name} (${type.replace('_', ' ')})`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, sysMsg]);

      // Trigger re-evaluation
      if (onApplicationCreated) onApplicationCreated();
      await handleSend(`I uploaded my ${type.replace('_', ' ')}. Check my application status.`);
      
    } catch (err: any) {
      setError(err.message || "Document upload failed.");
      toast.error(err.message || "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  if (showConsentPreview && currentAppId) {
    return (
      <div className="bg-white rounded-2xl shadow-sm border border-brand-200 flex flex-col h-full overflow-hidden">
        <ApplicationPreview 
          applicationId={currentAppId} 
          onEdit={() => {
            setShowConsentPreview(false);
            handleSend("I need to edit my application before submitting.");
          }}
          onSubmitSuccess={(status, ref) => {
            setShowConsentPreview(false);
            const aiMsg: ChatMessage = {
              id: `ai-${Date.now()}`,
              sender: "assistant",
              text: `Your application has been successfully submitted.\n\nGovernment Reference: **${ref}**\n\nYou can track the progress in the dashboard.`,
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              status: status
            };
            setMessages(prev => [...prev, aiMsg]);
            toast.success("Application Submitted");
            if (onApplicationCreated) onApplicationCreated();
          }}
        />
      </div>
    );
  }

  const hasUserMessages = messages.some(m => m.sender === "user");

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-brand-200 flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 flex items-center justify-between border-b border-brand-100 bg-white">
        <div className="flex items-center space-x-3">
          <div className="h-10 w-10 rounded-xl bg-primary-50 flex items-center justify-center text-primary-600 border border-primary-100">
            <Bot className="h-5 w-5" />
          </div>
          <div>
            <h3 className="font-bold text-base text-brand-900 tracking-tight">SEVA Citizen Assistant</h3>
            <p className="text-xs text-brand-500 font-medium mt-0.5">Your guide to government services</p>
          </div>
        </div>
        {currentAppId && (
          <div className="hidden sm:flex items-center px-2.5 py-1 rounded-md bg-success-50 border border-success-200 text-[10px] font-bold text-success-700 tracking-wider">
            <div className="h-1.5 w-1.5 rounded-full bg-success-500 mr-1.5 animate-pulse"></div>
            ACTIVE APPLICATION LINKED
          </div>
        )}
      </div>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto bg-brand-50/50 p-4 sm:p-6 space-y-6">
        {messages.map((msg, i) => (
          <div key={msg.id} className={`flex items-end space-x-2.5 ${msg.sender === "user" ? "justify-end" : "justify-start"}`}>
            
            {msg.sender === "assistant" && (
              <div className="h-7 w-7 rounded-full bg-primary-100 border border-primary-200 flex items-center justify-center shrink-0 mb-1">
                <Bot className="h-3.5 w-3.5 text-primary-700" />
              </div>
            )}

            <div className={`max-w-[85%] flex flex-col space-y-2 ${msg.sender === "user" ? "items-end" : "items-start"}`}>
              <div 
                className={`px-4 py-3 rounded-2xl text-[13px] leading-relaxed shadow-sm ${
                  msg.sender === "user" 
                    ? "bg-brand-900 text-white rounded-br-sm" 
                    : "bg-white border border-brand-200 rounded-bl-sm"
                }`}
              >
                {msg.sender === "user" ? (
                  <div className="whitespace-pre-line">{msg.text}</div>
                ) : (
                  <MarkdownRenderer content={msg.text} />
                )}
              </div>

              {/* Structured UI inside Bot Bubble */}
              {msg.service_code && (
                <div className="w-full bg-white rounded-xl border border-brand-200 p-4 shadow-sm space-y-4">
                  <div className="flex items-center space-x-2">
                    <ShieldCheck className="h-4 w-4 text-primary-500" />
                    <span className="text-[11px] font-bold text-brand-900 uppercase tracking-wider">
                      {msg.service_code.replace(/_/g, ' ')}
                    </span>
                  </div>

                  {(msg.required_documents?.length || 0) > 0 && (
                    <div>
                      <span className="text-[10px] font-bold text-brand-500 uppercase tracking-wider mb-2 block">
                        Required Documents
                      </span>
                      <div className="space-y-2">
                        {msg.required_documents?.map((doc, idx) => {
                          const uploaded = uploadedDocs.find(d => d.document_type === doc && d.verification_status === "VERIFIED");
                          return (
                            <div key={idx} className="flex items-center space-x-2 text-xs">
                              {uploaded ? (
                                <CheckCircle2 className="h-4 w-4 text-success-500" />
                              ) : (
                                <Circle className="h-4 w-4 text-brand-300" />
                              )}
                              <span className={uploaded ? "text-brand-900 line-through opacity-70" : "text-brand-900 font-medium"}>
                                {doc.replace(/_/g, ' ')}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {msg.status === "MISSING_INFORMATION" && (
                    <div className="bg-warning-50 border border-warning-200 rounded-lg p-3">
                      <div className="flex items-start space-x-2">
                        <AlertTriangle className="h-4 w-4 text-warning-600 mt-0.5 shrink-0" />
                        <div className="text-xs text-warning-800 space-y-1">
                          <span className="font-bold block">Action Required</span>
                          <span className="block">Please upload the missing documents or provide the required details in the chat.</span>
                        </div>
                      </div>
                    </div>
                  )}
                  
                  {msg.status === "COLLECTING_DOCUMENTS" && !uploading && (
                    <div className="pt-2">
                      <DocumentUploader onUpload={handleFileUpload} uploading={uploading} />
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}

        {!hasUserMessages && (
          <div className="flex flex-col items-center justify-center h-full py-10 space-y-6">
            <div className="flex flex-col items-center space-y-3">
              <span className="text-4xl mb-2">✨</span>
              <h2 className="text-xl font-extrabold text-brand-900 tracking-tight">How can SEVA help?</h2>
              <p className="text-sm text-brand-500 text-center max-w-[280px]">Tell me what government service you need. I'll guide you through the process.</p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-[440px] pt-4">
              <button onClick={() => handleSend("Apply for an Income Certificate")} className="px-4 py-3.5 bg-white border border-brand-200 hover:border-primary-300 hover:bg-primary-50 hover:shadow-sm rounded-xl text-[13px] font-semibold text-brand-700 transition-all text-center">
                Income Certificate
              </button>
              <button onClick={() => handleSend("Get a Birth Certificate")} className="px-4 py-3.5 bg-white border border-brand-200 hover:border-primary-300 hover:bg-primary-50 hover:shadow-sm rounded-xl text-[13px] font-semibold text-brand-700 transition-all text-center">
                Birth Certificate
              </button>
              <button onClick={() => handleSend("Apply for a Driving Licence")} className="px-4 py-3.5 bg-white border border-brand-200 hover:border-primary-300 hover:bg-primary-50 hover:shadow-sm rounded-xl text-[13px] font-semibold text-brand-700 transition-all text-center">
                Driving Licence
              </button>
              <button onClick={() => handleSend("What documents do I need?")} className="px-4 py-3.5 bg-white border border-brand-200 hover:border-primary-300 hover:bg-primary-50 hover:shadow-sm rounded-xl text-[13px] font-semibold text-brand-700 transition-all text-center">
                What documents do I need?
              </button>
            </div>
          </div>
        )}

        {/* Agent Activity / Loading */}
        {(loading || uploading || agentActivity) && (
          <div className="flex justify-start pl-2">
            <div className="flex items-center space-x-2 bg-white border border-brand-200 px-3 py-2 rounded-xl shadow-xs">
              <Loader2 className="h-3.5 w-3.5 text-primary-500 animate-spin shrink-0" />
              <span className="text-xs font-medium text-brand-600 animate-pulse">
                {agentActivity || (uploading ? "Uploading document..." : "SEVA is working...")}
              </span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 bg-white border-t border-brand-100">
        <form 
          onSubmit={(e) => { e.preventDefault(); handleSend(); }} 
          className="flex items-end space-x-2 bg-brand-50 border border-brand-200 rounded-2xl p-2 focus-within:ring-2 focus-within:ring-primary-500 focus-within:border-transparent transition-all shadow-sm"
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Tell SEVA what you need..."
            className="flex-1 bg-transparent text-[13px] px-3 py-2.5 min-h-[44px] max-h-[120px] resize-none focus:outline-none text-brand-900 placeholder:text-brand-400 font-medium"
            disabled={loading || uploading}
            rows={1}
          />
          <button
            type="submit"
            disabled={loading || uploading || !input.trim()}
            className="h-[44px] w-[44px] bg-brand-900 hover:bg-brand-800 disabled:bg-brand-200 disabled:text-brand-400 text-white rounded-xl flex items-center justify-center transition-colors shrink-0 mb-0 shadow-sm"
          >
            <Send className="h-4 w-4 ml-0.5" />
          </button>
        </form>
      </div>
    </div>
  );
}
