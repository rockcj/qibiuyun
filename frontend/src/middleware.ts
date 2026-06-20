import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import {
  ACCESS_TOKEN_KEY,
  clearAccessTokenCookie,
  isAccessTokenValid,
} from "@/lib/authTokens";

/** 无需登录即可访问的路径 */
const PUBLIC_PATHS = ["/login", "/register", "/demo"];

/** 静态资源和 API 路由不拦截 */
const SKIP_PATTERNS = ["/api/", "/_next/", "/favicon.ico", "/health"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // 首页始终可访问（未登录可使用 demo 模式体验）
  if (pathname === "/") {
    return NextResponse.next();
  }

  // 静态资源 / API 路由放行
  if (SKIP_PATTERNS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  // 公开页面：仅「有效 token」视为已登录；过期 cookie 需清除以免挡住登录页
  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));
  const accessToken = request.cookies.get(ACCESS_TOKEN_KEY)?.value;
  const hasValidToken = isAccessTokenValid(accessToken);

  if (isPublic) {
    if (hasValidToken) {
      return NextResponse.redirect(new URL("/", request.url));
    }
    if (accessToken) {
      const response = NextResponse.next();
      clearAccessTokenCookie(response);
      return response;
    }
    return NextResponse.next();
  }

  // 受限页面：无有效 token 则重定向到登录
  if (!hasValidToken) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    const response = NextResponse.redirect(loginUrl);
    if (accessToken) {
      clearAccessTokenCookie(response);
    }
    return response;
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
