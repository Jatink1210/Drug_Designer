import React, { createContext, useContext, useState, useEffect } from 'react';

interface User {
  id: string;
  email: string;
  full_name?: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (token: string, userData: User) => void;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  token: null,
  login: () => {},
  logout: () => {},
  isLoading: true,
});

export const useAuth = () => useContext(AuthContext);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const storedToken = localStorage.getItem('dss_auth_token');
    
    // Check if auth is disabled entirely via health/config endpoint (assuming dev mode if fetch fails)
    const checkAuthStatus = async () => {
      if (storedToken) {
        setToken(storedToken);
        try {
          const res = await fetch('http://localhost:8000/api/auth/me', {
            headers: { Authorization: `Bearer ${storedToken}` }
          });
          if (res.ok) {
            setUser(await res.json());
          } else {
            localStorage.removeItem('dss_auth_token');
            setToken(null);
          }
        } catch {
          // If offline, assume logged out
        }
      } else {
        // Desktop implicit bypass check mechanism could go here
      }
      setIsLoading(false);
    };

    checkAuthStatus();
  }, []);

  const login = (newToken: string, userData: User) => {
    localStorage.setItem('dss_auth_token', newToken);
    setToken(newToken);
    setUser(userData);
  };

  const logout = () => {
    localStorage.removeItem('dss_auth_token');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
};
