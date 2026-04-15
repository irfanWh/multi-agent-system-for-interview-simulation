export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
export const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws';

export async function fetchAPI(path: string, options: RequestInit = {}) {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
  
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

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

  return response;
}

export const api = {
  login: async (formData: FormData) => {
    // OAuth2PasswordRequestForm expects form url encoded
    return fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      body: formData,
    });
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

  uploadCV: async (file: File, role: string, level: string) => {
    const formData = new FormData();
    formData.append("file", file);

    const token = localStorage.getItem('token');
    return fetch(`${API_BASE_URL}/profiles/upload-cv?target_role=${encodeURIComponent(role)}&experience_level=${encodeURIComponent(level)}`, {
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
  }
};
