import type { Metadata } from "next";
import { ClerkProvider, SignedIn, SignedOut, UserButton, SignInButton } from "@clerk/nextjs";
import "./globals.css";

export const metadata: Metadata = {
  title: "Lightningfish",
  description: "Multi-agent opinion simulation for finance and code review",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body className="min-h-screen bg-white text-neutral-900">
          <header className="border-b border-neutral-200 px-6 py-4 flex items-center justify-between">
            <a href="/" className="text-sm font-semibold tracking-tight">
              Lightningfish
            </a>
            <nav className="flex items-center gap-6 text-sm text-neutral-500">
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
                  <button className="text-neutral-900 font-medium hover:underline">
                    Sign in
                  </button>
                </SignInButton>
              </SignedOut>
            </nav>
          </header>
          <main>{children}</main>
        </body>
      </html>
    </ClerkProvider>
  );
}
