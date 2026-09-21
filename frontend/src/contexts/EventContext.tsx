"use client";

import React, { createContext, useContext, useState, ReactNode } from "react";

interface EventContextType {
  agentActivity: string | null;
  setAgentActivity: (activity: string | null) => void;
}

const EventContext = createContext<EventContextType | undefined>(undefined);

export const EventProvider = ({ children }: { children: ReactNode }) => {
  const [agentActivity, setAgentActivity] = useState<string | null>(null);

  return (
    <EventContext.Provider value={{ agentActivity, setAgentActivity }}>
      {children}
    </EventContext.Provider>
  );
};

export const useEventContext = () => {
  const context = useContext(EventContext);
  if (context === undefined) {
    throw new Error("useEventContext must be used within an EventProvider");
  }
  return context;
};
