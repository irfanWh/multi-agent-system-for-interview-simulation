// ──────────────────────────────────────────────────────────────────────────────
// MatchReport types — mirrors backend MatchReport Pydantic schema
// ──────────────────────────────────────────────────────────────────────────────

export interface SkillMatched {
  skill: string
  level_in_cv: string   // "junior"|"mid"|"senior"|"expert"
  level_required: string
}

export interface SkillMissing {
  skill: string
  importance: 'critical' | 'nice_to_have'
  learn_time_weeks: number
}

export interface DomainScore {
  domain: string
  score: number           // 0-10 (legacy — candidate side)
  candidate_score: number // 0-10
  required_score: number  // 0-10
  matched: number
  total: number
}

export interface ExperienceMatch {
  score: number
  candidate_years: number
  required_years: number
  verdict: string
}

export interface SenioritySignal {
  signal: string  // "Technical depth"|"Ownership"|"Leadership"|"Impact"
  score: number   // 0-10
}

export interface KeywordAlignment {
  keyword: string
  jd_frequency: number
  found_in_cv: boolean
}

export interface CvVsJdInsight {
  type: 'gap' | 'strength' | 'warning'
  title: string
  body: string
}

export interface InterviewFocusArea {
  domain: string
  reason: string
  probability: 'high' | 'medium' | 'low'
  tip: string
}

export interface MatchReport {
  global_match_score: number
  readiness_level: 'strong_match' | 'good_match' | 'partial_match' | 'weak_match'
  recommendation: string

  skills_matched: SkillMatched[]
  skills_missing: SkillMissing[]
  skills_exceeded: string[]

  domain_scores: DomainScore[]
  experience_match: ExperienceMatch

  seniority_signals: SenioritySignal[]
  keyword_alignment: KeywordAlignment[]
  cv_vs_jd_insights: CvVsJdInsight[]

  soft_skills_found: string[]
  soft_skills_missing: string[]
  soft_skills_tip: string

  interview_focus_areas: InterviewFocusArea[]
}
