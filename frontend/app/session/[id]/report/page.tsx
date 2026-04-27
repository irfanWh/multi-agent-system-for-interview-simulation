"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Loader2, Download, CheckCircle2, AlertCircle, TrendingUp, Award, Zap, ArrowLeft, ExternalLink } from "lucide-react";

interface Evaluation {
  exchange_id: string;
  turn_number: number;
  question: string;
  candidate_answer: string;
  evaluation: {
    score_accuracy: number;
    score_depth: number;
    score_clarity: number;
    score_star: number;
    feedback: string;
    improvement_tips: {
      tips: string[];
      strengths: string[];
      global_score: number;
    };
  };
}

interface ReportData {
  id: string;
  session_id: string;
  global_score: number;
  competency_breakdown: Record<string, {
    score: number;
    nb_questions: number;
    feedback: string;
  }>;
  action_plan: Array<{
    step: string;
    resources: string;
    timeframe: string;
  }>;
  pdf_url: string;
  generated_at: string;
}

export default function ReportPage() {
  const { id } = useParams();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [report, setReport] = useState<ReportData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    loadReport();
  }, [id]);

  const loadReport = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getReport(id as string);
      setReport(res.data);
      setLoading(false);
    } catch (err: any) {
      // If report doesn't exist yet, it will return 404
      if (err.response?.data?.detail === "Report not found for this session. Generate it first." || 
          err.response?.status === 404) {
        generateReport();
      } else {
        setError("Failed to load report. Please try again.");
        setLoading(false);
      }
    }
  };

  const generateReport = async () => {
    setGenerating(true);
    setError(null);
    try {
      await api.generateReport(id as string);
      // Poll for completion
      pollReport();
    } catch (err) {
      setError("Failed to trigger report generation. Ensure the interview is complete.");
      setGenerating(false);
    }
  };

  const pollReport = async () => {
    const maxAttempts = 30;
    let attempts = 0;
    
    const interval = setInterval(async () => {
      attempts++;
      try {
        const res = await api.getReport(id as string);
        if (res.data.pdf_url) {
          setReport(res.data);
          setGenerating(false);
          setLoading(false);
          clearInterval(interval);
        }
      } catch (err) {
        if (attempts >= maxAttempts) {
          setError("Report generation is taking longer than expected. Please refresh this page in a minute.");
          setGenerating(false);
          clearInterval(interval);
        }
      }
    }, 4000);
  };

  if (loading || generating) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-white p-6 font-sans">
        <div className="relative w-24 h-24 mb-8">
          <div className="absolute inset-0 border-4 border-indigo-500/20 rounded-full" />
          <div className="absolute inset-0 border-4 border-t-indigo-500 rounded-full animate-spin" />
          <div className="absolute inset-0 flex items-center justify-center">
            <Zap className="w-10 h-10 text-indigo-400 animate-pulse" />
          </div>
        </div>
        <h2 className="text-2xl font-bold mb-2">Generating your Interview Insights...</h2>
        <p className="text-slate-400 text-center max-w-md">
          Our AI is evaluating your responses, aggregating scores across domains, and preparing your personalized PDF report.
        </p>
        <div className="mt-8 flex items-center gap-2 text-slate-500 text-sm">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span>This usually takes 30-60 seconds</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-white p-6 font-sans">
        <div className="w-16 h-16 bg-red-500/10 border border-red-500/20 rounded-full flex items-center justify-center mb-6">
          <AlertCircle className="w-10 h-10 text-red-500" />
        </div>
        <h2 className="text-2xl font-bold mb-4">{error}</h2>
        <div className="flex gap-4">
          <Button onClick={() => router.push('/dashboard')} variant="outline" className="border-slate-800 text-slate-300">
            Back to Dashboard
          </Button>
          <Button onClick={loadReport} className="bg-indigo-600 hover:bg-indigo-500">
            Try Again
          </Button>
        </div>
      </div>
    );
  }

  if (!report) return null;

  return (
    <div className="min-h-screen bg-[#020617] text-slate-200 pb-20 font-sans selection:bg-indigo-500/30">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-[#020617]/80 backdrop-blur-md border-b border-white/5 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button 
              onClick={() => router.push('/dashboard')}
              className="p-2 hover:bg-white/5 rounded-lg transition-colors text-slate-400"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="h-8 w-[1px] bg-white/10 mx-1 hidden sm:block" />
            <div>
              <h1 className="text-lg font-bold leading-none tracking-tight">Interview Report</h1>
              <p className="text-[10px] text-slate-500 mt-1.5 uppercase tracking-widest font-semibold">
                Session ID: {id?.slice(0, 8)} • Completed on {new Date(report.generated_at).toLocaleDateString()}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <a href={report.pdf_url} target="_blank" rel="noopener noreferrer">
              <Button className="bg-white text-black hover:bg-slate-200 gap-2 font-bold px-5">
                <Download className="w-4 h-4" />
                Download PDF
              </Button>
            </a>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 pt-10 grid grid-cols-1 lg:grid-cols-12 gap-10">
        
        {/* Left Column: Summary & Scores */}
        <div className="lg:col-span-4 space-y-8">
          
          {/* Global Score Card */}
          <div className="bg-slate-900/40 border border-white/5 rounded-[2rem] p-8 flex flex-col items-center text-center relative overflow-hidden group">
            <div className="absolute inset-0 bg-gradient-to-br from-indigo-600/5 to-purple-600/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
            <Award className="w-12 h-12 text-indigo-400 mb-6 relative z-10" />
            <h3 className="text-slate-500 uppercase tracking-[0.2em] text-[10px] font-black mb-2 relative z-10">Performance Score</h3>
            <div className="relative z-10 flex items-baseline">
               <span className="text-8xl font-black tracking-tighter text-white">
                {report.global_score}
              </span>
              <span className="text-2xl text-slate-600 font-bold ml-2">/10</span>
            </div>
            <div className="mt-8 w-full h-2.5 bg-slate-800/50 rounded-full overflow-hidden relative z-10">
              <div 
                className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 rounded-full shadow-[0_0_15px_rgba(99,102,241,0.5)] transition-all duration-1000 ease-out"
                style={{ width: `${report.global_score * 10}%` }}
              />
            </div>
            <p className="mt-6 text-xs text-slate-400 leading-relaxed font-medium">
              Overall competency match based on technical accuracy, depth of explanation, and communication clarity.
            </p>
          </div>

          {/* Competency Breakdown */}
          <div className="bg-slate-900/40 border border-white/5 rounded-[2rem] p-8">
            <h3 className="text-xs font-black uppercase tracking-[0.15em] text-slate-400 mb-8 flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-emerald-400" />
              Competency Breakdown
            </h3>
            <div className="space-y-8">
              {Object.entries(report.competency_breakdown).map(([domain, data]) => (
                <div key={domain} className="group">
                  <div className="flex justify-between items-end mb-2.5">
                    <span className="text-sm font-bold text-slate-300 group-hover:text-white transition-colors">{domain}</span>
                    <span className={`text-xs font-black px-2 py-0.5 rounded ${
                      data.score >= 7 ? 'bg-emerald-500/10 text-emerald-400' : 
                      data.score >= 4 ? 'bg-amber-500/10 text-amber-400' : 'bg-red-500/10 text-red-400'
                    }`}>
                      {data.score}/10
                    </span>
                  </div>
                  <div className="h-2 bg-slate-800/50 rounded-full overflow-hidden">
                    <div 
                      className={`h-full rounded-full transition-all duration-1000 ease-out ${
                        data.score >= 7 ? 'bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.3)]' : 
                        data.score >= 4 ? 'bg-amber-500 shadow-[0_0_10px_rgba(245,158,11,0.3)]' : 'bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.3)]'
                      }`}
                      style={{ width: `${data.score * 10}%` }}
                    />
                  </div>
                  <p className="mt-2.5 text-[11px] text-slate-500 leading-relaxed italic line-clamp-2">
                    {data.feedback}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Narrative & Action Plan */}
        <div className="lg:col-span-8 space-y-10">
          
          {/* Action Plan */}
          <div className="bg-indigo-600/5 border border-indigo-500/20 rounded-[2.5rem] p-10 relative overflow-hidden">
            <div className="absolute top-0 right-0 p-10 opacity-5">
              <Zap className="w-40 h-40 text-indigo-400" />
            </div>
            <h3 className="text-2xl font-black mb-10 text-indigo-100 tracking-tight relative z-10 flex items-center gap-3">
              Actionable Growth Roadmap
              <span className="text-[10px] bg-indigo-500 text-white px-2 py-1 rounded-full uppercase tracking-tighter">AI Curated</span>
            </h3>
            <div className="space-y-10 relative z-10">
              {report.action_plan.map((step, index) => (
                <div key={index} className="flex gap-6 group">
                  <div className="flex flex-col items-center gap-2">
                    <div className="w-10 h-10 shrink-0 rounded-2xl bg-indigo-500 text-white flex items-center justify-center font-black text-sm shadow-lg shadow-indigo-500/20 group-hover:scale-110 transition-transform">
                      {index + 1}
                    </div>
                    {index < report.action_plan.length - 1 && (
                      <div className="w-[2px] h-full bg-gradient-to-b from-indigo-500/30 to-transparent" />
                    )}
                  </div>
                  <div className="pb-4">
                    <h4 className="text-lg font-bold text-white mb-2 group-hover:text-indigo-300 transition-colors">{step.step}</h4>
                    <p className="text-slate-400 mb-4 leading-relaxed text-sm">{step.resources}</p>
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-1.5 text-[10px] font-black uppercase tracking-widest text-indigo-400 bg-indigo-400/5 border border-indigo-400/10 px-3 py-1.5 rounded-full">
                        ⏱ {step.timeframe}
                      </div>
                      <button className="text-[10px] font-black uppercase tracking-widest text-slate-500 hover:text-white transition-colors flex items-center gap-1">
                        Resource link <ExternalLink className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Highlights & Lowlights */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-emerald-500/[0.03] border border-emerald-500/10 rounded-3xl p-8 hover:bg-emerald-500/[0.05] transition-colors">
              <div className="w-10 h-10 rounded-2xl bg-emerald-500/10 flex items-center justify-center mb-6">
                <CheckCircle2 className="w-6 h-6 text-emerald-400" />
              </div>
              <h4 className="text-emerald-400 font-black text-xs uppercase tracking-widest mb-6">Demonstrated Strengths</h4>
              <ul className="space-y-4">
                {Object.entries(report.competency_breakdown)
                  .filter(([_, data]) => data.score >= 7)
                  .map(([domain]) => (
                    <li key={domain} className="text-sm text-slate-300 flex items-start gap-3">
                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-2 shrink-0 shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
                      <span>Showcased deep conceptual understanding of <strong>{domain}</strong>.</span>
                    </li>
                  ))
                }
                {Object.entries(report.competency_breakdown).filter(([_, data]) => data.score >= 7).length === 0 && (
                  <li className="text-xs text-slate-500 italic">No high-level strengths detected in this session.</li>
                )}
              </ul>
            </div>
            
            <div className="bg-amber-500/[0.03] border border-amber-500/10 rounded-3xl p-8 hover:bg-amber-500/[0.05] transition-colors">
              <div className="w-10 h-10 rounded-2xl bg-amber-500/10 flex items-center justify-center mb-6">
                <TrendingUp className="w-6 h-6 text-amber-400" />
              </div>
              <h4 className="text-amber-400 font-black text-xs uppercase tracking-widest mb-6">Focus for growth</h4>
              <ul className="space-y-4">
                {Object.entries(report.competency_breakdown)
                  .filter(([_, data]) => data.score < 6)
                  .map(([domain]) => (
                    <li key={domain} className="text-sm text-slate-300 flex items-start gap-3">
                      <div className="w-1.5 h-1.5 rounded-full bg-amber-500 mt-2 shrink-0 shadow-[0_0_8px_rgba(245,158,11,0.5)]" />
                      <span>Opportunity to refine practical application in <strong>{domain}</strong>.</span>
                    </li>
                  ))
                }
                {Object.entries(report.competency_breakdown).filter(([_, data]) => data.score < 6).length === 0 && (
                  <li className="text-xs text-slate-500 italic">No significant growth areas detected. Great consistency!</li>
                )}
              </ul>
            </div>
          </div>

          {/* Footer CTA */}
          <div className="bg-slate-900/20 border border-white/5 rounded-3xl p-8 text-center">
            <p className="text-slate-500 text-sm mb-6 max-w-lg mx-auto">
              Ready to put this feedback into practice? Start a new session focusing on your growth areas to track your progress.
            </p>
            <Button 
              onClick={() => router.push('/session/new')}
              className="bg-indigo-600/20 text-indigo-400 border border-indigo-600/30 hover:bg-indigo-600/30 transition-all font-bold px-8 rounded-2xl"
            >
              Start New Session
            </Button>
          </div>

        </div>
      </main>
    </div>
  );
}
