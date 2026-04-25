'use client'

import React from 'react'
import {
  Chart as ChartJS, CategoryScale, LinearScale,
  BarElement, Title, Tooltip, Legend
} from 'chart.js'
import { Bar } from 'react-chartjs-2'
import type {
  MatchReport, SkillMatched, SkillMissing, DomainScore,
  KeywordAlignment, CvVsJdInsight, InterviewFocusArea
} from './MatchDashboard.types'

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend)

// ── Helpers ──────────────────────────────────────────────────────────────────
function scoreColor(score: number, required: number) {
  if (score >= required) return '#5DCAA5'
  if (score >= required * 0.8) return '#EF9F27'
  return '#E24B4A'
}
function matchColor(score: number) {
  if (score >= 75) return 'text-green-600'
  if (score >= 50) return 'text-amber-600'
  return 'text-red-500'
}
function matchBg(score: number) {
  if (score >= 75) return '#1D9E75'
  if (score >= 50) return '#BA7517'
  return '#E24B4A'
}
const LEVEL_ORDER: Record<string, number> = { junior: 1, mid: 2, senior: 3, expert: 4 }
function levelMet(cv: string, req: string) {
  return (LEVEL_ORDER[cv] ?? 2) >= (LEVEL_ORDER[req] ?? 2)
}

const SectionHeader = ({ num, title }: { num: number; title: string }) => (
  <div className="text-xs font-medium text-gray-400 uppercase tracking-wide border-b border-gray-700 pb-1.5 mb-3">
    {num} — {title}
  </div>
)

const Pill = ({ children, className = '' }: { children: React.ReactNode; className?: string }) => (
  <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium mr-1.5 mb-1.5 ${className}`}>
    {children}
  </span>
)

// ── Props ────────────────────────────────────────────────────────────────────
interface MatchDashboardProps {
  matchReport: MatchReport
  onStartInterview: (focusAreas: string[]) => void
  wasCached?: boolean
  cacheAgeHours?: number
}

// ══════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ══════════════════════════════════════════════════════════════════════════════
export default function MatchDashboard({ matchReport: r, onStartInterview, wasCached = false, cacheAgeHours }: MatchDashboardProps) {
  const criticalGaps = (r.skills_missing ?? []).filter(s => s.importance === 'critical').length
  const exp = r.experience_match
  const domains = r.domain_scores ?? []
  const domainsMet = domains.filter(d => (d.candidate_score || d.score) >= (d.required_score || 5)).length
  const domainsNeed = domains.length - domainsMet
  const keywords = [...(r.keyword_alignment ?? [])].sort((a, b) => b.jd_frequency - a.jd_frequency)
  const kwFound = keywords.filter(k => k.found_in_cv).length
  const kwHighMissing = keywords.filter(k => !k.found_in_cv && k.jd_frequency >= 3).length

  return (
    <div className="space-y-6 text-gray-200">

      {/* ── SECTION 0: Verdict ──────────────────────────────────────────── */}
      <section className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <div className="flex flex-col md:flex-row gap-6 items-start">
          {/* Left: score */}
          <div className="flex flex-col items-center shrink-0">
            <span className="text-6xl font-black" style={{ color: matchBg(r.global_match_score) }}>
              {Math.round(r.global_match_score)}%
            </span>
            <Pill className={`mt-2 ${
              r.readiness_level === 'strong_match' ? 'bg-green-900/60 text-green-400 border border-green-700' :
              r.readiness_level === 'good_match' ? 'bg-green-900/40 text-green-400 border border-green-800' :
              r.readiness_level === 'partial_match' ? 'bg-amber-900/40 text-amber-400 border border-amber-700' :
              'bg-red-900/40 text-red-400 border border-red-700'
            }`}>
              {r.readiness_level === 'strong_match' ? 'Strong match' :
               r.readiness_level === 'good_match' ? 'Good match' :
               r.readiness_level === 'partial_match' ? 'Partial match' :
               'Weak match — consider applying anyway'}
            </Pill>
            {wasCached && (
              <span className="mt-2 text-[10px] text-indigo-400 flex items-center gap-1">
                ⚡ instant{cacheAgeHours ? ` · cached ${cacheAgeHours}h ago` : ''}
              </span>
            )}
          </div>
          {/* Right: text */}
          <div className="flex-1 min-w-0">
            <p className="text-sm text-gray-300 leading-relaxed mb-3">{r.recommendation}</p>
            <div className="flex flex-wrap gap-2">
              <Pill className="bg-green-900/40 text-green-400 border border-green-800">
                {(r.skills_matched ?? []).length} skills matched
              </Pill>
              <Pill className="bg-red-900/40 text-red-400 border border-red-800">
                {criticalGaps} critical gaps
              </Pill>
              <Pill className="bg-amber-900/40 text-amber-400 border border-amber-800">
                {exp?.candidate_years ?? '?'} yrs vs {exp?.required_years ?? '?'} required
              </Pill>
            </div>
          </div>
        </div>
      </section>

      {/* ── SECTION 1: Skills coverage ──────────────────────────────────── */}
      <section className="mb-6">
        <SectionHeader num={1} title="Skills coverage" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Left: matched */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Skills you have</h4>
            <div className="space-y-2">
              {(r.skills_matched ?? []).map((s, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  <span className={`w-2 h-2 rounded-full shrink-0 ${levelMet(s.level_in_cv, s.level_required) ? 'bg-green-500' : 'bg-amber-500'}`} />
                  <span className="text-gray-200">{s.skill}</span>
                  <Pill className={levelMet(s.level_in_cv, s.level_required) ? 'bg-green-900/40 text-green-400 border border-green-800' : 'bg-amber-900/40 text-amber-400 border border-amber-800'}>
                    {s.level_in_cv} · req: {s.level_required}
                  </Pill>
                </div>
              ))}
            </div>
            {(r.skills_exceeded ?? []).length > 0 && (
              <div className="mt-4 pt-3 border-t border-gray-800 flex flex-wrap gap-1">
                {r.skills_exceeded.map((s, i) => (
                  <Pill key={i} className="bg-green-900/40 text-green-400 border border-green-800">{s} (exceeds)</Pill>
                ))}
              </div>
            )}
          </div>
          {/* Right: missing */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Missing from your profile</h4>
            <div className="space-y-2">
              {(r.skills_missing ?? []).map((s, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  <span className={`w-2 h-2 rounded-full shrink-0 ${s.importance === 'critical' ? 'bg-red-500' : 'bg-amber-500'}`} />
                  <span className="text-gray-200">{s.skill}</span>
                  <Pill className={s.importance === 'critical' ? 'bg-red-900/40 text-red-400 border border-red-800' : 'bg-amber-900/40 text-amber-400 border border-amber-800'}>
                    {s.importance === 'critical' ? 'Critical · not in CV' : `Nice-to-have · ~${s.learn_time_weeks} wks`}
                  </Pill>
                </div>
              ))}
              {(r.skills_missing ?? []).length === 0 && <p className="text-xs text-gray-500 italic">No significant gaps.</p>}
            </div>
          </div>
        </div>
      </section>

      {/* ── SECTION 2: Domain scores chart ──────────────────────────────── */}
      <section className="mb-6">
        <SectionHeader num={2} title="Domain scores vs required" />
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="flex gap-4 mb-2 text-xs text-gray-400">
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm" style={{ background: '#5DCAA5' }} /> Your level</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm" style={{ background: '#D3D1C7' }} /> Required</span>
          </div>
          <div style={{ height: '220px' }}>
            <Bar
              data={{
                labels: domains.map(d => d.domain),
                datasets: [
                  {
                    label: 'Your level',
                    data: domains.map(d => d.candidate_score || d.score || 0),
                    backgroundColor: domains.map(d => scoreColor(d.candidate_score || d.score || 0, d.required_score || 5)),
                    borderRadius: 4,
                    barPercentage: 0.5,
                  },
                  {
                    label: 'Required',
                    data: domains.map(d => d.required_score || 5),
                    backgroundColor: '#D3D1C7',
                    borderRadius: 4,
                    barPercentage: 0.5,
                  },
                ],
              }}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  legend: { display: false },
                  tooltip: {
                    callbacks: {
                      label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y}/10`,
                    },
                  },
                },
                scales: {
                  y: { min: 0, max: 10, ticks: { stepSize: 2, color: '#9ca3af' }, grid: { color: '#374151' } },
                  x: { ticks: { color: '#9ca3af', font: { size: 10 } }, grid: { display: false } },
                },
              }}
            />
          </div>
          <p className="text-xs text-gray-500 mt-2">
            {domainsMet} of {domains.length} domains meet requirements · {domainsNeed} domains need attention
          </p>
        </div>
      </section>

      {/* ── SECTION 3: Experience & seniority ───────────────────────────── */}
      <section className="mb-6">
        <SectionHeader num={3} title="Experience & seniority fit" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Experience card */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Years of experience</h4>
            {exp && (() => {
              const pct = Math.min((exp.candidate_years / Math.max(exp.required_years, 1)) * 100, 100)
              const diff = exp.required_years - exp.candidate_years
              const barColor = diff <= 0 ? '#5DCAA5' : diff <= 1 ? '#EF9F27' : '#E24B4A'
              return (
                <>
                  <div className="flex justify-between text-xs text-gray-400 mb-1">
                    <span>Your experience</span><span>Required</span>
                  </div>
                  <div className="relative h-2 bg-gray-800 rounded-full overflow-visible mb-2">
                    <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: barColor }} />
                    <div className="absolute top-[-3px] h-4 w-0.5 bg-red-500" style={{ left: '100%' }} />
                  </div>
                  <div className="flex justify-between text-xs">
                    <span style={{ color: barColor }}>{exp.candidate_years} years</span>
                    <span className="text-red-400">{exp.required_years} years required</span>
                  </div>
                  <p className="text-xs text-gray-500 mt-2">{exp.verdict}</p>
                </>
              )
            })()}
          </div>
          {/* Seniority card */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Seniority calibration</h4>
            <div className="space-y-3">
              {(r.seniority_signals ?? []).map((s, i) => {
                const c = s.score >= 7 ? '#5DCAA5' : s.score >= 5 ? '#EF9F27' : '#E24B4A'
                return (
                  <div key={i}>
                    <div className="flex justify-between text-xs text-gray-300 mb-1">
                      <span>{s.signal}</span><span style={{ color: c }}>{s.score}/10</span>
                    </div>
                    <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                      <div className="h-full rounded-full transition-all duration-500" style={{ width: `${s.score * 10}%`, background: c }} />
                    </div>
                  </div>
                )
              })}
              {(r.seniority_signals ?? []).length === 0 && <p className="text-xs text-gray-500 italic">No seniority signals available.</p>}
            </div>
          </div>
        </div>
      </section>

      {/* ── SECTION 4: Keyword alignment ────────────────────────────────── */}
      <section className="mb-6">
        <SectionHeader num={4} title="Keyword alignment" />
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="flex flex-wrap gap-1.5">
            {keywords.map((k, i) => {
              let cls = ''
              if (k.found_in_cv && k.jd_frequency >= 3) cls = 'bg-green-900/50 text-green-400 border border-green-700'
              else if (k.found_in_cv) cls = 'bg-green-900/30 text-green-500 border border-green-800'
              else if (k.jd_frequency >= 3) cls = 'bg-red-900/40 text-red-400 border border-red-700'
              else cls = 'text-gray-500 border border-dashed border-gray-700'
              return <Pill key={i} className={cls}>{k.keyword} ×{k.jd_frequency}</Pill>
            })}
          </div>
          {keywords.length > 0 && (
            <p className="text-xs text-gray-500 mt-3">
              {kwFound} of {keywords.length} key terms found in your CV · {kwHighMissing} high-frequency terms absent
            </p>
          )}
        </div>
      </section>

      {/* ── SECTION 5: CV vs JD insights ────────────────────────────────── */}
      <section className="mb-6">
        <SectionHeader num={5} title="CV vs JD narrative insights" />
        <div className="space-y-2">
          {(r.cv_vs_jd_insights ?? []).map((ins, i) => {
            const border = ins.type === 'gap' ? 'border-l-amber-500' : ins.type === 'strength' ? 'border-l-green-500' : 'border-l-red-500'
            const bg = ins.type === 'gap' ? 'bg-amber-950/20' : ins.type === 'strength' ? 'bg-green-950/20' : 'bg-red-950/20'
            return (
              <div key={i} className={`border-l-4 ${border} ${bg} rounded-r-lg p-3`}>
                <p className="text-[13px] font-semibold text-gray-200">{ins.title}</p>
                <p className="text-[12px] text-gray-400 leading-relaxed mt-0.5">{ins.body}</p>
              </div>
            )
          })}
          {(r.cv_vs_jd_insights ?? []).length === 0 && <p className="text-xs text-gray-500 italic">No detailed insights available.</p>}
        </div>
      </section>

      {/* ── SECTION 6: Soft skills ──────────────────────────────────────── */}
      <section className="mb-6">
        <SectionHeader num={6} title="Soft skills & culture fit" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-3">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Found in your CV</h4>
            <div className="flex flex-wrap">{(r.soft_skills_found ?? []).map((s, i) => (
              <Pill key={i} className="bg-green-900/40 text-green-400 border border-green-800">{s}</Pill>
            ))}</div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Expected by JD — not visible</h4>
            <div className="flex flex-wrap">{(r.soft_skills_missing ?? []).map((s, i) => (
              <Pill key={i} className="text-gray-500 border border-dashed border-gray-700">{s}</Pill>
            ))}</div>
          </div>
        </div>
        {r.soft_skills_tip && (
          <div className="border-l-4 border-l-amber-500 pl-3 py-1">
            <p className="text-xs text-gray-400"><span className="font-semibold text-amber-400">Tip:</span> {r.soft_skills_tip}</p>
          </div>
        )}
      </section>

      {/* ── SECTION 7: Interview focus areas ────────────────────────────── */}
      <section className="mb-6">
        <SectionHeader num={7} title="Interview focus areas" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {(r.interview_focus_areas ?? []).map((f, i) => {
            const bdr = f.probability === 'high' ? 'border-l-red-500' : f.probability === 'medium' ? 'border-l-amber-500' : 'border-l-gray-500'
            return (
              <div key={i} className={`bg-gray-900 border border-gray-800 border-l-4 ${bdr} rounded-xl p-4`}>
                <p className="text-[13px] font-medium text-gray-200 mb-1">{f.domain}</p>
                <p className="text-[12px] text-gray-400 leading-relaxed mb-2">{f.reason}</p>
                <Pill className={
                  f.probability === 'high' ? 'bg-red-900/40 text-red-400 border border-red-800' :
                  f.probability === 'medium' ? 'bg-amber-900/40 text-amber-400 border border-amber-800' :
                  'bg-gray-800 text-gray-400 border border-gray-700'
                }>
                  {f.probability === 'high' ? 'High probability' : f.probability === 'medium' ? 'Medium probability' : 'Lower priority'}
                </Pill>
                {f.tip && <p className="text-[11px] text-gray-500 italic mt-2">{f.tip}</p>}
              </div>
            )
          })}
        </div>
      </section>

      {/* ── BOTTOM CTA ──────────────────────────────────────────────────── */}
      <section className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex flex-col md:flex-row items-center gap-4">
        <p className="text-sm text-gray-400 flex-1">{r.recommendation}</p>
        <button
          onClick={() => onStartInterview((r.interview_focus_areas ?? []).map(f => f.domain))}
          className="shrink-0 px-6 py-3 bg-gradient-to-r from-indigo-600 via-purple-600 to-fuchsia-600 hover:from-indigo-500 hover:via-purple-500 hover:to-fuchsia-500 text-white font-bold rounded-xl transition-all shadow-[0_0_20px_rgba(147,51,234,0.4)] hover:shadow-[0_0_30px_rgba(147,51,234,0.6)]"
        >
          Start targeted interview →
        </button>
      </section>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
// SKELETON
// ══════════════════════════════════════════════════════════════════════════════
const Bone = ({ className = '' }: { className?: string }) => (
  <div className={`animate-pulse bg-gray-800 rounded ${className}`} />
)

export function MatchDashboardSkeleton() {
  return (
    <div className="space-y-6">
      {/* Verdict */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex gap-6">
        <Bone className="w-24 h-24 rounded-lg shrink-0" />
        <div className="flex-1 space-y-2"><Bone className="h-4 w-3/4" /><Bone className="h-4 w-1/2" /><div className="flex gap-2 mt-3"><Bone className="h-5 w-24 rounded-full" /><Bone className="h-5 w-20 rounded-full" /><Bone className="h-5 w-28 rounded-full" /></div></div>
      </div>
      {/* Skills */}
      <div className="grid grid-cols-2 gap-4">{[0,1].map(i => <div key={i} className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-2"><Bone className="h-3 w-24" /><Bone className="h-3 w-full" /><Bone className="h-3 w-5/6" /><Bone className="h-3 w-4/6" /></div>)}</div>
      {/* Chart */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4"><Bone className="h-[220px] w-full rounded-lg" /></div>
      {/* Experience */}
      <div className="grid grid-cols-2 gap-4">{[0,1].map(i => <div key={i} className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-2"><Bone className="h-3 w-24" /><Bone className="h-2 w-full rounded-full" /><Bone className="h-3 w-3/4" /></div>)}</div>
      {/* Keywords */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex flex-wrap gap-1.5">{Array.from({length:12}).map((_,i) => <Bone key={i} className="h-5 w-16 rounded-full" />)}</div>
      {/* Insights */}
      <div className="space-y-2">{[0,1,2].map(i => <Bone key={i} className="h-14 w-full rounded-lg" />)}</div>
      {/* Focus areas */}
      <div className="grid grid-cols-3 gap-3">{[0,1,2].map(i => <Bone key={i} className="h-28 rounded-xl" />)}</div>
    </div>
  )
}
