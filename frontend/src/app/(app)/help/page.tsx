"use client";

import React from "react";
import Link from "next/link";
import { HelpCircle, ChevronRight, FileText, Upload, ShieldCheck, Activity } from "lucide-react";

export default function HelpPage() {
  return (
    <div className="max-w-4xl mx-auto space-y-8 pb-12">
      <div className="flex items-center space-x-3 mb-6">
        <div className="h-10 w-10 bg-brand-100 rounded-xl flex items-center justify-center text-brand-600">
          <HelpCircle className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-extrabold text-brand-900">Help & Support</h1>
          <p className="text-sm text-brand-500">Learn how to use SEVA AI to manage your government services.</p>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl border border-brand-200 p-6 shadow-sm">
          <div className="flex items-center space-x-3 mb-4">
            <div className="h-8 w-8 bg-primary-50 rounded-lg flex items-center justify-center text-primary-600">
              <FileText className="h-4 w-4" />
            </div>
            <h2 className="text-lg font-bold text-brand-900">What SEVA AI Does</h2>
          </div>
          <p className="text-sm text-brand-600 leading-relaxed mb-4">
            SEVA AI is your personal government services assistant. It helps you apply for services like Income Certificates, Birth Certificates, and Driving Licences by automatically guiding you through the required steps and documents.
          </p>
          <ul className="text-sm text-brand-600 list-disc list-inside space-y-1">
            <li>Income Certificate</li>
            <li>Birth Certificate</li>
            <li>Driving Licence</li>
          </ul>
        </div>

        <div className="bg-white rounded-2xl border border-brand-200 p-6 shadow-sm">
          <div className="flex items-center space-x-3 mb-4">
            <div className="h-8 w-8 bg-primary-50 rounded-lg flex items-center justify-center text-primary-600">
              <Upload className="h-4 w-4" />
            </div>
            <h2 className="text-lg font-bold text-brand-900">Document Upload</h2>
          </div>
          <p className="text-sm text-brand-600 leading-relaxed">
            When you chat with SEVA, it will ask for required documents. You can easily drag and drop your PDFs or images directly into the chat. Once uploaded, documents are saved in your secure <strong>Document Vault</strong> for future applications.
          </p>
        </div>

        <div className="bg-white rounded-2xl border border-brand-200 p-6 shadow-sm">
          <div className="flex items-center space-x-3 mb-4">
            <div className="h-8 w-8 bg-primary-50 rounded-lg flex items-center justify-center text-primary-600">
              <ShieldCheck className="h-4 w-4" />
            </div>
            <h2 className="text-lg font-bold text-brand-900">Application Consent</h2>
          </div>
          <p className="text-sm text-brand-600 leading-relaxed">
            SEVA will never submit an application without your explicit consent. Before submission, you will see an <strong>Application Preview</strong>. You must review the gathered information and click <strong>Approve & Submit</strong> to officially file your request.
          </p>
        </div>

        <div className="bg-white rounded-2xl border border-brand-200 p-6 shadow-sm">
          <div className="flex items-center space-x-3 mb-4">
            <div className="h-8 w-8 bg-primary-50 rounded-lg flex items-center justify-center text-primary-600">
              <Activity className="h-4 w-4" />
            </div>
            <h2 className="text-lg font-bold text-brand-900">Tracking Applications</h2>
          </div>
          <p className="text-sm text-brand-600 leading-relaxed">
            After submission, you'll receive a Government Reference ID. You can track the progress of your application on the <strong>Applications</strong> page. Real-time updates and notifications will appear in your <strong>Activity</strong> feed.
          </p>
        </div>
      </div>

      <div className="bg-brand-50 rounded-2xl border border-brand-200 p-6 text-center">
        <h3 className="font-bold text-brand-900 mb-2">Ready to get started?</h3>
        <p className="text-sm text-brand-600 mb-6">Head back to your dashboard to start a new application.</p>
        <Link 
          href="/dashboard"
          className="inline-flex items-center justify-center px-6 py-2.5 bg-brand-900 hover:bg-brand-800 text-white font-medium rounded-xl transition-colors shadow-sm"
        >
          Go to Dashboard
          <ChevronRight className="h-4 w-4 ml-2" />
        </Link>
      </div>
    </div>
  );
}
