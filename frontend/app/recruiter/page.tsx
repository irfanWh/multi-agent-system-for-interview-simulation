"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/Button";
import { Briefcase, CalendarClock, Copy, FileText, Plus, RefreshCw, ShieldCheck, UserRound } from "lucide-react";

interface RecruiterInterview {
  id: string;
  role_title: string;
  interview_type: string;
  duration_minutes: number;
  deadline_at: string;
  status: string;
  code_hint: string;
  access_code?: string | null;
  candidate_name?: string | null;
  candidate_email?: string | null;
  session_id?: string | null;
  report_ready: boolean;
  created_at: string;
}

const statusClass = (status: string) => {
  if (status === "completed") return "bg-emerald-500/10 text-emerald-300 border-emerald-500/20";
  if (status === "in_progress") return "bg-blue-500/10 text-blue-300 border-blue-500/20";
  if (status === "expired") return "bg-red-500/10 text-red-300 border-red-500/20";
  if (status === "pending") return "bg-amber-500/10 text-amber-300 border-amber-500/20";
  return "bg-indigo-500/10 text-indigo-300 border-indigo-500/20";
};

export default function RecruiterDashboard() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [sessions, setSessions] = useState<RecruiterInterview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [freshCode, setFreshCode] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) router.push("/");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (user) loadSessions();
  }, [user]);

  const loadSessions = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getRecruiterSessions();
      setSessions(res.data);
    } catch {
      setError("Failed to load recruiter sessions.");
    } finally {
      setLoading(false);
    }
  };

  const copyText = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setFreshCode(text);
    setTimeout(() => setFreshCode(null), 2500);
  };

  const regenerateCode = async (id: string) => {
    try {
      const res = await api.regenerateRecruiterCode(id);
      await loadSessions();
      if (res.data.access_code) copyText(res.data.access_code);
    } catch {
      setError("Could not regenerate this code.");
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-slate-100 pb-16">
      <header className="sticky top-0 z-40 bg-[#0a0a0f]/80 backdrop-blur-md border-b border-white/5 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-indigo-500/20 flex items-center justify-center border border-indigo-500/30">
              <ShieldCheck className="w-5 h-5 text-indigo-300" />
            </div>
            <div>
              <h1 className="text-xl font-bold">Recruiter Mode</h1>
              <p className="text-xs text-slate-500">Invite candidates and review AI interview reports</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Button onClick={() => router.push("/dashboard")} variant="outline" className="bg-transparent border-slate-700 text-slate-300 hover:bg-slate-800">
              Candidate Dashboard
            </Button>
            <Button onClick={() => router.push("/recruiter/new")} className="bg-indigo-600 hover:bg-indigo-500 gap-2">
              <Plus className="w-4 h-4" /> Create Session
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8">
        <div className="mb-8 flex flex-col md:flex-row md:items-end md:justify-between gap-4">
          <div>
            <h2 className="text-3xl font-black tracking-tight">Interview invitations</h2>
            <p className="text-slate-400 mt-2">Each code opens one assigned AI interview flow for a candidate.</p>
          </div>
          {freshCode && (
            <div className="text-sm text-emerald-300 bg-emerald-500/10 border border-emerald-500/20 px-4 py-2 rounded-xl">
              Code copied: {freshCode}
            </div>
          )}
        </div>

        {error && <div className="mb-6 rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-red-300">{error}</div>}

        <div className="bg-slate-900/40 border border-white/5 rounded-3xl overflow-hidden">
          {loading ? (
            <div className="p-12 text-center text-slate-400">Loading recruiter sessions...</div>
          ) : sessions.length === 0 ? (
            <div className="p-12 text-center">
              <Briefcase className="w-12 h-12 text-slate-600 mx-auto mb-4" />
              <h3 className="text-lg font-bold mb-2">No recruiter sessions yet</h3>
              <p className="text-slate-400 mb-6">Create an interview invite and share its access code with your candidate.</p>
              <Button onClick={() => router.push("/recruiter/new")} className="bg-indigo-600 hover:bg-indigo-500">Create first invite</Button>
            </div>
          ) : (
            <div className="divide-y divide-white/5">
              {sessions.map((session) => (
                <div key={session.id} className="p-6 grid grid-cols-1 lg:grid-cols-[1.5fr_1fr_auto] gap-6 items-center hover:bg-white/[0.02]">
                  <div>
                    <div className="flex flex-wrap items-center gap-3 mb-3">
                      <h3 className="text-xl font-bold">{session.role_title}</h3>
                      <span className={`text-xs uppercase tracking-wider border rounded-full px-2.5 py-1 ${statusClass(session.status)}`}>
                        {session.status.replace("_", " ")}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-4 text-sm text-slate-400">
                      <span className="flex items-center gap-2"><Briefcase className="w-4 h-4" /> {session.interview_type}</span>
                      <span className="flex items-center gap-2"><CalendarClock className="w-4 h-4" /> {session.duration_minutes} min</span>
                      <span>Deadline {new Date(session.deadline_at).toLocaleString()}</span>
                    </div>
                  </div>

                  <div className="text-sm">
                    <div className="flex items-center gap-2 text-slate-300 mb-2">
                      <UserRound className="w-4 h-4 text-slate-500" />
                      {session.candidate_name || session.candidate_email || "Waiting for candidate"}
                    </div>
                    <div className="text-slate-500">Code ending {session.code_hint}</div>
                  </div>

                  <div className="flex flex-wrap justify-start lg:justify-end gap-2">
                    <Button
                      onClick={() => regenerateCode(session.id)}
                      disabled={["completed", "in_progress"].includes(session.status)}
                      variant="outline"
                      className="bg-transparent border-slate-700 text-slate-300 hover:bg-slate-800 gap-2"
                    >
                      <RefreshCw className="w-4 h-4" /> New Code
                    </Button>
                    {session.report_ready ? (
                      <Button onClick={() => router.push(`/session/${session.session_id}/report`)} className="bg-emerald-600 hover:bg-emerald-500 gap-2">
                        <FileText className="w-4 h-4" /> View Report
                      </Button>
                    ) : session.status === "completed" ? (
                      <span className="inline-flex items-center rounded-md border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-300">
                        Report unavailable
                      </span>
                    ) : (
                      <Button
                        onClick={() => copyText(`${window.location.origin}/access`)}
                        variant="outline"
                        className="bg-transparent border-indigo-500/30 text-indigo-300 hover:bg-indigo-500/10 gap-2"
                      >
                        <Copy className="w-4 h-4" /> Copy Access Link
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
