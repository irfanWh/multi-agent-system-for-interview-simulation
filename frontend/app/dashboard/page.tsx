"use client";

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { 
  Play, 
  BarChart3, 
  Clock, 
  Award, 
  Briefcase, 
  Activity,
  ArrowRight,
  TrendingUp,
  Target,
  Zap,
  AlertCircle
} from 'lucide-react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  RadialLinearScale,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';
import { Line, Radar } from 'react-chartjs-2';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  RadialLinearScale,
  Title,
  Tooltip,
  Legend,
  Filler
);

interface Session {
  id: string;
  interview_type: string;
  job_description: string | null;
  status: string;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
}

interface ScoreEvolution {
  date: string;
  score: number;
}

interface StrengthsProfile {
  category: string;
  average_score: number;
  percentage: number;
  level: 'strong' | 'medium' | 'weak';
  interviews_used: number;
  feedback_summary?: string | null;
}

interface DashboardStats {
  total_interviews: number;
  completed_interviews: number;
  active_interviews: number;
  active_resumes: number;
  average_score: number | null;
  best_score: number | null;
  score_evolution: ScoreEvolution[];
  strengths_profile: StrengthsProfile[];
}

export default function DashboardPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  
  const [sessions, setSessions] = useState<Session[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [statsError, setStatsError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/');
    }
  }, [user, authLoading, router]);

  useEffect(() => {
    if (user) {
      fetchData();
    }
  }, [user]);

  const fetchData = async () => {
    try {
      setLoading(true);
      setStatsError(null);

      const [sessionsResult, statsResult] = await Promise.allSettled([
        api.get('/sessions/'),
        api.getDashboardStats()
      ]);

      if (sessionsResult.status === 'fulfilled') {
        const sessionData = Array.isArray(sessionsResult.value.data)
          ? sessionsResult.value.data
          : (sessionsResult.value.data.items || []);

        const sorted = [...sessionData].sort((a, b) => {
          const dateA = new Date(a.started_at || a.created_at).getTime();
          const dateB = new Date(b.started_at || b.created_at).getTime();
          return dateB - dateA;
        });

        setSessions(sorted);
      }

      if (statsResult.status === 'fulfilled') {
        setStats(statsResult.value.data);
      } else {
        setStatsError("Could not load strengths profile.");
      }
    } catch (err) {
      console.error("Failed to fetch dashboard data", err);
      setStatsError("Could not load strengths profile.");
    } finally {
      setLoading(false);
    }
  };

  if (authLoading || loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  const userName = user?.email?.split('@')[0] || 'Guest';
  
  // Prepare data for Line Chart (Score Evolution)
  const lineChartData = {
    labels: stats?.score_evolution?.map(e => e.date) || [],
    datasets: [
      {
        label: 'Global Score',
        data: stats?.score_evolution?.map(e => e.score) || [],
        borderColor: '#818cf8', // indigo-400
        backgroundColor: 'rgba(99, 102, 241, 0.1)', // indigo-500 w/ opacity
        borderWidth: 2,
        tension: 0.4,
        fill: true,
        pointBackgroundColor: '#6366f1',
        pointBorderColor: '#fff',
        pointHoverBackgroundColor: '#fff',
        pointHoverBorderColor: '#6366f1',
      }
    ]
  };

  const lineChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        mode: 'index' as const,
        intersect: false,
        backgroundColor: 'rgba(15, 23, 42, 0.9)',
        titleColor: '#f1f5f9',
        bodyColor: '#cbd5e1',
        borderColor: 'rgba(255,255,255,0.1)',
        borderWidth: 1,
      },
    },
    scales: {
      y: {
        min: 0,
        max: 10,
        grid: { color: 'rgba(255, 255, 255, 0.05)' },
        ticks: { color: '#94a3b8' }
      },
      x: {
        grid: { display: false },
        ticks: { color: '#94a3b8' }
      }
    }
  };

  // Prepare data for Radar Chart (Strengths)
  const radarChartData = {
    labels: stats?.strengths_profile?.map(s => s.category) || [],
    datasets: [
      {
        label: 'Your Profile',
        data: stats?.strengths_profile?.map(s => s.average_score) || [],
        backgroundColor: 'rgba(168, 85, 247, 0.2)', // purple-500 w/ opacity
        borderColor: '#c084fc', // purple-400
        pointBackgroundColor: '#a855f7',
        pointBorderColor: '#fff',
        pointHoverBackgroundColor: '#fff',
        pointHoverBorderColor: '#a855f7',
      }
    ]
  };

  const radarChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      r: {
        angleLines: { color: 'rgba(255, 255, 255, 0.1)' },
        grid: { color: 'rgba(255, 255, 255, 0.1)' },
        pointLabels: { color: '#cbd5e1', font: { size: 11 } },
        ticks: { display: false, min: 0, max: 10 }
      }
    },
    plugins: {
      legend: { display: false }
    }
  };

  const levelClass = (level: StrengthsProfile['level']) => {
    if (level === 'strong') return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
    if (level === 'medium') return 'text-amber-400 bg-amber-500/10 border-amber-500/20';
    return 'text-red-400 bg-red-500/10 border-red-500/20';
  };

  // Helper to format session date
  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Unknown';
    const d = new Date(dateString);
    return new Intl.DateTimeFormat('en-US', { 
      month: 'short', day: 'numeric', year: 'numeric' 
    }).format(d);
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-slate-100 font-sans pb-20">
      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-50 bg-[#0a0a0f]/80 backdrop-blur-md border-b border-white/5 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/20 flex items-center justify-center border border-indigo-500/30">
              <Zap className="w-4 h-4 text-indigo-400" />
            </div>
            <span className="text-xl font-bold tracking-tight bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
              InterviewAI
            </span>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push('/recruiter')}
              className="text-sm text-indigo-300 hover:text-indigo-200 hidden sm:block"
            >
              Recruiter Mode
            </button>
            <span className="text-sm text-slate-400 hidden sm:block">{user?.email}</span>
            <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center">
              <span className="text-sm font-medium">{userName.charAt(0).toUpperCase()}</span>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8">
        
        {/* Welcome Section & Primary CTA */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-10">
          <div>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight mb-2">
              Welcome back, <span className="text-indigo-400 capitalize">{userName}</span>
            </h1>
            <p className="text-slate-400 text-lg">Track your progress and prepare for your next big role.</p>
          </div>
          <Button 
            onClick={() => router.push('/session/new')}
            className="group relative overflow-hidden bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-bold px-8 py-6 rounded-xl shadow-[0_0_20px_rgba(99,102,241,0.3)] transition-all hover:scale-[1.02] shrink-0"
          >
            <div className="absolute inset-0 bg-white/20 translate-y-full group-hover:translate-y-0 transition-transform duration-300 ease-in-out" />
            <span className="relative flex items-center text-lg">
              <Play className="w-5 h-5 mr-2 fill-current" />
              Launch Interview
            </span>
          </Button>
        </div>

        {/* Quick Stats Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
          <div className="bg-slate-900/50 backdrop-blur-sm border border-white/5 rounded-2xl p-5 hover:bg-slate-800/50 transition-colors">
            <div className="flex items-center justify-between mb-4">
              <span className="text-slate-400 text-sm font-medium">Total Interviews</span>
              <Activity className="w-5 h-5 text-blue-400" />
            </div>
            <div className="text-3xl font-black text-white">{stats?.total_interviews || 0}</div>
          </div>
          
          <div className="bg-slate-900/50 backdrop-blur-sm border border-white/5 rounded-2xl p-5 hover:bg-slate-800/50 transition-colors">
            <div className="flex items-center justify-between mb-4">
              <span className="text-slate-400 text-sm font-medium">Average Score</span>
              <Award className="w-5 h-5 text-emerald-400" />
            </div>
            <div className="text-3xl font-black text-white flex items-baseline">
              {stats?.average_score ? stats.average_score.toFixed(1) : "-"} <span className="text-sm text-slate-500 ml-1">/ 10</span>
            </div>
          </div>
          
          <div className="bg-slate-900/50 backdrop-blur-sm border border-white/5 rounded-2xl p-5 hover:bg-slate-800/50 transition-colors">
            <div className="flex items-center justify-between mb-4">
              <span className="text-slate-400 text-sm font-medium">Best Score</span>
              <TrendingUp className="w-5 h-5 text-purple-400" />
            </div>
            <div className="text-3xl font-black text-white flex items-baseline">
              {stats?.best_score ? stats.best_score.toFixed(1) : "-"} <span className="text-sm text-slate-500 ml-1">/ 10</span>
            </div>
          </div>
          
          <div className="bg-slate-900/50 backdrop-blur-sm border border-white/5 rounded-2xl p-5 hover:bg-slate-800/50 transition-colors">
            <div className="flex items-center justify-between mb-4">
              <span className="text-slate-400 text-sm font-medium">Active Resumes</span>
              <Briefcase className="w-5 h-5 text-amber-400" />
            </div>
            <div className="text-3xl font-black text-white">{stats?.active_resumes || 0}</div>
          </div>
        </div>

        {/* Charts Section */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-10">
          {/* Line Chart */}
          <div className="lg:col-span-2 bg-slate-900/40 border border-white/5 rounded-3xl p-6">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-bold flex items-center">
                <BarChart3 className="w-5 h-5 mr-2 text-indigo-400" /> Score Evolution
              </h3>
            </div>
            <div className="h-[250px] w-full">
              {stats?.score_evolution && stats.score_evolution.length > 0 ? (
                <Line data={lineChartData} options={lineChartOptions} />
              ) : (
                <div className="w-full h-full flex flex-col items-center justify-center text-slate-500">
                  <BarChart3 className="w-8 h-8 mb-2 opacity-50" />
                  <p className="text-sm">Complete interviews to see your evolution</p>
                </div>
              )}
            </div>
          </div>
          
          {/* Radar Chart */}
          <div className="bg-slate-900/40 border border-white/5 rounded-3xl p-6">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-bold flex items-center">
                <Target className="w-5 h-5 mr-2 text-purple-400" /> Strengths Profile
              </h3>
            </div>
            <div className="h-[250px] w-full flex items-center justify-center">
              {statsError ? (
                <div className="w-full h-full flex flex-col items-center justify-center text-red-300">
                  <AlertCircle className="w-8 h-8 mb-2 opacity-70" />
                  <p className="text-sm text-center px-4">{statsError}</p>
                </div>
              ) : stats?.strengths_profile && stats.strengths_profile.length >= 3 ? (
                <Radar data={radarChartData} options={radarChartOptions} />
              ) : stats?.strengths_profile && stats.strengths_profile.length > 0 ? (
                <div className="w-full space-y-4">
                  {stats.strengths_profile.map((strength) => (
                    <div key={strength.category}>
                      <div className="flex items-center justify-between gap-3 mb-2">
                        <span className="text-sm font-semibold text-slate-200 truncate">{strength.category}</span>
                        <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full border ${levelClass(strength.level)}`}>
                          {strength.level}
                        </span>
                      </div>
                      <div className="h-2 bg-slate-800/80 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-purple-400 rounded-full"
                          style={{ width: `${Math.min(strength.percentage, 100)}%` }}
                        />
                      </div>
                      <div className="mt-1 flex justify-between text-[11px] text-slate-500">
                        <span>{strength.average_score.toFixed(1)}/10</span>
                        <span>{strength.interviews_used} interview{strength.interviews_used === 1 ? '' : 's'}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="w-full h-full flex flex-col items-center justify-center text-slate-500">
                  <Target className="w-8 h-8 mb-2 opacity-50" />
                  <p className="text-sm text-center px-4">Complete more interviews to unlock your strengths profile.</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Recent Interviews List */}
        <div>
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold flex items-center">
              <Clock className="w-5 h-5 mr-2 text-slate-400" /> Recent Activity
            </h2>
          </div>
          
          <div className="bg-slate-900/40 border border-white/5 rounded-3xl overflow-hidden">
            {sessions.length === 0 ? (
              <div className="p-12 text-center">
                <div className="w-16 h-16 bg-slate-800 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Briefcase className="w-8 h-8 text-slate-500" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">No interviews yet</h3>
                <p className="text-slate-400 max-w-sm mx-auto mb-6">
                  You haven't completed any interviews. Launch your first session to start tracking your performance.
                </p>
                <Button 
                  onClick={() => router.push('/session/new')}
                  variant="outline"
                  className="border-indigo-500/30 text-indigo-300 hover:bg-indigo-500/10"
                >
                  Start First Interview
                </Button>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-white/5 bg-slate-900/50">
                      <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Date</th>
                      <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Type</th>
                      <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Context</th>
                      <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Status</th>
                      <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {sessions.map((session) => (
                      <tr key={session.id} className="hover:bg-slate-800/30 transition-colors group">
                        <td className="px-6 py-5 whitespace-nowrap">
                          <div className="text-sm font-medium text-slate-200">
                            {formatDate(session.started_at || session.created_at)}
                          </div>
                        </td>
                        <td className="px-6 py-5 whitespace-nowrap">
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize bg-slate-800 text-slate-300 border border-slate-700">
                            {session.interview_type}
                          </span>
                        </td>
                        <td className="px-6 py-5">
                          <div className="text-sm text-slate-400 truncate max-w-xs">
                            {session.job_description 
                              ? (session.job_description.startsWith('Link:') ? 'Web URL Context' : session.job_description) 
                              : 'General Practice'}
                          </div>
                        </td>
                        <td className="px-6 py-5 whitespace-nowrap">
                          {session.status === 'completed' ? (
                            <span className="inline-flex items-center text-xs font-medium text-emerald-400">
                              <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-2" />
                              Completed
                            </span>
                          ) : session.status === 'active' || session.status === 'in_progress' ? (
                            <span className="inline-flex items-center text-xs font-medium text-amber-400">
                              <div className="w-1.5 h-1.5 rounded-full bg-amber-400 mr-2 animate-pulse" />
                              In Progress
                            </span>
                          ) : (
                            <span className="inline-flex items-center text-xs font-medium text-slate-400">
                              <div className="w-1.5 h-1.5 rounded-full bg-slate-400 mr-2" />
                              {session.status}
                            </span>
                          )}
                        </td>
                        <td className="px-6 py-5 whitespace-nowrap text-right">
                          {session.status === 'completed' ? (
                            <Button 
                              onClick={() => router.push(`/session/${session.id}/report`)}
                              variant="outline" 
                              className="text-xs bg-transparent border-indigo-500/30 text-indigo-300 hover:bg-indigo-500/10 group-hover:border-indigo-500/50"
                            >
                              View Report <ArrowRight className="ml-1.5 w-3 h-3" />
                            </Button>
                          ) : (
                            <Button 
                              onClick={() => router.push(`/session/${session.id}`)}
                              className="text-xs bg-indigo-600 hover:bg-indigo-500"
                            >
                              Resume
                            </Button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
