import React, { useState } from 'react';
import { useAuth } from '../components/AuthProvider';
import { Target } from 'lucide-react';
import { ensureApiBase } from '@/lib/api';

export function LoginPage() {
  const { login } = useAuth();
  const [isRegistering, setIsRegistering] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    try {
      const base = await ensureApiBase();
      if (isRegistering) {
        const res = await fetch(`${base}/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password, full_name: fullName }),
        });
        if (!res.ok) throw new Error((await res.json()).detail || 'Registration failed');
      }

      const params = new URLSearchParams();
      params.append('username', email);
      params.append('password', password);

      const res = await fetch(`${base}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: params,
      });

      if (!res.ok) throw new Error('Invalid credentials');
      const data = await res.json();
      
      const meRes = await fetch(`${base}/auth/me`, {
        headers: { Authorization: `Bearer ${data.access_token}` }
      });
      const userData = await meRes.json();
      
      login(data.access_token, userData);
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div className="flex h-screen items-center justify-center bg-[var(--bg-app)] px-4">
      {/* Impeccable constraint: No wrapping "cards" unless necessary. Let it breathe on the background. */}
      <div className="w-full max-w-sm space-y-10">
        
        <div className="flex flex-col items-center">
            {/* Minimalist Logo */}
            <div className="w-12 h-12 mb-6 text-[var(--accent)] flex items-center justify-center border border-[var(--border)] shadow-sm bg-[var(--bg-elevated)] p-2">
                <Target size={24} strokeWidth={1.5} />
            </div>

            <h1 className="text-3xl font-bold tracking-tight text-center text-[var(--accent)]">
                DrugDesigner
            </h1>
            <p className="mt-4 text-center text-sm font-medium text-[var(--text-secondary)] tracking-wide">
                {isRegistering ? 'Register your instance' : 'Access your workstation'}
            </p>
        </div>

        <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
          {error && (
            <div className="p-3 border border-red-200 bg-red-50 text-red-700 text-xs font-semibold text-center">
              {error}
            </div>
          )}

          <div className="space-y-4">
            {isRegistering && (
              <div>
                <input
                  type="text"
                  required
                  className="w-full px-4 py-2.5 text-sm bg-transparent border-b border-[var(--border)] text-[var(--text-primary)] focus:border-[var(--accent)] focus:outline-none transition-colors placeholder:text-[var(--text-muted)]"
                  placeholder="Full Name"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                />
              </div>
            )}
            <div>
              <input
                type="email"
                required
                className="w-full px-4 py-2.5 text-sm bg-transparent border-b border-[var(--border)] text-[var(--text-primary)] focus:border-[var(--accent)] focus:outline-none transition-colors placeholder:text-[var(--text-muted)]"
                placeholder="Email Address"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div>
              <input
                type="password"
                required
                className="w-full px-4 py-2.5 text-sm bg-transparent border-b border-[var(--border)] text-[var(--text-primary)] focus:border-[var(--accent)] focus:outline-none transition-colors placeholder:text-[var(--text-muted)]"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
          </div>

          <div className="pt-4">
            <button
              type="submit"
              className="w-full bg-[var(--accent)] text-white py-3 px-4 text-sm font-semibold tracking-wide hover:bg-[var(--accent-hover)] transition-colors"
            >
              {isRegistering ? 'INITIALIZE' : 'SIGN IN'}
            </button>
          </div>
          
          <div className="text-center pt-6 pb-2">
            <button
              type="button"
              className="text-xs font-semibold text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors uppercase tracking-wider"
              onClick={() => setIsRegistering(!isRegistering)}
            >
              {isRegistering ? '← Back to Login' : 'Create an Account'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
