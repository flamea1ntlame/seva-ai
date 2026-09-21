import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";
import { EventProvider } from "@/contexts/EventContext";
import { Toaster } from "react-hot-toast";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "SEVA AI - Citizen Services & Document Vault",
  description: "Empowering citizens with seamless AI-assisted government service applications",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen bg-brand-50 flex flex-col antialiased font-sans text-brand-900">
        <AuthProvider>
          <EventProvider>
            <Toaster position="top-right" />
            {children}
          </EventProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
