"use client";

import React, { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { ArrowRight, CheckCircle2, FileText, Loader2, LockKeyhole, Upload } from "lucide-react";

const validateEmail = (email: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());

interface AccessInfo {
  valid: boolean;
  interview_id: string;
  role_title: string;
  interview_type: string;
  duration_minutes: number;
  deadline_at: string;
  status: string;
  resume_uploaded: boolean;
  resume_analyzed: boolean;
  candidate_name?: string | null;
  candidate_email?: string | null;
  session_id?: string | null;
}

export default function CandidateAccessPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [code, setCode] = useState("");
  const [candidateName, setCandidateName] = useState("");
  const [candidateEmail, setCandidateEmail] = useState("");
  const [accessInfo, setAccessInfo] = useState<AccessInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const normalizedCode = code.trim().toUpperCase();

  const validateCode = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.validateCandidateCode(normalizedCode);
      setAccessInfo(res.data);
      setCandidateName(res.data.candidate_name || "");
      setCandidateEmail(res.data.candidate_email || "");
    } catch (err: any) {
      setAccessInfo(null);
      setError(err.response?.data?.detail || "Invalid or expired interview code.");
    } finally {
      setLoading(false);
    }
  };

  const uploadResume = async (file: File) => {
    if (candidateName.trim().length < 2) {
      setError("Please enter the candidate's full name.");
      return;
    }
    if (!validateEmail(candidateEmail)) {
      setError("Please enter a valid candidate email address.");
      return;
    }

    setUploading(true);
    setError(null);
    try {
      const res = await api.uploadCandidateResume(normalizedCode, file, candidateName, candidateEmail);
      setAccessInfo(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to upload resume.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const refreshStatus = async () => {
    if (!normalizedCode) return;
    try {
      const res = await api.validateCandidateCode(normalizedCode);
      setAccessInfo(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Could not refresh interview status.");
    }
  };

  const startInterview = async () => {
    if (candidateName.trim().length < 2) {
      setError("Please enter the candidate's full name.");
      return;
    }
    if (!validateEmail(candidateEmail)) {
      setError("Please enter a valid candidate email address.");
      return;
    }

    setStarting(true);
    setError(null);
    try {
      const res = await api.startCandidateInterview(normalizedCode, candidateName, candidateEmail);
      sessionStorage.setItem(`access_code:${res.data.session_id}`, normalizedCode);
      router.push(`/session/${res.data.session_id}?access_code=${encodeURIComponent(normalizedCode)}`);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (detail === "resume_still_processing") {
        setError("Your resume is still being analyzed. Try again in a moment.");
        refreshStatus();
      } else {
        setError(detail || "Could not start the interview.");
      }
    } finally {
      setStarting(false);
    }
  };

  const candidateNameError = candidateName && candidateName.trim().length < 2 ? "Please enter the candidate's full name." : null;
  const candidateEmailError = candidateEmail && !validateEmail(candidateEmail) ? "Please enter a valid candidate email address." : null;
  const candidateIdentityInvalid = candidateName.trim().length < 2 || !validateEmail(candidateEmail);

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-slate-100 flex items-center justify-center p-4 md:p-8">
      <div className="w-full max-w-3xl">
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center p-4 bg-indigo-500/10 rounded-2xl mb-5 border border-indigo-500/20">
            <LockKeyhole className="text-indigo-400 h-9 w-9" />
          </div>
          <h1 className="text-4xl font-black tracking-tight">Candidate Interview Access</h1>
          <p className="mt-3 text-slate-400">Enter the secure code shared by your recruiter to start your AI interview.</p>
        </div>

        {error && <div className="mb-6 rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-red-300">{error}</div>}

        <div className="bg-slate-900/50 border border-white/10 rounded-3xl overflow-hidden shadow-2xl">
          <div className="p-8 grid gap-6">
            <div>
              <label className="block text-sm font-semibold uppercase tracking-wider text-slate-400 mb-3">Access code</label>
              <div className="flex gap-3">
                <input
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="ABCD-123-XYZ"
                  className="flex-1 bg-slate-950/80 border border-white/10 rounded-2xl px-5 py-4 font-mono tracking-widest text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-indigo-500/50"
                />
                <Button disabled={!code.trim() || loading} onClick={validateCode} className="bg-indigo-600 hover:bg-indigo-500 px-6">
                  {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : "Validate"}
                </Button>
              </div>
            </div>

            {accessInfo && (
              <div className="grid gap-6 animate-in fade-in slide-in-from-bottom-4">
                <div className="rounded-2xl bg-indigo-500/10 border border-indigo-500/20 p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h2 className="text-2xl font-black">{accessInfo.role_title}</h2>
                      <p className="text-slate-400 mt-1 capitalize">{accessInfo.interview_type} interview • {accessInfo.duration_minutes} minutes</p>
                    </div>
                    <span className="text-xs uppercase tracking-wider border border-indigo-500/30 text-indigo-200 rounded-full px-3 py-1">
                      {accessInfo.status.replace("_", " ")}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mt-4">Deadline {new Date(accessInfo.deadline_at).toLocaleString()}</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <input
                    value={candidateName}
                    onChange={(e) => setCandidateName(e.target.value)}
                    placeholder="Your name"
                    className="bg-slate-950/80 border border-white/10 rounded-2xl px-5 py-4 text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-indigo-500/50"
                  />
                  <input
                    type="email"
                    value={candidateEmail}
                    onChange={(e) => setCandidateEmail(e.target.value)}
                    placeholder="Your email"
                    className="bg-slate-950/80 border border-white/10 rounded-2xl px-5 py-4 text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-indigo-500/50"
                  />
                  {candidateNameError && <p className="text-sm text-red-300">{candidateNameError}</p>}
                  {candidateEmailError && <p className="text-sm text-red-300">{candidateEmailError}</p>}
                </div>

                <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
                  <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                    <div className="flex items-center gap-3">
                      {accessInfo.resume_uploaded ? (
                        <CheckCircle2 className="w-6 h-6 text-emerald-400" />
                      ) : (
                        <FileText className="w-6 h-6 text-slate-500" />
                      )}
                      <div>
                        <div className="font-bold">Candidate resume</div>
                        <div className="text-sm text-slate-400">
                          {accessInfo.resume_uploaded
                            ? accessInfo.resume_analyzed ? "Resume analyzed and ready" : "Resume uploaded, analysis in progress"
                            : "Upload your CV to personalize the interview"}
                        </div>
                      </div>
                    </div>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".pdf,.docx,.txt"
                      className="hidden"
                      onChange={(e) => e.target.files?.[0] && uploadResume(e.target.files[0])}
                    />
                    <Button onClick={() => fileInputRef.current?.click()} disabled={uploading || accessInfo.status === "in_progress" || candidateIdentityInvalid} variant="outline" className="bg-transparent border-slate-700 text-slate-300 gap-2">
                      {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                      Upload CV
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </div>

          {accessInfo && (
            <div className="p-6 border-t border-white/5 flex justify-end gap-3 bg-black/20">
              {accessInfo.resume_uploaded && !accessInfo.resume_analyzed && (
                <Button onClick={refreshStatus} variant="outline" className="bg-transparent border-slate-700 text-slate-300">
                  Refresh analysis status
                </Button>
              )}
              <Button
                onClick={startInterview}
                disabled={!accessInfo.resume_uploaded || !accessInfo.resume_analyzed || candidateIdentityInvalid || starting}
                className="bg-indigo-600 hover:bg-indigo-500 px-8 gap-2"
              >
                {starting ? <Loader2 className="w-5 h-5 animate-spin" /> : <>Start Interview <ArrowRight className="w-5 h-5" /></>}
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
