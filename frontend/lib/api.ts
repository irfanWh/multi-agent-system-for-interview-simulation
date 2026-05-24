export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
export const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws';

export async function fetchAPI(path: string, options: RequestInit = {}) {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
  
  const isFormData = options.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers as any),
  };

  if (!isFormData && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('token');
      window.location.href = '/';
    }
  }

  if (!response.ok) {
    let detail = 'An error occurred';
    try {
      const errData = await response.json();
      detail = errData.detail || detail;
    } catch (e) {}
    throw { response: { data: { detail } } };
  }

  return { data: await response.json() };
}

export const api = {
  get: async (path: string, options?: RequestInit) => {
    return fetchAPI(path, { ...options, method: 'GET' });
  },
  post: async (path: string, body?: any, options?: RequestInit) => {
    const isFormData = body instanceof FormData;
    return fetchAPI(path, { 
      ...options, 
      method: 'POST', 
      body: isFormData ? body : JSON.stringify(body) 
    });
  },
  login: async (formData: FormData) => {
    // OAuth2PasswordRequestForm expects form url encoded
    const res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      throw new Error("Invalid credentials");
    }
    const data = await res.json();
    return { data, ok: res.ok, json: async () => data };
  },
  
  register: async (data: any) => {
    return fetchAPI('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  getMe: async () => {
    return fetchAPI('/auth/me');
  },

  uploadCV: async (file: File, role: string, level: string, jobText?: string, jobUrl?: string) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("target_role", role);
    formData.append("experience_level", level);
    if (jobText) formData.append("job_description_text", jobText);
    if (jobUrl) formData.append("job_description_url", jobUrl);

    const token = localStorage.getItem('token');
    return fetch(`${API_BASE_URL}/profiles/upload-cv`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    });
  },

  analyzeProfile: async (profileId: string) => {
    return fetchAPI(`/profiles/${profileId}/analyze`, { method: 'POST' });
  },

  analyzeMatch: async (profileId: string) => {
    return fetchAPI(`/profiles/${profileId}/match-analysis`, { method: 'POST' });
  },

  createSession: async (data: any) => {
    return fetchAPI('/sessions/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  getSession: async (id: string) => {
    return fetchAPI(`/sessions/${id}`);
  },

  getExchanges: async (id: string) => {
    return fetchAPI(`/sessions/${id}/exchanges`);
  },
  
  getReport: async (sessionId: string) => {
    return fetchAPI(`/sessions/${sessionId}/report`);
  },

  generateReport: async (sessionId: string) => {
    return fetchAPI(`/sessions/${sessionId}/generate-report`, { method: 'POST' });
  },

  getEvaluations: async (sessionId: string) => {
    return fetchAPI(`/sessions/${sessionId}/evaluations`);
  },

  getDashboardStats: async () => {
    return fetchAPI('/dashboard/stats');
  },

  getRecruiterSessions: async () => {
    return fetchAPI('/recruiter/sessions');
  },

  createRecruiterSession: async (data: any) => {
    return fetchAPI('/recruiter/sessions', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  regenerateRecruiterCode: async (interviewId: string) => {
    return fetchAPI(`/recruiter/sessions/${interviewId}/regenerate-code`, { method: 'POST' });
  },

  getRecruiterReport: async (interviewId: string) => {
    return fetchAPI(`/recruiter/sessions/${interviewId}/report`);
  },

  validateCandidateCode: async (code: string) => {
    return fetchAPI('/candidate-access/validate', {
      method: 'POST',
      body: JSON.stringify({ code }),
    });
  },

  uploadCandidateResume: async (code: string, file: File, candidateName?: string, candidateEmail?: string) => {
    const formData = new FormData();
    formData.append('code', code);
    formData.append('file', file);
    if (candidateName) formData.append('candidate_name', candidateName);
    if (candidateEmail) formData.append('candidate_email', candidateEmail);
    return fetchAPI('/candidate-access/upload-resume', {
      method: 'POST',
      body: formData,
    });
  },

  startCandidateInterview: async (code: string, candidateName?: string, candidateEmail?: string) => {
    return fetchAPI('/candidate-access/start', {
      method: 'POST',
      body: JSON.stringify({ code, candidate_name: candidateName, candidate_email: candidateEmail }),
    });
  }
};
