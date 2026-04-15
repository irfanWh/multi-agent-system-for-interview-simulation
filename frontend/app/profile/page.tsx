"use client";

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';

export default function ProfileSetup() {
  const [file, setFile] = useState<File | null>(null);
  const [role, setRole] = useState('Software Engineer');
  const [level, setLevel] = useState('junior');
  const [loading, setLoading] = useState(false);
  const [profileData, setProfileData] = useState<any>(null);
  const [interviewType, setInterviewType] = useState('mixed');
  const [duration, setDuration] = useState('30');
  
  const ctx = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!ctx.loading && !ctx.user) {
      router.push('/');
    }
  }, [ctx, router]);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return alert('Please select a CV file');
    
    setLoading(true);
    try {
      // 1. Upload CV
      const res = await api.uploadCV(file, role, level);
      if (!res.ok) throw new Error('Failed to upload CV');
      const profile = await res.json();
      
      // 2. Analyze Profile
      const analyzeRes = await api.analyzeProfile(profile.id);
      if (!analyzeRes.ok) throw new Error('Analysis failed');
      const analyzed = await analyzeRes.json();
      
      setProfileData(analyzed);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  };

  const startInterview = async () => {
    if (!profileData) return;
    setLoading(true);
    try {
      const res = await api.createSession({
        interview_type: interviewType,
        profile_id: profileData.id,
        user_id: ctx.user?.id
      });
      if (!res.ok) throw new Error('Failed to create session');
      const session = await res.json();
      router.push(`/session/${session.id}`);
    } catch (err: any) {
      alert(err.message);
      setLoading(false);
    }
  };

  if (!ctx.user) return null;

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Interview Setup</h1>
        <Button variant="outline" onClick={ctx.logout}>Logout</Button>
      </div>

      {!profileData ? (
        <Card>
          <CardHeader>
            <CardTitle>1. Upload your CV</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleUpload} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">CV Document (PDF/DOCX)</label>
                <input 
                  type="file" 
                  accept=".pdf,.docx" 
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  className="w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Target Role</label>
                  <Input value={role} onChange={e => setRole(e.target.value)} />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Experience Level</label>
                  <select 
                    value={level} 
                    onChange={e => setLevel(e.target.value)}
                    className="flex h-10 w-full rounded-md border border-slate-300 bg-transparent px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-600"
                  >
                    <option value="junior">Junior</option>
                    <option value="mid">Mid-Level</option>
                    <option value="senior">Senior</option>
                    <option value="lead">Lead</option>
                  </select>
                </div>
              </div>
              <Button type="submit" isLoading={loading}>Analyze Profile</Button>
            </form>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Profile Analysis Complete</CardTitle>
            </CardHeader>
            <CardContent>
              {profileData.skills_extracted && (
                <div className="space-y-4 bg-slate-50 p-4 rounded-lg text-sm">
                  <div>
                    <span className="font-semibold text-slate-700">Estimated Level: </span>
                    <span className="capitalize">{profileData.skills_extracted.calibrated_level}</span>
                  </div>
                  <div>
                    <span className="font-semibold text-slate-700">Priority Domains: </span>
                    {profileData.skills_extracted.priority_domains?.join(", ")}
                  </div>
                  <div>
                    <span className="font-semibold text-slate-700">Detected Gaps: </span>
                    {profileData.skills_extracted.detected_gaps?.join(", ")}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>2. Configure Interview</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Interview Type</label>
                  <select 
                    value={interviewType} 
                    onChange={e => setInterviewType(e.target.value)}
                    className="flex h-10 w-full rounded-md border border-slate-300 bg-transparent px-3 py-2 text-sm"
                  >
                    <option value="technical">Technical</option>
                    <option value="behavioral">Behavioral</option>
                    <option value="mixed">Mixed</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Duration (minutes)</label>
                  <select 
                    value={duration} 
                    onChange={e => setDuration(e.target.value)}
                    className="flex h-10 w-full rounded-md border border-slate-300 bg-transparent px-3 py-2 text-sm"
                  >
                    <option value="20">20 min</option>
                    <option value="30">30 min</option>
                    <option value="45">45 min</option>
                  </select>
                </div>
              </div>
              <Button onClick={startInterview} isLoading={loading} className="w-full">
                Start Interview Session
              </Button>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
