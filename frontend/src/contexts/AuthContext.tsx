"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  clearTokens,
  getStoredTokens,
  isAccessTokenValid,
  storeTokens,
  type AuthTokens,
} from "@/lib/authTokens";

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

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

/** 无需强制跳转登录的公开路径 */
const PUBLIC_PATH_PREFIXES = ["/login", "/register", "/demo"];

function isPublicPath(pathname: string): boolean {
  return pathname === "/" || PUBLIC_PATH_PREFIXES.some((p) => pathname.startsWith(p));
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

  // 会话恢复失败：清除残留 token，必要时跳转登录
  const handleInvalidSession = useCallback(() => {
    clearTokens();
    setUser(null);

    const pathname = window.location.pathname;
    if (isPublicPath(pathname)) {
      // 首页等公开页：若曾持有失效 token，引导重新登录
      if (pathname === "/") {
        window.location.href = "/login";
      }
      return;
    }

    window.location.href = `/login?redirect=${encodeURIComponent(pathname)}`;
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

      // access token 仍有效时直接拉用户信息
      if (isAccessTokenValid(tokens.accessToken)) {
        const u = await fetchMe(tokens.accessToken);
        if (!cancelled && u) {
          setUser(u);
          setIsLoading(false);
          return;
        }
      }

      // access 失效或 /me 失败，尝试 refresh
      const newTokens = await refreshAccessToken(tokens.refreshToken);
      if (newTokens && !cancelled) {
        storeTokens(newTokens);
        const u = await fetchMe(newTokens.accessToken);
        if (u) {
          setUser(u);
          setIsLoading(false);
          return;
        }
      }

      // 本地 token 已不可用：清除并引导重新登录
      if (!cancelled) {
        setIsLoading(false);
        handleInvalidSession();
      }
    }

    init();
    return () => {
      cancelled = true;
    };
  }, [fetchMe, refreshAccessToken, handleInvalidSession]);

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
