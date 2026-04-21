"use client";

import React from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer 
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';

export interface MatchReportData {
  global_match_score: number;
  skills_matched: { skill: string; level_in_cv: string; level_required: string }[];
  skills_missing: { skill: string; importance: string; learn_time_weeks: number }[];
  skills_exceeded: string[];
  domain_scores: { domain: string; score: number; matched: number; total: number }[];
  experience_match: { score: number; candidate_years: number; required_years: number; verdict: string };
  soft_skills_match: { score: number; found: string[]; missing: string[] };
  interview_focus_areas: string[];
  recommendation: string;
  readiness_level: string;
}

interface MatchDashboardProps {
  report: MatchReportData;
  onStartInterview: (focusAreas: string[]) => void;
  loading?: boolean;
}

export function MatchDashboard({ report, onStartInterview, loading }: MatchDashboardProps) {
  
  const getScoreColor = (score: number) => {
    if (score >= 75) return 'text-green-600';
    if (score >= 50) return 'text-amber-500';
    return 'text-red-600';
  };

  const getScoreBg = (score: number) => {
    if (score >= 75) return 'bg-green-100 text-green-800';
    if (score >= 50) return 'bg-amber-100 text-amber-800';
    return 'bg-red-100 text-red-800';
  };

  const readinessLabels: Record<string, string> = {
    strong_match: "Strong Match 🔥",
    good_match: "Good Match ✅",
    partial_match: "Partial Match ⚠️",
    weak_match: "Weak Match ❌"
  };

  // Format data for Recharts
  const chartData = report.domain_scores.map(d => ({
    name: d.domain,
    "Candidate Score": d.score,
    "Target/Required": 100 // Visual baseline
  }));

  return (
    <div className="space-y-6 animate-in fade-in zoom-in duration-500">
      {/* 1. HEADER ROW */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6 text-center">
            <div className={`text-4xl font-bold ${getScoreColor(report.global_match_score)}`}>
              {report.global_match_score}%
            </div>
            <div className="mt-2 text-sm text-slate-500 font-medium">Global Match</div>
            <div className={`mt-2 inline-flex px-2 py-1 rounded-full text-xs font-semibold ${getScoreBg(report.global_match_score)}`}>
              {readinessLabels[report.readiness_level] || report.readiness_level}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6 text-center">
            <div className="text-4xl font-bold text-slate-800">
              {report.skills_matched.length}
            </div>
            <div className="mt-2 text-sm text-slate-500 font-medium">Skills Matched</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6 text-center">
            <div className="text-4xl font-bold text-slate-800">
              {report.skills_missing.length}
            </div>
            <div className="mt-2 text-sm text-slate-500 font-medium">Skills Missing</div>
            <div className="mt-2 text-xs text-red-500 font-medium">
              {report.skills_missing.filter(s => s.importance === 'critical').length} Critical
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6 text-center">
            <div className="text-4xl font-bold text-slate-800">
              {report.experience_match.candidate_years} / {report.experience_match.required_years}
            </div>
            <div className="mt-2 text-sm text-slate-500 font-medium">Years Experience</div>
            <div className="mt-2 text-xs text-slate-400 truncate" title={report.experience_match.verdict}>
              {report.experience_match.verdict}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 2. SKILLS CHART */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Domain Performance Profile</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart layout="vertical" data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" domain={[0, 100]} />
                <YAxis dataKey="name" type="category" width={100} />
                <Tooltip />
                <Legend />
                <Bar dataKey="Candidate Score" fill="#10b981" radius={[0, 4, 4, 0]} />
                <Bar dataKey="Target/Required" fill="#e2e8f0" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* 3. TWO COLUMNS */}
      <div className="grid md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">✅ Skills You Have</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {report.skills_matched.length === 0 && <p className="text-sm text-slate-500">None detected.</p>}
            {report.skills_matched.map((s, i) => (
              <div key={i} className="flex justify-between items-center p-2 rounded-md bg-green-50 border border-green-100">
                <span className="font-medium text-green-800 text-sm">{s.skill}</span>
                <span className="text-xs text-green-600 bg-green-100 px-2 py-1 rounded-full">
                  You: {s.level_in_cv} / Req: {s.level_required}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">⚠️ Skills to Work On</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {report.skills_missing.length === 0 && <p className="text-sm text-slate-500">None missing!</p>}
            {report.skills_missing.map((s, i) => (
              <div key={i} className={`flex justify-between items-center p-2 rounded-md border ${s.importance === 'critical' ? 'bg-red-50 border-red-100' : 'bg-amber-50 border-amber-100'}`}>
                <div className="flex items-center gap-2">
                  {s.importance === 'critical' && <span title="Critical">🔒</span>}
                  <span className={`font-medium text-sm ${s.importance === 'critical' ? 'text-red-800' : 'text-amber-800'}`}>
                    {s.skill}
                  </span>
                </div>
                <span className={`text-xs px-2 py-1 rounded-full ${s.importance === 'critical' ? 'text-red-600 bg-red-100' : 'text-amber-600 bg-amber-100'}`}>
                  ~{s.learn_time_weeks} weeks
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* 4. SOFT SKILLS */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Soft Skills Harmony</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {report.soft_skills_match.found.map((ss, i) => (
              <span key={`f-${i}`} className="px-3 py-1 bg-teal-100 text-teal-800 text-sm rounded-full font-medium shadow-sm">
                {ss}
              </span>
            ))}
            {report.soft_skills_match.missing.map((ss, i) => (
              <span key={`m-${i}`} className="px-3 py-1 bg-slate-100 text-slate-500 text-sm rounded-full border border-dashed border-slate-300">
                {ss} (missing)
              </span>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* 5. INTERVIEW FOCUS & CTA */}
      <Card className="bg-slate-900 border-none text-white shadow-xl overflow-hidden relative">
        <div className="absolute top-0 right-0 p-8 opacity-10 blur-xl w-64 h-64 bg-blue-500 rounded-full mix-blend-screen pointer-events-none"></div>
        <CardHeader>
          <CardTitle className="text-xl">Next: Targeted Interview 🎯</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6 relative z-10">
          <p className="text-slate-300 italic">
            "{report.recommendation}"
          </p>
          
          <div>
            <h4 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">Focus Areas Selected for Interview:</h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {report.interview_focus_areas.map((focus, i) => (
                <div key={i} className="bg-slate-800 border border-slate-700 rounded-md p-3 text-sm text-blue-200">
                  {i + 1}. {focus}
                </div>
              ))}
            </div>
          </div>

          <Button 
            onClick={() => onStartInterview(report.interview_focus_areas)} 
            isLoading={loading}
            className="w-full text-lg py-6 bg-blue-600 hover:bg-blue-500 text-white shadow-lg transition-transform hover:scale-[1.01]"
          >
            Start Interview (Focused on Gaps) 🚀
          </Button>
        </CardContent>
      </Card>
      
    </div>
  );
}
