import type { Metadata } from "next";
import Link from "next/link";
import { Fraunces, Hanken_Grotesk, JetBrains_Mono } from "next/font/google";
import { HAS_CLERK } from "@/lib/clerk";
import { BoltIcon } from "@/components/icons";
import "./globals.css";

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-display",
  axes: ["opsz", "SOFT", "WONK"],
  display: "swap",
});

const hanken = Hanken_Grotesk({
  subsets: ["latin"],
  variable: "--font-body",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Lightningfish",
  description: "A multi-agent deliberation simulator, not a forecaster — calibrated AI personas argue out a stock, a PR, or a Hacker News post.",
};

async function AuthNav() {
  if (!HAS_CLERK) return null;
  const { SignedIn, SignedOut, UserButton, SignInButton } = await import("@clerk/nextjs");
  return (
    <>
      <SignedIn>
        <a href="/history" className="hover:text-glow transition-colors">
          History
        </a>
        <a href="/dev/keys" className="hover:text-glow transition-colors">
          API Keys
        </a>
        <UserButton />
      </SignedIn>
      <SignedOut>
        <SignInButton>
          <button className="btn-ghost px-3.5 py-1.5 text-xs font-medium">Sign in</button>
        </SignInButton>
      </SignedOut>
    </>
  );
}

async function Shell({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${fraunces.variable} ${hanken.variable} ${jetbrainsMono.variable}`}>
      <body className="min-h-screen bg-ink-950 text-fg font-sans relative">
        {/* Atmosphere: a faint bioluminescent glow drifting behind the top of
            the page, plus a subtle grain so the near-black background never
            reads as a flat, dead #000. */}
        <div
          aria-hidden
          className="pointer-events-none fixed inset-0 -z-10"
          style={{
            backgroundImage:
              "radial-gradient(60rem 34rem at 15% -10%, rgba(63,235,184,0.10), transparent 60%), radial-gradient(40rem 26rem at 100% 0%, rgba(255,179,67,0.055), transparent 55%)",
          }}
        />
        <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 bg-grain" />

        <header className="border-b border-ink-700/80 px-6 py-4 flex items-center justify-between backdrop-blur-sm sticky top-0 z-10 bg-ink-950/80">
          <Link href="/" className="flex items-center gap-2 group">
            <BoltIcon className="w-3.5 h-3.5 text-glow animate-bolt-flicker" />
            <span className="font-display text-base tracking-tight text-fg">
              Lightningfish
            </span>
          </Link>
          <nav className="flex items-center gap-6 text-sm text-fg-muted">
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
