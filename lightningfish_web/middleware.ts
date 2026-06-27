import { NextRequest, NextResponse } from "next/server";

const CLERK_KEY = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ?? "";
const HAS_CLERK =
  CLERK_KEY.startsWith("pk_") &&
  CLERK_KEY !== "pk_test_bGlnaHRuaW5nZmlzaC5sb2NhbGhvc3Qk";

export async function middleware(req: NextRequest) {
  if (!HAS_CLERK) return NextResponse.next();

  const { clerkMiddleware, createRouteMatcher } = await import("@clerk/nextjs/server");
  const isPublicRoute = createRouteMatcher([
    "/",
    "/sign-in(.*)",
    "/sign-up(.*)",
    "/report/(.*)",
  ]);
  const handler = clerkMiddleware(async (auth, r) => {
    if (!isPublicRoute(r)) await auth.protect();
  });
  // clerkMiddleware returns a Next.js middleware handler
  return handler(req, {} as never);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.svg).*)", "/"],
};
