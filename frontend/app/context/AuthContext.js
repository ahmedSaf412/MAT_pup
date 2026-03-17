'use client';

import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import api from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);

  // Load token from localStorage on mount
  useEffect(() => {
    const savedToken = localStorage.getItem('token');
    const savedUser = localStorage.getItem('user');
    if (savedToken && savedUser) {
      setToken(savedToken);
      setUser(JSON.parse(savedUser));
    }
    setLoading(false);
  }, []);

  const login = useCallback(async (email, password) => {
    try {
      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', password);

      const response = await api.post('/api/auth/login', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
      });

      const { access_token } = response.data;
      setToken(access_token);
      localStorage.setItem('token', access_token);

      // Fetch user profile
      const profileRes = await api.get('/api/users/me', {
        headers: { Authorization: `Bearer ${access_token}` }
      });

      setUser(profileRes.data);
      localStorage.setItem('user', JSON.stringify(profileRes.data));
      return { success: true };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Login failed'
      };
    }
  }, []);

  const register = useCallback(async (userData) => {
    try {
      await api.post('/api/auth/register', userData);
      // Auto-login after registration
      return await login(userData.email, userData.password);
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Registration failed'
      };
    }
  }, [login]);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('token');
    localStorage.removeItem('user');
  }, []);

  const updateUser = useCallback((updatedData) => {
    setUser(prev => {
      const newUser = { ...prev, ...updatedData };
      localStorage.setItem('user', JSON.stringify(newUser));
      return newUser;
    });
  }, []);

  // For demo mode — use mock data when backend is not available
  const demoLogin = useCallback((role) => {
    const mockUser = {
      id: 1,
      email: role === 'coach' ? 'coach@demo.com' : 'user@demo.com',
      full_name: role === 'coach' ? 'Coach Ahmed' : 'Trainee Mohamed',
      role: role,
      belt_level: role === 'coach' ? 'black' : 'white',
      created_at: new Date().toISOString()
    };
    const mockToken = 'demo-token-' + role;
    setToken(mockToken);
    setUser(mockUser);
    localStorage.setItem('token', mockToken);
    localStorage.setItem('user', JSON.stringify(mockUser));
    return { success: true };
  }, []);

  const value = {
    user,
    token,
    loading,
    isAuthenticated: !!token,
    isCoach: user?.role === 'coach',
    isTrainer: user?.role === 'trainer' || user?.role === 'user',
    login,
    register,
    logout,
    updateUser,
    demoLogin,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
