import type { Metadata } from "next";
import Link from "next/link";
import { HAS_CLERK } from "@/lib/clerk";
import "./globals.css";

export const metadata: Metadata = {
  title: "Lightningfish",
  description: "Multi-agent opinion simulation for markets, code review, and Hacker News",
};

async function AuthNav() {
  if (!HAS_CLERK) return null;
  const { SignedIn, SignedOut, UserButton, SignInButton } = await import("@clerk/nextjs");
  return (
    <>
      <SignedIn>
        <a href="/history" className="hover:text-neutral-900 transition-colors">
          History
        </a>
        <a href="/dev/keys" className="hover:text-neutral-900 transition-colors">
          API Keys
        </a>
        <UserButton />
      </SignedIn>
      <SignedOut>
        <SignInButton>
          <button className="text-neutral-900 font-medium hover:underline">Sign in</button>
        </SignInButton>
      </SignedOut>
    </>
  );
}

async function Shell({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-white text-neutral-900">
        <header className="border-b border-neutral-200 px-6 py-4 flex items-center justify-between">
          <Link href="/" className="text-sm font-semibold tracking-tight">
            Lightningfish
          </Link>
          <nav className="flex items-center gap-6 text-sm text-neutral-500">
            <AuthNav />
          </nav>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  if (!HAS_CLERK) {
    return <Shell>{children}</Shell>;
  }
  const { ClerkProvider } = await import("@clerk/nextjs");
  return (
    <ClerkProvider>
      <Shell>{children}</Shell>
    </ClerkProvider>
  );
}
