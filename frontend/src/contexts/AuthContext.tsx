"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface AuthUser {
  id: string;
  email: string;
  name: string | null;
  avatarUrl: string | null;
  plan: string;
}

interface AuthTokens {
  accessToken: string;
  refreshToken: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
  logout: () => void;
  getAccessToken: () => string | null;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const ACCESS_TOKEN_KEY = "offergpt-access-token";
const REFRESH_TOKEN_KEY = "offergpt-refresh-token";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

// ---------------------------------------------------------------------------
// Token helpers
// ---------------------------------------------------------------------------
function getStoredTokens(): AuthTokens | null {
  try {
    const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
    const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
    if (accessToken && refreshToken) {
      return { accessToken, refreshToken };
    }
  } catch {
    // localStorage 不可用（SSR / 隐私模式）
  }
  return null;
}

function storeTokens(tokens: AuthTokens) {
  try {
    localStorage.setItem(ACCESS_TOKEN_KEY, tokens.accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refreshToken);
    // 同步写入 cookie 供 middleware 读取（httpOnly=false 简化版）
    document.cookie = `${ACCESS_TOKEN_KEY}=${tokens.accessToken};path=/;max-age=2592000;SameSite=Lax`;
  } catch {
    // ignore
  }
}

function clearTokens() {
  try {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    document.cookie = `${ACCESS_TOKEN_KEY}=;path=/;max-age=0`;
  } catch {
    // ignore
  }
}

function getJwtPayload(token: string): { exp?: number } | null {
  try {
    const base64 = token.split(".")[1];
    return JSON.parse(atob(base64));
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------
const AuthContext = createContext<AuthContextValue>({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  login: async () => {},
  register: async () => {},
  logout: () => {},
  getAccessToken: () => null,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // 获取 access token
  const getAccessToken = useCallback((): string | null => {
    try {
      return localStorage.getItem(ACCESS_TOKEN_KEY);
    } catch {
      return null;
    }
  }, []);

  // 调用 GET /api/auth/me 验证 token 并获取用户
  const fetchMe = useCallback(async (token: string): Promise<AuthUser | null> => {
    try {
      const res = await fetch(`${API_BASE}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        return await res.json();
      }
    } catch {
      // 网络错误
    }
    return null;
  }, []);

  // 刷新 token
  const refreshAccessToken = useCallback(async (refreshToken: string): Promise<AuthTokens | null> => {
    try {
      const res = await fetch(`${API_BASE}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refreshToken }),
      });
      if (res.ok) {
        const data = await res.json();
        return {
          accessToken: data.accessToken,
          refreshToken: data.refreshToken,
        };
      }
    } catch {
      // 网络错误
    }
    return null;
  }, []);

  // 退出登录
  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
  }, []);

  // 登录
  const login = useCallback(async (email: string, password: string) => {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.message || "登录失败");
    }
    const data = await res.json();
    storeTokens({ accessToken: data.accessToken, refreshToken: data.refreshToken });
    setUser(data.user);
  }, []);

  // 注册
  const register = useCallback(async (email: string, password: string, name?: string) => {
    const res = await fetch(`${API_BASE}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name: name || "" }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.message || "注册失败");
    }
    const data = await res.json();
    storeTokens({ accessToken: data.accessToken, refreshToken: data.refreshToken });
    setUser(data.user);
  }, []);

  // 初始化：从 localStorage 恢复会话
  useEffect(() => {
    let cancelled = false;

    async function init() {
      const tokens = getStoredTokens();
      if (!tokens) {
        if (!cancelled) setIsLoading(false);
        return;
      }

      // 检查 access token 是否过期
      const payload = getJwtPayload(tokens.accessToken);
      const now = Math.floor(Date.now() / 1000);

      if (payload?.exp && payload.exp > now + 60) {
        // token 有效，直接验证
        const u = await fetchMe(tokens.accessToken);
        if (!cancelled && u) {
          setUser(u);
          setIsLoading(false);
          return;
        }
      }

      // token 即将过期或无效，尝试刷新
      const newTokens = await refreshAccessToken(tokens.refreshToken);
      if (newTokens && !cancelled) {
        storeTokens(newTokens);
        const u = await fetchMe(newTokens.accessToken);
        if (u) {
          setUser(u);
        }
      }
      if (!cancelled) setIsLoading(false);
    }

    init();
    return () => { cancelled = true; };
  }, [fetchMe, refreshAccessToken]);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: user !== null,
        isLoading,
        login,
        register,
        logout,
        getAccessToken,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
