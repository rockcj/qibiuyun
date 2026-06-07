import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

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

  // 公开页面：已登录则跳回首页，未登录则放行
  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));
  const accessToken = request.cookies.get("offergpt-access-token")?.value;

  if (isPublic) {
    if (accessToken) {
      return NextResponse.redirect(new URL("/", request.url));
    }
    return NextResponse.next();
  }

  // 受限页面：无 token 则重定向到登录
  // 注意：demo 模式也放行（token 可能为空但后端会回退到 demo 用户）
  // 此处仅做基础检查，严格验证在后端 get_current_user 中完成
  if (!accessToken) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
