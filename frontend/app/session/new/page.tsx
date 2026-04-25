'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { Loader2, FileText, CheckCircle, Clock, Upload, ArrowRight, AlertCircle, RefreshCw, Zap, Briefcase, BrainCircuit, Link as LinkIcon, BarChart3, AlertTriangle, Trash2, X } from 'lucide-react';
import DurationPicker from '@/components/DurationPicker';

interface Resume {
  id: string;
  filename: string;
  created_at: string;
  is_analyzed: boolean;
  sessions_count: number;
}

export default function NewSessionPage() {
  const router = useRouter();
  
  // Stepper state
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Step 1 state
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [selectedResumeId, setSelectedResumeId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<Resume | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [pollingId, setPollingId] = useState<string | null>(null);

  // Step 2 state
  const [inputType, setInputType] = useState<'text' | 'url'>('text');
  const [jobDescription, setJobDescription] = useState('');
  const [jobUrl, setJobUrl] = useState('');
  const [matchReport, setMatchReport] = useState<any>(null);
  const [analyzingMatch, setAnalyzingMatch] = useState(false);
  const [wasCached, setWasCached] = useState(false);

  // Step 3 state
  const [interviewType, setInterviewType] = useState('technical');
  const [duration, setDuration] = useState(30);

  useEffect(() => {
    fetchResumes();
  }, []);

  useEffect(() => {
    if (!pollingId) return;

    let attempts = 0;
    const MAX_ATTEMPTS = 90; // 90 × 2s = 3 minutes max

    const interval = setInterval(async () => {
      attempts++;
      try {
        const res = await api.get(`/resumes/${pollingId}/status`);
        if (res.data.is_analyzed) {
          clearInterval(interval);
          setPollingId(null);
          fetchResumes();
          return;
        }
      } catch (err) {
        console.error('Failed to poll status', err);
      }

      // Safety valve: stop after MAX_ATTEMPTS
      if (attempts >= MAX_ATTEMPTS) {
        clearInterval(interval);
        setPollingId(null);
        setError('Profile analysis is taking too long. Please try refreshing the page.');
        fetchResumes(); // reload so user sees the current state
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [pollingId]);

  const handleDeleteResume = async (resume: Resume) => {
    setDeletingId(resume.id);
    setConfirmDelete(null);
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'}/resumes/${resume.id}`, {
        method: 'DELETE',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error('Delete failed');
      if (selectedResumeId === resume.id) setSelectedResumeId(null);
      await fetchResumes();
    } catch (err: any) {
      setError('Failed to delete resume');
    } finally {
      setDeletingId(null);
    }
  };

  const fetchResumes = async () => {
    try {
      const res = await api.get('/resumes');
      setResumes(res.data);
    } catch (err) {
      setError('Failed to fetch resumes');
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    
    const file = e.target.files[0];
    const formData = new FormData();
    formData.append('file', file);
    
    setUploading(true);
    setError(null);
    try {
      const res = await api.post('/resumes/upload', formData);
      
      const { resume_id, is_analyzed, was_duplicate } = res.data;
      
      if (was_duplicate) {
        alert('This exact resume was already uploaded. Selecting it now.');
        setSelectedResumeId(resume_id);
      } else {
        setSelectedResumeId(resume_id);
        if (!is_analyzed) {
          setPollingId(resume_id);
        }
      }
      fetchResumes();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      const errorMsg = Array.isArray(detail) ? detail[0]?.msg : detail;
      setError(errorMsg || 'Failed to upload resume');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleAnalyzeMatch = async () => {
    const jdContent = inputType === 'url' ? `Link: ${jobUrl}` : jobDescription;
    if (!selectedResumeId || !jdContent) return;
    setAnalyzingMatch(true);
    setError(null);
    try {
      const res = await api.post(`/resumes/${selectedResumeId}/match-analysis`, {
        job_description: jdContent
      });
      setMatchReport(res.data.match_report);
      setWasCached(res.data.was_cached);
      // We don't auto-skip anymore, user must click Continue
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      const errorMsg = Array.isArray(detail) ? detail[0]?.msg : detail;
      setError(errorMsg || 'Match analysis failed');
    } finally {
      setAnalyzingMatch(false);
    }
  };

  const handleStartSession = async () => {
    if (!selectedResumeId) return;
    setLoading(true);
    setError(null);
    const jdContent = inputType === 'url' ? `Link: ${jobUrl}` : jobDescription;
    
    try {
      // Note: We use query params directly in the URL for duration_minutes
      const res = await api.post(`/sessions/?duration_minutes=${duration}`, {
        resume_id: selectedResumeId,
        job_description: jdContent || undefined,
        interview_type: interviewType,
      });
      
      router.push(`/session/${res.data.id}`);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      const errorMsg = Array.isArray(detail) ? detail[0]?.msg : detail;
      setError(errorMsg || 'Failed to start session');
      setLoading(false);
    }
  };

  const isSelectedResumeReady = () => {
    const resume = resumes.find(r => r.id === selectedResumeId);
    return resume && resume.is_analyzed;
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-slate-100 flex items-center justify-center p-4 md:p-8 relative overflow-hidden font-sans">
      
      {/* Dynamic Background Elements */}
      <div className="absolute top-[-10%] left-[-10%] w-[500px] h-[500px] rounded-full bg-indigo-600/20 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[600px] h-[600px] rounded-full bg-fuchsia-600/10 blur-[150px] pointer-events-none" />
      <div className="absolute top-[40%] right-[20%] w-[300px] h-[300px] rounded-full bg-blue-500/10 blur-[100px] pointer-events-none" />

      <div className="container max-w-4xl w-full relative z-10">
        
        {/* Header */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center justify-center p-3 bg-indigo-500/10 rounded-2xl mb-4 border border-indigo-500/20 backdrop-blur-md">
            <BrainCircuit className="text-indigo-400 h-8 w-8" />
          </div>
          <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight bg-gradient-to-br from-white via-slate-200 to-indigo-300 bg-clip-text text-transparent">
            Launch Your Interview
          </h1>
          <p className="mt-3 text-slate-400 text-lg">AI-powered simulation tailored to your unique profile.</p>
        </div>
        
        {/* Modern Stepper */}
        <div className="flex justify-center items-center mb-12 max-w-2xl mx-auto px-4">
          <div className={`flex flex-col items-center transition-all duration-300 \${step === 1 ? 'text-indigo-400 scale-110' : step > 1 ? 'text-emerald-400' : 'text-slate-600'}`}>
            <div className={`w-10 h-10 rounded-full flex items-center justify-center mb-2 shadow-lg transition-all duration-300 \${step === 1 ? 'bg-indigo-500 text-white shadow-indigo-500/30' : step > 1 ? 'bg-emerald-500 text-white shadow-emerald-500/30' : 'bg-slate-800/50 border border-slate-700'}`}>
              {step > 1 ? <CheckCircle size={20} /> : '1'}
            </div>
            <span className="text-xs font-semibold uppercase tracking-wider">Profile</span>
          </div>
          <div className={`flex-1 h-[2px] mx-4 transition-all duration-500 \${step > 1 ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-slate-800'}`} />
          
          <div className={`flex flex-col items-center transition-all duration-300 \${step === 2 ? 'text-indigo-400 scale-110' : step > 2 ? 'text-emerald-400' : 'text-slate-600'}`}>
            <div className={`w-10 h-10 rounded-full flex items-center justify-center mb-2 shadow-lg transition-all duration-300 \${step === 2 ? 'bg-indigo-500 text-white shadow-indigo-500/30' : step > 2 ? 'bg-emerald-500 text-white shadow-emerald-500/30' : 'bg-slate-800/50 border border-slate-700'}`}>
              {step > 2 ? <CheckCircle size={20} /> : '2'}
            </div>
            <span className="text-xs font-semibold uppercase tracking-wider">Target</span>
          </div>
          <div className={`flex-1 h-[2px] mx-4 transition-all duration-500 \${step > 2 ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-slate-800'}`} />
          
          <div className={`flex flex-col items-center transition-all duration-300 \${step === 3 ? 'text-indigo-400 scale-110' : 'text-slate-600'}`}>
            <div className={`w-10 h-10 rounded-full flex items-center justify-center mb-2 shadow-lg transition-all duration-300 \${step === 3 ? 'bg-indigo-500 text-white shadow-indigo-500/30' : 'bg-slate-800/50 border border-slate-700'}`}>3</div>
            <span className="text-xs font-semibold uppercase tracking-wider">Setup</span>
          </div>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-xl flex items-center mb-8 backdrop-blur-md shadow-lg animate-in slide-in-from-top-4">
            <AlertCircle className="mr-3 h-5 w-5 flex-shrink-0" />
            <span className="font-medium">{error}</span>
          </div>
        )}

        {/* Main Glass Card */}
        <div className="bg-slate-900/40 backdrop-blur-xl border border-white/10 rounded-3xl overflow-hidden shadow-2xl transition-all duration-500">
          
          {/* STEP 1: RESUME */}
          {step === 1 && (
            <div className="animate-in fade-in slide-in-from-bottom-8 duration-500">
              <div className="p-8 border-b border-white/5 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <h2 className="text-2xl font-bold text-white flex items-center">
                    <FileText className="mr-3 text-indigo-400" /> Select Your Resume
                  </h2>
                  <p className="text-slate-400 mt-1">Choose an existing profile or upload a new document.</p>
                </div>
                <div className="relative">
                  <input type="file" ref={fileInputRef} onChange={handleFileUpload} className="hidden" accept=".pdf,.docx,.txt" />
                  <button 
                    onClick={() => fileInputRef.current?.click()} 
                    disabled={uploading}
                    className="flex items-center justify-center px-5 py-2.5 bg-indigo-500 hover:bg-indigo-400 text-white font-medium rounded-xl transition-colors shadow-[0_0_15px_rgba(99,102,241,0.3)] disabled:opacity-50"
                  >
                    {uploading ? <Loader2 className="mr-2 h-5 w-5 animate-spin" /> : <Upload className="mr-2 h-5 w-5" />}
                    Upload New
                  </button>
                </div>
              </div>
              
              <div className="p-8">
                {resumes.length === 0 && !uploading && (
                  <div className="text-center py-16 px-4 bg-white/5 border border-white/10 border-dashed rounded-2xl flex flex-col items-center">
                    <div className="p-4 bg-indigo-500/10 rounded-full mb-4">
                      <FileText className="h-10 w-10 text-indigo-400" />
                    </div>
                    <h3 className="text-xl font-semibold mb-2">No resumes found</h3>
                    <p className="text-slate-400 mb-6 max-w-md">Upload your CV to let our AI extract your skills and experiences for a personalized interview.</p>
                    <button onClick={() => fileInputRef.current?.click()} className="text-indigo-400 font-medium hover:text-indigo-300 transition-colors">
                      Browse Files
                    </button>
                  </div>
                )}
                
                <div className="grid gap-4 md:grid-cols-2">
                  {resumes.map(resume => (
                    <div 
                      key={resume.id} 
                      className={`group relative p-5 rounded-2xl border transition-all duration-300 cursor-pointer overflow-hidden \${selectedResumeId === resume.id ? 'bg-indigo-500/10 border-indigo-500/50 shadow-[0_0_20px_rgba(99,102,241,0.15)]' : 'bg-white/5 border-white/5 hover:border-indigo-500/30 hover:bg-white/10'}`}
                      onClick={() => setSelectedResumeId(resume.id)}
                    >
                      {/* Delete button — top-right, visible on hover */}
                      <button
                        onClick={(e) => { e.stopPropagation(); setConfirmDelete(resume); }}
                        disabled={deletingId === resume.id}
                        className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity duration-200 p-1.5 rounded-lg bg-red-500/20 hover:bg-red-500/40 text-red-400 hover:text-red-300 border border-red-500/20 z-10"
                        title="Delete resume"
                      >
                        {deletingId === resume.id ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                      </button>
                      {/* Active indicator bar */}
                      {selectedResumeId === resume.id && (
                        <div className="absolute left-0 top-0 bottom-0 w-1 bg-indigo-500 rounded-l-2xl" />
                      )}
                      
                      <div className="flex items-start">
                        <div className={`p-3 rounded-xl mr-4 transition-colors \${selectedResumeId === resume.id ? 'bg-indigo-500/20 text-indigo-400' : 'bg-white/10 text-slate-400 group-hover:text-indigo-300'}`}>
                          <FileText size={24} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <h3 className={`font-semibold text-lg truncate transition-colors \${selectedResumeId === resume.id ? 'text-white' : 'text-slate-200'}`}>
                            {resume.filename}
                          </h3>
                          <div className="flex flex-col space-y-1 mt-2">
                            <span className="text-xs text-slate-500">Uploaded {new Date(resume.created_at).toLocaleDateString()}</span>
                            <span className="text-xs text-slate-500 flex items-center"><RefreshCw size={12} className="mr-1" /> Used in {resume.sessions_count} sessions</span>
                          </div>
                        </div>
                      </div>
                      
                      <div className="mt-4 pt-4 border-t border-white/10 flex items-center justify-between">
                        {resume.is_analyzed ? (
                          <span className="flex items-center text-emerald-400 text-sm font-medium">
                            <CheckCircle size={16} className="mr-1.5" /> Ready for Interview
                          </span>
                        ) : (
                          <span className="flex items-center text-amber-400 text-sm font-medium">
                            <Loader2 size={16} className="mr-1.5 animate-spin" /> Analyzing Profile...
                          </span>
                        )}
                        
                        <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center transition-colors \${selectedResumeId === resume.id ? 'border-indigo-500 bg-indigo-500' : 'border-slate-600'}`}>
                          {selectedResumeId === resume.id && <div className="w-2 h-2 bg-white rounded-full" />}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              
              <div className="p-6 border-t border-white/5 flex items-center justify-end bg-black/20">
                <button 
                  onClick={() => setStep(2)} 
                  disabled={!selectedResumeId || !isSelectedResumeReady()}
                  className="flex items-center justify-center px-8 py-3 bg-gradient-to-r from-indigo-500 to-purple-500 hover:from-indigo-400 hover:to-purple-400 text-white font-medium rounded-xl transition-all shadow-[0_0_20px_rgba(99,102,241,0.4)] disabled:opacity-50 disabled:shadow-none"
                >
                  Continue to Job Match <ArrowRight className="ml-2 h-5 w-5" />
                </button>
              </div>
            </div>
          )}

          {/* STEP 2: JOB DESCRIPTION */}
          {step === 2 && (
            <div className="animate-in fade-in slide-in-from-right-8 duration-500">
              <div className="p-8 border-b border-white/5">
                <h2 className="text-2xl font-bold text-white flex items-center">
                  <Briefcase className="mr-3 text-indigo-400" /> Target Job Description
                </h2>
                <p className="text-slate-400 mt-1">Provide a job description to tailor the interview questions and receive an instant match analysis.</p>
              </div>
              
              <div className="p-8">
                {/* Tabs for Link vs Text */}
                <div className="flex space-x-2 mb-6 bg-slate-800/50 p-1.5 rounded-xl border border-white/5 w-fit">
                  <button 
                    onClick={() => setInputType('text')}
                    className={`px-4 py-2 rounded-lg font-medium text-sm transition-all \${inputType === 'text' ? 'bg-indigo-500 text-white shadow-md' : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'}`}
                  >
                    <FileText className="inline-block mr-2 w-4 h-4" /> Paste Text
                  </button>
                  <button 
                    onClick={() => setInputType('url')}
                    className={`px-4 py-2 rounded-lg font-medium text-sm transition-all \${inputType === 'url' ? 'bg-indigo-500 text-white shadow-md' : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'}`}
                  >
                    <LinkIcon className="inline-block mr-2 w-4 h-4" /> Provide URL
                  </button>
                </div>

                <div className="relative group">
                  <div className="absolute -inset-0.5 bg-gradient-to-r from-indigo-500 to-purple-500 rounded-2xl blur opacity-20 group-focus-within:opacity-50 transition duration-500"></div>
                  
                  {inputType === 'text' ? (
                    <textarea 
                      placeholder="E.g. We are looking for a Senior React Developer with 5+ years of experience..." 
                      value={jobDescription}
                      onChange={e => setJobDescription(e.target.value)}
                      className="relative w-full min-h-[200px] bg-slate-900/80 border border-white/10 rounded-2xl p-6 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-indigo-500/50 resize-y text-base transition-colors"
                    />
                  ) : (
                    <div className="relative bg-slate-900/80 border border-white/10 rounded-2xl p-6">
                      <label className="block text-sm font-medium text-slate-400 mb-2">Job Posting URL</label>
                      <div className="flex items-center">
                        <LinkIcon className="absolute left-9 text-slate-500 w-5 h-5" />
                        <input 
                          type="url"
                          placeholder="https://linkedin.com/jobs/..." 
                          value={jobUrl}
                          onChange={e => setJobUrl(e.target.value)}
                          className="w-full bg-slate-800/50 border border-white/10 rounded-xl py-3 pl-12 pr-4 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-indigo-500/50 transition-colors"
                        />
                      </div>
                      <p className="mt-3 text-xs text-slate-500 italic">We will use this link to extract the context for the interview.</p>
                    </div>
                  )}
                </div>
                
                {matchReport && (
                  <div className="mt-8 p-6 rounded-3xl bg-slate-800/40 border border-white/10 shadow-2xl animate-in fade-in slide-in-from-bottom-8 duration-700 relative overflow-hidden backdrop-blur-xl">
                    {/* Glowing background blob */}
                    <div className={`absolute top-[-50px] right-[-50px] w-48 h-48 rounded-full blur-[80px] opacity-20 pointer-events-none \${matchReport.global_match_score >= 80 ? 'bg-emerald-500' : matchReport.global_match_score >= 50 ? 'bg-amber-500' : 'bg-red-500'}`} />
                    
                    <div className="flex items-center justify-between mb-8 pb-4 border-b border-white/5 relative z-10">
                      <div className="flex items-center text-white font-bold text-2xl">
                        <BarChart3 className="mr-3 h-7 w-7 text-indigo-400" /> Match Analysis Report
                      </div>
                      {wasCached && (
                        <span className="flex items-center text-xs font-bold uppercase tracking-wider bg-indigo-500/20 text-indigo-300 px-3 py-1.5 rounded-full border border-indigo-500/30">
                          <Zap size={14} className="mr-1.5" /> Instant Cached Result
                        </span>
                      )}
                    </div>
                    
                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 relative z-10">
                      
                      {/* Left Column: Score & Summary */}
                      <div className="lg:col-span-4 flex flex-col items-center justify-center p-6 bg-slate-900/50 rounded-2xl border border-white/5">
                        <div className="relative">
                          {/* Circular Score */}
                          <svg className="w-40 h-40 transform -rotate-90">
                            <circle cx="80" cy="80" r="70" className="stroke-slate-800" strokeWidth="12" fill="none" />
                            <circle 
                              cx="80" cy="80" r="70" 
                              className={`\${matchReport.global_match_score >= 80 ? 'stroke-emerald-500' : matchReport.global_match_score >= 50 ? 'stroke-amber-500' : 'stroke-red-500'} transition-all duration-1000 ease-out`} 
                              strokeWidth="12" fill="none" 
                              strokeDasharray="439.8" 
                              strokeDashoffset={439.8 - (439.8 * matchReport.global_match_score) / 100} 
                              strokeLinecap="round" 
                            />
                          </svg>
                          <div className="absolute inset-0 flex flex-col items-center justify-center">
                            <span className="text-4xl font-black text-white">{Math.round(matchReport.global_match_score)}%</span>
                          </div>
                        </div>
                        <span className="mt-4 text-sm font-bold uppercase tracking-widest text-slate-400">Overall Match</span>
                        
                        <div className="mt-6 w-full text-center">
                          <span className={`inline-block px-4 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider border \${
                            matchReport.readiness_level === 'strong_match' ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' :
                            matchReport.readiness_level === 'good_match' ? 'bg-blue-500/20 text-blue-400 border-blue-500/30' :
                            matchReport.readiness_level === 'partial_match' ? 'bg-amber-500/20 text-amber-400 border-amber-500/30' :
                            'bg-red-500/20 text-red-400 border-red-500/30'
                          }`}>
                            {matchReport.readiness_level ? matchReport.readiness_level.replace('_', ' ') : 'Match Result'}
                          </span>
                        </div>
                      </div>
                      
                      {/* Middle Column: Domain Scores (Graphs) */}
                      <div className="lg:col-span-8 flex flex-col justify-center">
                        <h4 className="text-sm font-bold text-slate-300 uppercase tracking-wider mb-5 flex items-center">
                          <CheckCircle className="w-4 h-4 mr-2 text-indigo-400" /> Domain Competency
                        </h4>
                        
                        <div className="space-y-4">
                          {matchReport.domain_scores?.map((ds: any, idx: number) => (
                            <div key={idx} className="bg-slate-900/30 p-3 rounded-xl border border-white/5">
                              <div className="flex justify-between items-end mb-2">
                                <span className="text-sm font-medium text-slate-200">{ds.domain}</span>
                                <span className="text-xs font-bold text-slate-400">{Math.round(ds.score)}% ({ds.matched}/{ds.total} skills)</span>
                              </div>
                              <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                                <div 
                                  className={`h-full rounded-full transition-all duration-1000 ease-out \${
                                    ds.score >= 80 ? 'bg-gradient-to-r from-emerald-500 to-emerald-400' : 
                                    ds.score >= 50 ? 'bg-gradient-to-r from-amber-500 to-amber-400' : 
                                    'bg-gradient-to-r from-red-500 to-red-400'
                                  }`} 
                                  style={{ width: `\${ds.score}%` }} 
                                />
                              </div>
                            </div>
                          ))}
                          
                          {/* Experience Bar */}
                          {matchReport.experience_match && (
                            <div className="bg-slate-900/30 p-3 rounded-xl border border-white/5 mt-4">
                              <div className="flex justify-between items-end mb-2">
                                <span className="text-sm font-medium text-slate-200">Experience (<span className="text-indigo-300">{matchReport.experience_match.candidate_years}</span> vs req <span className="text-slate-400">{matchReport.experience_match.required_years}</span> yrs)</span>
                                <span className="text-xs font-bold text-slate-400">{Math.round(matchReport.experience_match.score)}%</span>
                              </div>
                              <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                                <div 
                                  className={`h-full rounded-full bg-gradient-to-r from-indigo-600 to-purple-500 transition-all duration-1000 ease-out`} 
                                  style={{ width: `\${matchReport.experience_match.score}%` }} 
                                />
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                      
                    </div>
                    
                    {/* Bottom Row: Skills & Recommendation */}
                    <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-6 relative z-10">
                      <div className="bg-emerald-500/5 rounded-2xl p-5 border border-emerald-500/10">
                        <h4 className="text-sm font-bold text-emerald-400 uppercase tracking-wider mb-4 flex items-center">
                          <CheckCircle className="w-4 h-4 mr-2" /> Top Matched Skills
                        </h4>
                        <div className="flex flex-wrap gap-2">
                          {matchReport.skills_matched?.slice(0, 8).map((skill: any, idx: number) => (
                            <span key={idx} className="bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 text-xs px-2.5 py-1.5 rounded-lg shadow-sm">
                              {skill.skill} <span className="opacity-50 ml-1 text-[10px]">lvl {skill.level_in_cv}</span>
                            </span>
                          ))}
                          {(!matchReport.skills_matched || matchReport.skills_matched.length === 0) && (
                            <span className="text-sm text-slate-500 italic">No direct skill matches found.</span>
                          )}
                        </div>
                      </div>
                      
                      <div className="bg-amber-500/5 rounded-2xl p-5 border border-amber-500/10">
                        <h4 className="text-sm font-bold text-amber-400 uppercase tracking-wider mb-4 flex items-center">
                          <AlertTriangle className="w-4 h-4 mr-2" /> Missing or Critical Skills
                        </h4>
                        <div className="flex flex-wrap gap-2">
                          {matchReport.skills_missing?.slice(0, 6).map((skill: any, idx: number) => (
                            <span key={idx} className={`text-xs px-2.5 py-1.5 rounded-lg shadow-sm border \${skill.importance === 'critical' ? 'bg-red-500/10 text-red-300 border-red-500/20' : 'bg-amber-500/10 text-amber-300 border-amber-500/20'}`}>
                              {skill.skill} {skill.importance === 'critical' && <span className="ml-1 text-red-400">*</span>}
                            </span>
                          ))}
                          {(!matchReport.skills_missing || matchReport.skills_missing.length === 0) && (
                            <span className="text-sm text-slate-500 italic">No significant missing skills.</span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="mt-6 p-5 bg-indigo-500/10 rounded-2xl border border-indigo-500/20 relative z-10">
                      <h4 className="text-xs font-bold text-indigo-400 uppercase tracking-wider mb-2">AI Recommendation</h4>
                      <p className="text-slate-200 text-sm leading-relaxed italic">
                        "{matchReport.recommendation}"
                      </p>
                    </div>

                  </div>
                )}
              </div>
              
              <div className="p-6 border-t border-white/5 flex items-center justify-between bg-black/20">
                <button 
                  onClick={() => setStep(1)} 
                  className="px-6 py-2.5 text-slate-400 hover:text-white transition-colors font-medium"
                >
                  Back
                </button>
                <div className="flex items-center space-x-4">
                  {matchReport ? (
                    <button 
                      onClick={() => setStep(3)} 
                      className="flex items-center justify-center px-8 py-2.5 bg-gradient-to-r from-indigo-500 to-purple-500 hover:from-indigo-400 hover:to-purple-400 text-white font-medium rounded-xl transition-all shadow-[0_0_20px_rgba(99,102,241,0.4)]"
                    >
                      Continue Setup <ArrowRight className="ml-2 h-5 w-5" />
                    </button>
                  ) : (
                    <>
                      <button 
                        onClick={() => setStep(3)} 
                        className="px-6 py-2.5 border border-white/10 hover:bg-white/5 text-slate-300 font-medium rounded-xl transition-colors"
                      >
                        Skip
                      </button>
                      <button 
                        onClick={handleAnalyzeMatch} 
                        disabled={(inputType === 'text' && !jobDescription) || (inputType === 'url' && !jobUrl) || analyzingMatch} 
                        className="flex items-center justify-center px-6 py-2.5 bg-indigo-500 hover:bg-indigo-400 text-white font-medium rounded-xl transition-all shadow-[0_0_15px_rgba(99,102,241,0.3)] disabled:opacity-50 disabled:shadow-none"
                      >
                        {analyzingMatch ? (
                          <><Loader2 className="mr-2 h-5 w-5 animate-spin" /> Analyzing...</>
                        ) : (
                          <><Zap className="mr-2 h-5 w-5" /> Analyze Match</>
                        )}
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* STEP 3: CONFIGURE */}
          {step === 3 && (
            <div className="animate-in fade-in slide-in-from-right-8 duration-500">
              <div className="p-8 border-b border-white/5">
                <h2 className="text-2xl font-bold text-white flex items-center">
                  <Clock className="mr-3 text-indigo-400" /> Interview Configuration
                </h2>
                <p className="text-slate-400 mt-1">Set up the parameters for your simulated AI interview.</p>
              </div>
              
              <div className="p-8 grid gap-10">
                
                {/* Interview Type Selection */}
                <div>
                  <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-4 flex items-center">
                    <span className="w-6 h-px bg-slate-700 mr-3"></span> Interview Focus
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {['technical', 'behavioral', 'mixed'].map((type) => (
                      <label 
                        key={type}
                        className={`relative flex flex-col p-5 rounded-2xl border transition-all duration-300 cursor-pointer overflow-hidden \${interviewType === type ? 'bg-indigo-500/10 border-indigo-500/50 shadow-[0_0_20px_rgba(99,102,241,0.15)]' : 'bg-white/5 border-white/10 hover:bg-white/10'}`}
                      >
                        <input 
                          type="radio" 
                          name="interviewType" 
                          value={type} 
                          checked={interviewType === type} 
                          onChange={(e) => setInterviewType(e.target.value)} 
                          className="sr-only" 
                        />
                        <span className={`text-lg font-bold capitalize mb-1 transition-colors \${interviewType === type ? 'text-indigo-400' : 'text-slate-300'}`}>{type}</span>
                        <span className="text-xs text-slate-500">
                          {type === 'technical' && 'Focus on coding, system design, and hard skills.'}
                          {type === 'behavioral' && 'Focus on past experiences, culture fit, and soft skills.'}
                          {type === 'mixed' && 'A balanced mix of technical and behavioral questions.'}
                        </span>
                        {interviewType === type && <div className="absolute right-4 top-5 w-3 h-3 rounded-full bg-indigo-500 shadow-[0_0_10px_rgba(99,102,241,0.8)]" />}
                      </label>
                    ))}
                  </div>
                </div>
                
                {/* Duration Selection */}
                <div>
                  <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-6 flex items-center">
                    <span className="w-6 h-px bg-slate-700 mr-3"></span> Expected Duration
                  </h3>
                  <div className="flex justify-center">
                    <DurationPicker 
                      value={duration} 
                      onChange={(val) => setDuration(val)} 
                      min={5}
                      max={120}
                      step={5}
                    />
                  </div>
                </div>

              </div>
              
              <div className="p-6 border-t border-white/5 flex items-center justify-between bg-black/20">
                <button 
                  onClick={() => setStep(2)} 
                  className="px-6 py-2.5 text-slate-400 hover:text-white transition-colors font-medium"
                >
                  Back
                </button>
                <button 
                  onClick={handleStartSession} 
                  disabled={loading} 
                  className="flex items-center justify-center px-10 py-4 bg-gradient-to-r from-indigo-600 via-purple-600 to-fuchsia-600 hover:from-indigo-500 hover:via-purple-500 hover:to-fuchsia-500 text-white font-bold rounded-xl transition-all shadow-[0_0_30px_rgba(147,51,234,0.4)] hover:shadow-[0_0_40px_rgba(147,51,234,0.6)] disabled:opacity-50 disabled:shadow-none text-lg scale-100 hover:scale-[1.02] active:scale-[0.98]"
                >
                  {loading ? (
                    <><Loader2 className="mr-3 h-6 w-6 animate-spin" /> Initializing Agents...</>
                  ) : (
                    <>Start Interview <ArrowRight className="ml-3 h-6 w-6" /></>
                  )}
                </button>
              </div>
            </div>
          )}

        </div>
      </div>

      {/* ── Delete Confirmation Modal ── */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-white/10 rounded-3xl p-8 max-w-md w-full shadow-2xl animate-in zoom-in-95 duration-200">
            <div className="flex items-center mb-6">
              <div className="p-3 bg-red-500/20 rounded-xl mr-4">
                <Trash2 className="text-red-400 h-7 w-7" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-white">Delete Resume?</h3>
                <p className="text-slate-400 text-sm mt-0.5">This action cannot be undone.</p>
              </div>
            </div>
            
            <div className="bg-slate-800/60 border border-white/5 rounded-xl p-4 mb-6">
              <p className="text-slate-300 font-medium truncate">{confirmDelete.filename}</p>
              <p className="text-slate-500 text-sm mt-1">Uploaded {new Date(confirmDelete.created_at).toLocaleDateString()}</p>
              {confirmDelete.sessions_count > 0 && (
                <div className="mt-3 flex items-start text-amber-400 text-sm">
                  <AlertTriangle size={16} className="mr-2 mt-0.5 flex-shrink-0" />
                  <span>This resume was used in <strong>{confirmDelete.sessions_count}</strong> session(s). Those sessions will lose the reference to this resume.</span>
                </div>
              )}
            </div>

            <div className="flex items-center justify-end space-x-3">
              <button
                onClick={() => setConfirmDelete(null)}
                className="px-5 py-2.5 text-slate-400 hover:text-white border border-white/10 hover:border-white/20 rounded-xl transition-colors font-medium"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDeleteResume(confirmDelete)}
                className="flex items-center px-6 py-2.5 bg-red-600 hover:bg-red-500 text-white font-bold rounded-xl transition-colors shadow-[0_0_20px_rgba(239,68,68,0.3)] hover:shadow-[0_0_30px_rgba(239,68,68,0.5)]"
              >
                <Trash2 size={16} className="mr-2" /> Delete Permanently
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

