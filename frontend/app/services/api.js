import axios from 'axios';

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  timeout: 15000,   // 15 s — fail fast instead of hanging while models load
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor — attach JWT token
api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Response interceptor — handle 401 and timeout
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Timeout — backend is likely still loading models
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      error.friendlyMessage =
        '⏳ The server is still starting up (loading AI models). Please wait a moment and try again.';
    }

    if (error.response?.status === 401 && typeof window !== 'undefined') {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default api;
