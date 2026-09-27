"use client";

import { useEffect } from "react";
import { useEventContext } from "@/contexts/EventContext";
import { getApiBaseUrl } from "@/lib/api";
import toast from "react-hot-toast";

export default function SSEListener() {
  const { setAgentActivity } = useEventContext();

  useEffect(() => {
    // Only connect if there's a token
    const rawToken = typeof window !== "undefined" ? localStorage.getItem("seva_token") : null;
    const token =
      rawToken && rawToken !== "null" && rawToken !== "undefined" && rawToken.trim() !== ""
        ? rawToken.trim()
        : null;
    if (!token) return;

    // Use EventSource / manual fetch streaming with Bearer token
    const controller = new AbortController();
    
    const connectToStream = async () => {
      try {
        const baseUrl = getApiBaseUrl();
        const response = await fetch(`${baseUrl}/api/events/stream`, {
          headers: {
            "Authorization": `Bearer ${token}`
          },
          signal: controller.signal
        });

        if (response.status === 401 || response.status === 403) {
          // Token is invalid/expired or forbidden; do not loop reconnect
          return;
        }

        if (!response.body) return;
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop() || ""; // Keep the incomplete part

          for (const part of parts) {
            if (part.startsWith("data: ")) {
              const dataStr = part.replace("data: ", "");
              try {
                const eventData = JSON.parse(dataStr);
                
                if (eventData.event === "APPLICATION_STATUS_CHANGED") {
                  const { government_status, service_code, seva_status } = eventData.data;
                  const serviceName = service_code.split("_").map((w: string) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
                  
                  if (government_status === "UNDER_REVIEW") {
                    toast(`Your ${serviceName} application is now under review.`, { icon: "🔄" });
                  } else if (government_status === "APPROVED" || seva_status === "COMPLETED") {
                    toast.success(`Your ${serviceName} application has been approved!`);
                  } else if (government_status === "REJECTED") {
                    toast.error(`Your ${serviceName} application was rejected.`);
                  }
                } else if (eventData.event === "AGENT_ACTIVITY") {
                  setAgentActivity(eventData.data.activity);
                  // Auto-clear after 10s if stuck
                  setTimeout(() => setAgentActivity(null), 10000);
                }
              } catch (e) {
                console.error("Failed to parse SSE event", e);
              }
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          console.error("SSE connection error", err);
          // Auto-reconnect after 5s
          setTimeout(connectToStream, 5000);
        }
      }
    };

    connectToStream();

    return () => {
      controller.abort();
    };
  }, [setAgentActivity]);

  return null;
}
