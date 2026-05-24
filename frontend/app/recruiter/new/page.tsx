"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import DurationPicker from "@/components/DurationPicker";
import { ArrowLeft, CalendarClock, CheckCircle2, Copy, Loader2, ShieldCheck } from "lucide-react";

const validateEmail = (email: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());

const validateJobDescription = (text: string) => {
  if (!text || text.trim().length === 0) return null;

  const cleanText = text.trim();
  const wordCount = cleanText.split(/\s+/).filter(Boolean).length;

  if (wordCount < 50 && cleanText.length < 300) {
    return "Please enter a valid job description with responsibilities, required skills, and experience level.";
  }

  const meaningfulKeywords = [
    "role", "responsibilities", "skills", "requirements", "experience",
    "qualifications", "technologies", "tasks", "company", "developer",
    "engineer", "manager", "lead", "senior", "junior", "degree",
    "knowledge", "proficiency", "working", "ability",
    "mission", "profil recherché", "compétences", "expérience",
    "responsabilités", "offre d'emploi", "profil", "requis"
  ];

  const hasMeaningfulTerms = meaningfulKeywords.some((keyword) => cleanText.toLowerCase().includes(keyword));
  if (!hasMeaningfulTerms || /(.)\1{10,}/.test(cleanText)) {
    return "Please enter a valid job description with responsibilities, required skills, and experience level.";
  }

  return null;
};

export default function NewRecruiterSessionPage() {
  const router = useRouter();
  const [roleTitle, setRoleTitle] = useState("");
  const [candidateName, setCandidateName] = useState("");
  const [candidateEmail, setCandidateEmail] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [interviewType, setInterviewType] = useState<"technical" | "behavioral" | "mixed">("mixed");
  const [duration, setDuration] = useState(30);
  const [deadline, setDeadline] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdCode, setCreatedCode] = useState<string | null>(null);

  const createSession = async () => {
    const jobError = validateJobDescription(jobDescription);
    if (candidateName.trim().length < 2) {
      setError("Please enter the candidate's full name.");
      return;
    }
    if (!validateEmail(candidateEmail)) {
      setError("Please enter a valid candidate email address.");
      return;
    }
    if (jobError) {
      setError(jobError);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await api.createRecruiterSession({
        role_title: roleTitle,
        candidate_name: candidateName,
        candidate_email: candidateEmail,
        job_description: jobDescription,
        interview_type: interviewType,
        duration_minutes: duration,
        deadline_at: new Date(deadline).toISOString(),
      });
      setCreatedCode(res.data.access_code);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to create recruiter session.");
    } finally {
      setLoading(false);
    }
  };

  const jobDescriptionError = validateJobDescription(jobDescription);
  const candidateNameError = candidateName && candidateName.trim().length < 2 ? "Please enter the candidate's full name." : null;
  const candidateEmailError = candidateEmail && !validateEmail(candidateEmail) ? "Please enter a valid candidate email address." : null;
  const canSubmit = (
    roleTitle.trim().length > 1 &&
    candidateName.trim().length >= 2 &&
    validateEmail(candidateEmail) &&
    jobDescription.trim().length >= 50 &&
    !jobDescriptionError &&
    deadline &&
    !loading
  );

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-slate-100 p-4 md:p-8">
      <div className="max-w-5xl mx-auto">
        <button onClick={() => router.push("/recruiter")} className="mb-8 inline-flex items-center gap-2 text-slate-400 hover:text-white">
          <ArrowLeft className="w-4 h-4" /> Back to recruiter dashboard
        </button>

        <div className="mb-10">
          <div className="inline-flex items-center justify-center p-3 bg-indigo-500/10 rounded-2xl mb-4 border border-indigo-500/20">
            <ShieldCheck className="text-indigo-400 h-8 w-8" />
          </div>
          <h1 className="text-4xl font-black tracking-tight">Create recruiter interview</h1>
          <p className="mt-3 text-slate-400">Configure the interview invite. The candidate will upload their CV after entering the secure code.</p>
        </div>

        {error && <div className="mb-6 rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-red-300">{error}</div>}

        {createdCode ? (
          <div className="bg-slate-900/50 border border-white/10 rounded-3xl p-8 text-center">
            <CheckCircle2 className="w-14 h-14 text-emerald-400 mx-auto mb-5" />
            <h2 className="text-2xl font-black mb-2">Interview code generated</h2>
            <p className="text-slate-400 mb-6">Share this code with the candidate. It is shown once; regenerate from the recruiter dashboard if needed.</p>
            <div className="inline-flex items-center gap-3 bg-black/30 border border-indigo-500/30 rounded-2xl px-6 py-4 mb-6">
              <span className="font-mono text-3xl tracking-widest text-indigo-200">{createdCode}</span>
              <button onClick={() => navigator.clipboard.writeText(createdCode)} className="p-2 rounded-lg hover:bg-white/10 text-slate-300">
                <Copy className="w-5 h-5" />
              </button>
            </div>
            <div className="flex justify-center gap-3">
              <Button onClick={() => navigator.clipboard.writeText(`${window.location.origin}/access`)} variant="outline" className="bg-transparent border-slate-700 text-slate-300">
                Copy candidate access link
              </Button>
              <Button onClick={() => router.push("/recruiter")} className="bg-indigo-600 hover:bg-indigo-500">
                Done
              </Button>
            </div>
          </div>
        ) : (
          <div className="bg-slate-900/40 border border-white/10 rounded-3xl overflow-hidden">
            <div className="p-8 grid gap-8">
              <div>
                <label className="block text-sm font-semibold uppercase tracking-wider text-slate-400 mb-3">Role</label>
                <input
                  value={roleTitle}
                  onChange={(e) => setRoleTitle(e.target.value)}
                  placeholder="Senior Backend Engineer"
                  className="w-full bg-slate-950/80 border border-white/10 rounded-2xl px-5 py-4 text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-indigo-500/50"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-semibold uppercase tracking-wider text-slate-400 mb-3">Candidate name</label>
                  <input
                    value={candidateName}
                    onChange={(e) => setCandidateName(e.target.value)}
                    placeholder="Candidate full name"
                    className="w-full bg-slate-950/80 border border-white/10 rounded-2xl px-5 py-4 text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-indigo-500/50"
                  />
                  {candidateNameError && <p className="mt-2 text-sm text-red-300">{candidateNameError}</p>}
                </div>
                <div>
                  <label className="block text-sm font-semibold uppercase tracking-wider text-slate-400 mb-3">Candidate email</label>
                  <input
                    type="email"
                    value={candidateEmail}
                    onChange={(e) => setCandidateEmail(e.target.value)}
                    placeholder="candidate@example.com"
                    className="w-full bg-slate-950/80 border border-white/10 rounded-2xl px-5 py-4 text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-indigo-500/50"
                  />
                  {candidateEmailError && <p className="mt-2 text-sm text-red-300">{candidateEmailError}</p>}
                </div>
              </div>

              <div>
                <label className="block text-sm font-semibold uppercase tracking-wider text-slate-400 mb-3">Job description</label>
                <textarea
                  value={jobDescription}
                  onChange={(e) => setJobDescription(e.target.value)}
                  placeholder="Paste the role responsibilities, requirements, skills, and interview context..."
                  className="w-full min-h-[220px] bg-slate-950/80 border border-white/10 rounded-2xl px-5 py-4 text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-indigo-500/50 resize-y"
                />
                {jobDescriptionError && <p className="mt-2 text-sm text-red-300">{jobDescriptionError}</p>}
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div>
                  <label className="block text-sm font-semibold uppercase tracking-wider text-slate-400 mb-3">Interview type</label>
                  <div className="grid grid-cols-3 gap-3">
                    {(["technical", "behavioral", "mixed"] as const).map((type) => (
                      <button
                        key={type}
                        onClick={() => setInterviewType(type)}
                        className={`capitalize rounded-2xl border px-4 py-4 font-bold transition ${
                          interviewType === type
                            ? "bg-indigo-500/20 border-indigo-500/50 text-indigo-200"
                            : "bg-white/5 border-white/10 text-slate-400 hover:bg-white/10"
                        }`}
                      >
                        {type}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-semibold uppercase tracking-wider text-slate-400 mb-3">Deadline</label>
                  <div className="relative">
                    <CalendarClock className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 w-5 h-5" />
                    <input
                      type="datetime-local"
                      value={deadline}
                      onChange={(e) => setDeadline(e.target.value)}
                      className="w-full bg-slate-950/80 border border-white/10 rounded-2xl pl-12 pr-5 py-4 text-slate-100 focus:outline-none focus:border-indigo-500/50"
                    />
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-sm font-semibold uppercase tracking-wider text-slate-400 mb-4">Duration</label>
                <DurationPicker value={duration} onChange={setDuration} min={5} max={120} step={5} />
              </div>
            </div>

            <div className="p-6 border-t border-white/5 flex justify-end bg-black/20">
              <Button disabled={!canSubmit} onClick={createSession} className="bg-indigo-600 hover:bg-indigo-500 px-8 py-3">
                {loading ? <><Loader2 className="mr-2 h-5 w-5 animate-spin" /> Creating...</> : "Generate secure code"}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
